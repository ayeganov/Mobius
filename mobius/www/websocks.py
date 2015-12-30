import logging

from tornado import escape
import tornado.websocket

from mobius.comm import stream
from mobius.comm.msg_pb2 import Request, RESULT, ERROR, UPLOADING
from mobius.service import Command, Parameter
from mobius.utils import JSONObject

log = logging.getLogger(__name__)


class BaseWebSocket(tornado.websocket.WebSocketHandler):
    '''
    Base websocket handler to access the user instance.
    '''
    def get_current_user(self):
        '''
        Fetch current users information.
        '''
        user = escape.to_basestring(self.get_secure_cookie("mobius_user"))
        if user is None:
            return None
        return JSONObject(user)


class UploadProgressWS(BaseWebSocket):
    '''
    WebSocket to report current file upload progress.
    '''
    def open(self):
        '''
        New web socket opened - self will be a new instance of UploadProgressWS
        connected to its own client.
        '''
        user_id = self.get_secure_cookie("user_id")
        self.application._web_socks[user_id] = self

    def on_message(self, message):
        '''
        This socket received a message.

        @param message - the said message
        '''
        log.warning("Unexpected message: {0}".format(message))

    def send_progress(self, progress):
        '''
        Send progress message to the client.

        @params progress - progress message
        '''
        self.write_message(dict(progress=progress))


class ProviderUploadProgressWS(BaseWebSocket):
    '''
    WebSocket to report providers file upload progress.
    '''
    def open(self):
        '''
        Creates new instance of ProviderUploadProgressWS.
        '''
        self._progress_sub = stream.SocketFactory.sub_socket("/mobius/upload_progress",
                                                             on_recv=self._send_progress,
                                                             bind=True,
                                                             loop=self.application.loop)

    def _send_progress(self, envelope, msgs):
        '''
        Send received progress message to the client.

        @param envelope - envelope frames, will be filled with byte array if
                          they apply to this communication
        @param msgs - a list of received messages.
        '''
        msg = msgs[-1]
        self.write_message(dict(provider=msg.provider_id, progress=msg.progress))


class ProvidersService(BaseWebSocket):
    '''
    This websocket routes requests from the web to backend providers service,
    and routes responses back to the web.
    '''
    def open(self):
        log.info("Providers socket opening...")
        self._request_dealer = stream.SocketFactory.dealer_socket("/request/local",
                                                                  on_recv=self._process_result,
                                                                  transport=stream.INPROC,
                                                                  bind=False,
                                                                  loop=self.application.loop)

    def on_close(self):
        '''
        Web socket was closed on the client side.
        '''

    def on_message(self, request):
        '''
        Process web request in json format.
        '''
        json_req = JSONObject(request)
        log.info("Got request: {}".format(json_req))
        response = JSONObject()
        response.command = json_req.command
        response.apples = "How do you like them apples?!"
        self.write_message(response.json_string)

#        request = Request(command=json_req.command,
#                          params=json_req.params.json_string)

#        self._request_dealer.send(request)

    def _process_result(self, envelope, messages):
        '''
        Process responses from the service providers.

        @param envelope - unused parameter, should be an empty list.
        @param messages - a list containing a single response message.
        '''
        response = messages[-1]

        state = response.state

        if state.state_id == UPLOADING:
            result = JSONObject(state.response)
            log.info("Progress: {}".format(result))

        if state.state_id == ERROR:
            self.set_status(500)
            self.write_message(state.error)
        elif state.state_id == RESULT:
            self.set_status(200)
            self.write_message(state.response)
        else:
            self.set_status(500)
            self.write_message("Unexpected error occurred.")
