import asyncio
import os
import traceback

from tornado.httpserver import HTTPServer
from tornado.platform.asyncio import AsyncIOMainLoop
from tornado.web import RequestHandler, Application, StaticFileHandler

import utils


AsyncIOMainLoop().install()

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
        app = Application(
            [
                # Static file handlers
                (r'/(favicon.ico)', StaticFileHandler, {"path": ""}),

                # File upload handler
                (r'/upload', utils.StreamHandler, {"tmp_dir": TMP_DIR}),

                # Page handlers
                (r"/", MainHandler),
            ],
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True
        )

        server = HTTPServer(app, max_body_size=MAX_BUFFER)

        server.listen(8888)
        loop = asyncio.get_event_loop()
        print("Started mobius server.")
        loop.run_forever()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
        main()
