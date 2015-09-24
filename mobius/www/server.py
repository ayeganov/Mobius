# Standard lib
import argparse
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
from mobius.service import Command
from mobius.utils import set_up_logging, get_tmp_dir
from mobius.www.handlers import upload
from mobius.www.utils import get_max_request_buffer


log = logging.getLogger(__name__)

# TODO: Fix this by creating a util module
TMP_DIR = "/run/shm/"


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
        request = Request(command=Command.QUOTE.value,
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
    def port_type(value):
        '''
        Checks the value of the provided port is within the allowed range.
        '''
        try:
            ivalue = int(value)
            if 1 <= ivalue <= 1023:
                if os.getuid():
                    raise argparse.ArgumentTypeError("You must have root privileges to use port {0}"
                                                     .format(value))
            elif ivalue <= 0 or ivalue > 65535:
                raise ValueError()
            return ivalue
        except ValueError:
            raise argparse.ArgumentTypeError("Port value {0} is invalid.".format(value))

    try:
        parser = argparse.ArgumentParser(prog="Server", description="Tornado Server Instanc")
        parser.add_argument("-p",
                            "--port",
                            help="Port number to serve on.",
                            default=8888,
                            type=port_type)
        parser.add_argument("-v",
                            "--verbose",
                            help="Verbose mode shows more debugging information.",
                            default=False,
                            action="store_true")
        args = parser.parse_args()

        set_up_logging(logging.DEBUG if args.verbose else logging.INFO)
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
                (r'/upload', upload.StreamHandler, {"tmp_dir": get_tmp_dir(), "upload_pub": upload_pub}),

                (r'/test', TestHandler, {"loop": loop}),

                # Page handlers
                (r"/", MainHandler),
            ],
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True
        )

        server = HTTPServer(app, max_body_size=get_max_request_buffer())

        server.listen(args.port)
        print("Started mobius server.")
        loop.start()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
        main()
