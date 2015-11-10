import logging

import tornado.websocket

from mobius.comm.stream import SocketFactory, INPROC
from mobius.comm.msg_pb2 import UploadProgress


log = logging.getLogger(__name__)


class UploadProgressWS(tornado.websocket.WebSocketHandler):
    '''
    WebSocket to report current file upload progress.
    '''
    def open(self):
        '''
        New web socket opened - self will be a new instance of TestWebSocket
        connected to its own client.
        '''
        log.info("New websocket connected: {0}".format(self))
        self._upload_progress = SocketFactory.router_socket("/mobius/upload_progress",
                                                            on_recv=self._recv_progress,
                                                            transport=INPROC,
                                                            bind=True,
                                                            loop=self.application.loop)
        up_prog = UploadProgress(progress=0)
        self._upload_progress.send(up_prog)

    def on_message(self, message):
        '''
        This socket received a message.

        @param message - the said message
        '''
        log.warning("Unexpected message: {0}".format(message))

    def on_close(self):
        '''
        This socket has been closed by the client.
        '''
        log.info("Web socket closing...")
        self._upload_progress.close()

    def _recv_progress(self, envelope, msgs):
        '''
        Receive progress messages, and pass them along to the user.

        @params msgs - progress message
        '''
        progress = msgs[-1]
        self.write_message(dict(progress=progress.progress))
