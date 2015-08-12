import asyncio
import os
import traceback

import sgmsg

import libs.async_zmq as async_zmq
from tornado.platform.asyncio import AsyncIOMainLoop
import tornado.ioloop
import tornado.web
import tornado.websocket


AsyncIOMainLoop().install()

# TODO: Fix this by creating a util module
TMP_DIR = "/run/shm/"


class MainHandler(tornado.web.RequestHandler):
    '''
    This handler is responsible for serving up the root page of the
    application.
    '''
    def get(self):
        self.render("camera_view.html")


class NoCacheStaticFileHandler(tornado.web.StaticFileHandler):
    '''
    This handler disables caching of any files in the given directory.
    '''
    def set_extra_headers(self, path):
        '''
        Disable caching on files served from this path.
        '''
        self.set_header('Cache-Control',
                        'no-store, no-cache, must-revalidate, max-age=0')


class ImageServer(tornado.websocket.WebSocketHandler):
    '''
    This is the websocket connection that will serve the images back to the
    client.
    '''
    _image_pub = None
    _connections = []

    def __init__(self, *args, **kwargs):
        '''
        Initializes an instance of ImageServer.

        @param args - all positional args
        @param kwargs - all keyword args
        '''
        super(ImageServer, self).__init__(*args, **kwargs)
        if ImageServer._image_pub is None:
            ImageServer._image_pub = async_zmq.SocketFactory.sub_socket(
                                          topic="/tmp/img_path",
                                          on_recv=ImageServer._serve_image,
                                          loop=asyncio.get_event_loop())

    @staticmethod
    @asyncio.coroutine
    def _serve_image(img_path_msg):
        '''
        Callback that gets called whenever a camera serves images.

        @param img_path_msg - path to newly created image
        '''
        data = img_path_msg[-1]
        img_path = sgmsg.msgs.ImagePath.from_bytes(data)

        image_name = os.path.basename(img_path.path)
        image_url = os.path.join("images", image_name)
        for con in ImageServer._connections:
            yield from con(image_url)

    def open(self):
        '''
        Gets called when client opens a connection to this socket.
        '''
        print("Image websocket opened.")
        ImageServer._connections.append(self._send_image)

    def on_message(self, message):
        '''
        Gets called when message is received from client.

        @param message - message from client
        '''
        self.write_message("Did you say \"" + message + "\"")

    def on_close(self):
        '''
        Gets called when this websocket is closed.
        '''
        print("Image websocket closed.")
        try:
            ImageServer._connections.remove(self._send_image)
        except ValueError:
            print("Could not properly close websocket.")

    @asyncio.coroutine
    def _send_image(self, img_url):
        '''
        Callback that sends image URL to the client.

        @param img_url - URL to the image located on the server
        '''
        self.write_message(img_url)


class ShootSocket(tornado.websocket.WebSocketHandler):
    '''
    This socket is responsible for passing through AI commands to UI.
    '''
    _shoot_sub = None
    _connections = []

    def __init__(self, *args, **kwargs):
        '''
        Initializes an instance of ShootSocket.

        @param args - all positional args
        @param kwargs - all keyword args
        '''
        super(ShootSocket, self).__init__(*args, **kwargs)
        if ShootSocket._shoot_sub is None:
            ShootSocket._shoot_sub = async_zmq.SocketFactory.sub_socket(
                                          topic="/tmp/shoot",
                                          on_recv=ShootSocket._serve_shots,
                                          loop=asyncio.get_event_loop())

    def open(self):
        '''
        Gets called when client opens a connection to this socket.
        '''
        print("Shoot websocket opened.")
        ShootSocket._connections.append(self._send_shot)

    @staticmethod
    @asyncio.coroutine
    def _serve_shots(shot_msg):
        '''
        Sends the information about fired shots to the UI.
        '''
        shot_msg = shot_msg[-1]
        msg = sgmsg.msgs.Shoot.from_bytes(shot_msg)

        for con in ShootSocket._connections:
            yield from con(msg.type)

    @asyncio.coroutine
    def _send_shot(self, shot_type):
        '''
        Sends the shot type to the client.

        @param shot_type - type of shot commanded by the AI.
        '''
        if shot_type == sgmsg.msgs.Shoot.ShotType.single:
            self.write_message("single")

        elif shot_type == sgmsg.msgs.Shoot.ShotType.burst:
            self.write_message("burst")

        else:
            self.write_message("unknown")


def main():
    '''
    Main routine, what more do you want?
    '''
    try:
        app = tornado.web.Application(
            [
                # Static file handlers
                # First path is for testing locally wihtout RPi
#                (r'/images/(.*)', NoCacheStaticFileHandler, {'path': "/home/aleks/fun_data/squirt_data/motion/"}),
                (r'/images/(.*)', NoCacheStaticFileHandler, {'path': TMP_DIR}),

                # Websockets
                (r'/ws/camera', ImageServer),
                (r'/ws/shoot', ShootSocket),

                # Page handlers
                (r"/", MainHandler),
            ],
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            debug=True
        )

        app.listen(8888)
        loop = asyncio.get_event_loop()
        loop.run_forever()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
        main()
