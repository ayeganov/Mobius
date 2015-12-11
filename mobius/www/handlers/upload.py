import json
import logging
import tempfile

import tornado.gen
from tornado.concurrent import Future
from tornado import escape

# Mobius
from mobius.comm.msg_pb2 import Request, RESULT, ERROR, UPLOADING
from mobius.comm.stream import SocketFactory
from mobius.service import Command
from mobius.utils import get_tmp_dir, JSONObject
from mobius.www.utils import PostContentHandler


log = logging.getLogger(__name__)


class StreamHandler(PostContentHandler):
    '''
    Upload file request handler. It downloads the file in streaming mode from
    the client, and stores the downloaded files in the provided temporary
    directory.
    '''
    DISPOSITION = "Content-Disposition"
    FILE_FIELD = "fileID"
    NAME_FIELD = "fileName"
    POST_SUCCESS = 201

    def initialize(self, loop):
        '''
        The initialization method for this request handler.

        @param loop - zmq eventloop
        '''
        super(StreamHandler, self).initialize()
        self._tmp_file = tempfile.NamedTemporaryFile(dir=get_tmp_dir(), delete=False)
        self._upload_pub = SocketFactory.dealer_socket("/db/request",
                                                       bind=False,
                                                       on_recv=self._handle_response,
                                                       loop=loop)
        self._cur_headers = None
        self._file_started = False
        self._user_file_name = None
        self._upload_future = None
        self._uploaded_model_id = None
        self._web_sock = None #self.application._web_socks.get(self._user_id, None)

    def get_current_user(self):
        '''
        Fetch current users information.
        '''
        user = escape.to_basestring(self.get_secure_cookie("mobius_user"))
        if user is None:
            return None
        return JSONObject(user)

    def _handle_response(self, envelope, msgs):
        '''
        Handle the response from the database.

        @param envelope - a list of router socket ids
        @param msgs - list of messages
        '''
        self._upload_future.set_result(msgs[-1])

    def on_finish(self):
        '''
        Do the clean ups here.
        '''
        self._tmp_file.close()

    def post(self):
        '''
        Overriden post method to respond to the client.
        '''
        self.set_header("Content-Type", "text/plain")
        self.set_status(self.POST_SUCCESS)
        if self._uploaded_model_id is not None:
            self.write(json.dumps({"success": True,
                                  "model_id": self._uploaded_model_id}))
        else:
            self.write(json.dumps({"success": False,
                                  "model_id": -1}))
        self.finish()

    def _write_file_data(self, headers, data):
        '''
        Writes the data to the temporary file.

        @param headers - HTTP headers for this file
        @param data - a chunk of file data
        '''
        self._tmp_file.write(data)

    def _process_form_field(self, headers, data):
        '''
        Saves the data entered into the upload form.

        @param headers - HTTP headers for this form field
        @param data - data entered into the field.
        '''
        if self._get_field_name(headers) == self.NAME_FIELD:
            self._user_file_name = data.decode(self.HEADER_ENCODING)

    def _get_field_name(self, headers):
        '''
        Retrieve the name of the field from the given headers.

        @param headers - HTTP headers
        @returns name of the field specified on the page
        '''
        try:
            return headers[self.DISPOSITION]["params"]["name"]
        except KeyError:
            return None

    def receive_data(self, headers, chunk):
        if self._cur_headers != headers:
            self._cur_headers = headers

        if self._web_sock is not None:
            self._web_sock.send_progress(self.progress)
        else:
            log.error("Erroneous state: Unable to retrieve upload progress WS")

        # Process different content types differently
        if self._get_field_name(self._cur_headers) == self.FILE_FIELD:
            self._write_file_data(self._cur_headers, chunk)
        else:
            self._process_form_field(self._cur_headers, chunk)
    receive_data.__doc__ = PostContentHandler.receive_data.__doc__

    @tornado.gen.coroutine
    def request_done(self):
        self._upload_future = Future()

        params = JSONObject()
        params.path = self._tmp_file.name
        params.filename = self._user_file_name
        params.user_id = self.current_user.id

        upload_file = Request(command=Command.SAVE_FILE, params=params.json_string)
        log.info("Sending upload file: {0}".format(str(upload_file)))
        self._upload_pub.send(upload_file)
        yield self._upload_future

        try:
            response = self._upload_future.result()
            state = response.state
            if state.state_id == RESULT:
                log.debug("Successfully uploaded file {}".format(self._user_file_name))
                json_resp = JSONObject(state.response)
                self._uploaded_model_id = json_resp.model_id
            elif state.state_id == ERROR:
                log.debug("Failed to upload file {}".format(self._user_file_name))
            else:
                log.error("Unexpected response received: {}".format(str(response)))
        except:
            log.error("Error while uploading file: {}".format(self._user_file_name))

    request_done.__doc__ = PostContentHandler.request_done.__doc__
