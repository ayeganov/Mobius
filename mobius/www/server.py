# Standard lib
import os
import traceback


# 3rd party
from tornado import ioloop
from tornado.httpserver import HTTPServer
from tornado.web import (RequestHandler,
                         Application,
                         StaticFileHandler)

from mobius.www.handlers import upload
from mobius.comm.stream import SocketFactory

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


def main():
    '''
    Main routine, what more do you want?
    '''
    try:
        upload_pub = SocketFactory.pub_socket("/upload/ready/")
        app = Application(
            [
                # Static file handlers
                (r'/(favicon.ico)', StaticFileHandler, {"path": ""}),

                # File upload handler
                (r'/upload', upload.StreamHandler, {"tmp_dir": TMP_DIR, "upload_pub": upload_pub}),

                # Page handlers
                (r"/", MainHandler),
            ],
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True
        )

        server = HTTPServer(app, max_body_size=MAX_BUFFER)

        server.listen(8888)
        loop = ioloop.IOLoop.instance()
        print("Started mobius server.")
        loop.start()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
        main()
