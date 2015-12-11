import logging

import tornado.websocket

from mobius.comm.stream import SocketFactory

log = logging.getLogger(__name__)


class UploadProgressWS(tornado.websocket.WebSocketHandler):
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


class ProviderUploadProgressWS(tornado.websocket.WebSocketHandler):
    '''
    WebSocket to report providers file upload progress.
    '''
    def open(self):
        '''
        Creates new instance of ProviderUploadProgressWS.
        '''
        self._progress_sub = SocketFactory.sub_socket("/mobius/upload_progress",
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
