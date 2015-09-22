# Standard lib
import logging
import os
import traceback


# 3rd party
from zmq import eventloop
from tornado.concurrent import Future
from tornado import gen
from tornado.httpserver import HTTPServer
from tornado.web import (RequestHandler,
                         Application,
                         StaticFileHandler)

from mobius.comm import stream
from mobius.comm.msg_pb2 import Request, MobiusModel
from mobius.comm.stream import SocketFactory
from mobius.service import QUOTE, UPLOAD, TEST
from mobius.www.handlers import upload
from mobius.utils import set_up_logging


log = logging.getLogger(__name__)

# TODO: Fix this by creating a util module
TMP_DIR = "/run/shm/"
MAX_BUFFER = 1024**3


class MainHandler(RequestHandler):
    '''
    This handler is responsible for serving up the root page of the
    application.
    '''
    def get(self):
        self.render("index.html")


class TestHandler(RequestHandler):
    '''
    Remove me.
    '''
    def initialize(self, loop):
        self._loop = loop
        self._request_dealer = SocketFactory.dealer_socket("/request/local",
                                                           on_recv=self._process_result,
                                                           transport=stream.INPROC,
                                                           bind=False,
                                                           loop=loop)

        self._request_future = None

    def _process_result(self, msgs):
        response = msgs[-1]
        log.info("Response: {0}".format(msgs))
        self._request_future.set_result(response)

    @gen.coroutine
    def get(self):
        log.info("Test handler get")
        self._request_future = Future()

        mob_model = MobiusModel(id="hello", user_id="world")
        request = Request(type=UPLOAD,
                          model=mob_model)
        self._request_dealer.send(request)

        log.info("Lets wait here one second.")
        yield self._request_future
        log.info("One second should have passed.")

        response = self._request_future.result()
        print("Type of response: {0}".format(type(response)))
        if response.HasField("error"):
            self.set_status(500)
            self.write(response.error)
        elif response.HasField("response"):
            self.set_status(200)
            self.write(response.response)
        self._request_future = None


def main():
    '''
    Main routine, what more do you want?
    '''
    try:
        set_up_logging()
        loop = eventloop.IOLoop.instance()
        upload_pub = SocketFactory.pub_socket("/upload/ready/")
        local_proxy = stream.LocalRequestProxy(front_end_name="/request/local",
                                               back_end_name="/request/request",
                                               loop=loop)
        app = Application(
            [
                # Static file handlers
                (r'/(favicon.ico)', StaticFileHandler, {"path": ""}),

                # File upload handler
                (r'/upload', upload.StreamHandler, {"tmp_dir": TMP_DIR, "upload_pub": upload_pub}),

                (r'/test', TestHandler, {"loop": loop}),

                # Page handlers
                (r"/", MainHandler),
            ],
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True
        )

        server = HTTPServer(app, max_body_size=MAX_BUFFER)

        server.listen(8888)
        print("Started mobius server.")
        loop.start()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
        main()
