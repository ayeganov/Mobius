import json
import logging
import tempfile

import tornado.gen
from tornado.concurrent import Future

# Mobius
from mobius.comm.msg_pb2 import DBRequest, UploadProgress
from mobius.comm.stream import SocketFactory, INPROC
from mobius.service import Command
from mobius.utils import get_tmp_dir
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
        self._upload_pub = SocketFactory.dealer_socket("/db/new_file",
                                                       bind=False,
                                                       on_recv=self._handle_response,
                                                       loop=loop)
        self._upload_progress_router = SocketFactory.router_socket("/mobius/upload_progress",
                                                                   bind=False,
                                                                   transport=INPROC,
                                                                   on_recv=self._store_envelope,
                                                                   loop=loop)
        self._cur_headers = None
        self._file_started = False
        self._user_file_name = None
        self._user_id = int(self.get_secure_cookie("user_id"))
        self._upload_future = None
        self._uploaded_model_id = None
        self._envelope = None

    def _store_envelope(self, envelope, _):
        log.info("Saving envelope: {0}".format(envelope))
        self._envelope = envelope

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

        print("Progress: {0}".format(self.progress))
        if self._envelope:
            progress = UploadProgress(progress=self.progress)
            self._upload_progress_router.reply(self._envelope, progress)

        # Process different content types differently
        if self._get_field_name(self._cur_headers) == self.FILE_FIELD:
            self._write_file_data(self._cur_headers, chunk)
        else:
            self._process_form_field(self._cur_headers, chunk)
    receive_data.__doc__ = PostContentHandler.receive_data.__doc__

    @tornado.gen.coroutine
    def request_done(self):
        self._upload_future = Future()
        upload_file = DBRequest(command=Command.SAVE_FILE,
                                path=self._tmp_file.name,
                                filename=self._user_file_name,
                                user_id=self._user_id)
        log.info("Sending upload file: {0}".format(str(upload_file)))
        self._upload_pub.send(upload_file)
        yield self._upload_future

        try:
            result = self._upload_future.result()
            if result.success:
                log.debug("Successfully uploaded file {0}".format(self._user_file_name))
                self._uploaded_model_id = result.model.id
            else:
                log.debug("Failed to upload file {0}".format(self._user_file_name))
        except:
            log.error("Error while uploading file: {0}".format(self._user_file_name))

    request_done.__doc__ = PostContentHandler.request_done.__doc__
