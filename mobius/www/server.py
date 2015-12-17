# Standard lib
import argparse
import base64
import logging
import os
import traceback
import uuid


# 3rd party
import zmq.eventloop
from tornado import escape
from tornado import gen
from tornado.concurrent import Future
from tornado.httpserver import HTTPServer
from tornado.web import (
                         Application,
                         authenticated,
                         RequestHandler,
                         StaticFileHandler)

from mobius.db import db
from mobius.comm import stream
from mobius.comm.msg_pb2 import Request, RESULT, ERROR, UPLOADING
from mobius.comm.stream import SocketFactory
from mobius.service import Command, Parameter
from mobius.utils import set_up_logging, JSONObject, eventloop
from mobius.www.handlers import upload
from mobius.www.utils import get_max_request_buffer
from mobius.www.websocks import UploadProgressWS, ProviderUploadProgressWS


log = logging.getLogger(__name__)


username = "vagrant"
authentication = "tmp"
dbname = "mydb"
host = "localhost"


class RequestError(Exception):
    pass


class BaseHandler(RequestHandler):
    '''
    Defines a way to retrieve user object.
    '''
    def get_current_user(self):
        '''
        Fetch current users information.
        '''
        user = escape.to_basestring(self.get_secure_cookie("mobius_user"))
        if user is None:
            return None
        return JSONObject(user)


@gen.coroutine
def make_request(message, socket):
    '''
    Helper method to make async service requests.

    @param message - message to be sent to service
    @param socket - socket to send it on
    @returns service response message
    '''
    future = Future()

    # set result callback
    socket.on_recv(lambda _, msgs: future.set_result(msgs[-1]))
    socket.send(message)
    yield future

    # clear result callback
    socket.on_recv(None)
    return future.result()


@gen.coroutine
def hash_password(password, salt, loop):
    '''
    Make a request to hashing service to hash provided password.

    @param password - password to be hashed
    @param salt - password salt as required by bcrypt
    @param loop - event loop
    @returns hashed password
    '''
    return password
    hash_req = SocketFactory.dealer_socket("/login/request/hash",
                                           bind=False,
                                           loop=loop)
    params = JSONObject()
    params.password = password
    params.salt = salt
    login_request = Request(command=Command.HASH.value, params=params.json_string)
    login_response = yield make_request(login_request, hash_req)

    state = login_response.state
    if state.state_id == RESULT:
        return JSONObject(state.response)
    else:
        return None


@gen.coroutine
def load_user(email, loop):
    '''
    Issues a DB request for user information.

    @param email - email supplied by the user at login page.
    @returns user json object
    '''
    log.info("loading user: {}".format(email))
    user_req = SocketFactory.dealer_socket("/db/request",
                                           bind=False,
                                           loop=loop)

    params = JSONObject()
    params.email = email
    db_request = Request(command=Command.FIND_USER.value, params=params.json_string)
    db_response = yield make_request(db_request, user_req)
    state = db_response.state
    if state.state_id == RESULT:
        return JSONObject(state.response)
    else:
        return None


@gen.coroutine
def create_user(email, password, loop):
    '''
    Command to create a new user in mobius DB.

    @param email - user email
    @param user - user password
    @param loop - zmq event loop
    '''
    user_req = SocketFactory.dealer_socket("/db/request",
                                           bind=False,
                                           loop=loop)

    params = JSONObject()
    params.email = email
    params.password = password
    db_request = Request(command=Command.CREATE_USER.value, params=params.json_string)
    db_response = yield make_request(db_request, user_req)
    state = db_response.state
    if state.state_id == RESULT:
        return JSONObject(state.response)
    else:
        return None


class AuthCreateHandler(BaseHandler):
    '''
    Sign up page.
    '''
    def initialize(self, loop):
        self._loop = loop

    def get(self):
        self.render("login.html", error=None, next_page=self.get_argument('next', '/'))

    @gen.coroutine
    def post(self):
        '''
        Create new user.
        '''
        email = escape.to_basestring(self.get_argument('email'))
        password = escape.to_basestring(self.get_argument('password'))
        log.info("Creating new user: {} - {}".format(email, password))
        hashed_password = yield hash_password(password, salt=None, loop=self._loop)

        try:
            new_user = yield create_user(email, hashed_password, loop=self._loop)
            if new_user is None:
                raise RequestError("Failed to create user. User possibly already exists.")

            if "password" in new_user:
                del new_user.password
            self.set_secure_cookie("mobius_user", new_user.json_string)
            self.redirect(self.get_argument("next_page", "/"))
        except RequestError as req_err:
            self.render("login.html", error=str(req_err))


class AuthLoginHandler(BaseHandler):
    '''
    All login related activity should be done in this handler.
    '''
    def initialize(self, loop):
        self._loop = loop

    def get(self):
        if self.current_user is None:
            self.render("login.html", error=None, next_page=self.get_argument('next', '/'))
        else:
            self.redirect("/")

    @gen.coroutine
    def post(self):
        email = escape.to_basestring(self.get_argument('email'))
        password = escape.to_basestring(self.get_argument('password'))

        user = yield load_user(email, self._loop)

        if user is None:
            self.render('login.html',
                        error="Incorrect Credentials",
                        next_page=self.get_argument('next_page', '/'))
            return

        hashed_password = yield hash_password(password, salt=user.password, loop=self._loop)
        if hashed_password == user.password:
            # don't forget to delete the password from the cookie
            del user.password
            self.set_secure_cookie("mobius_user", user.json_string)
            self.redirect(self.get_argument('next_page', '/'))
        else:
            self.render("login.html", error="Incorrect Credentials")


class AuthLogoutHandler(BaseHandler):
    '''
    All logout activity should be done in this handler.
    '''
    def initialize(self, loop):
        self._loop = loop

    def get(self):
        self.render("logout.html", user=self.current_user)

    def post(self):
        self.clear_cookie("mobius_user")
        self.redirect("/")


class MainHandler(BaseHandler):
    '''
    This handler is responsible for serving up the root page of the
    application.
    '''
    def initialize(self, db_handle):
        self._db_handle = db_handle
        self._user_id = None

    @authenticated
    def get(self):
        self.render("index.html", user=self.current_user)


class QuoteHandler(BaseHandler):
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

    def _process_result(self, envelope, msgs):
        response = msgs[-1]
        self._request_future.set_result(response)

    @authenticated
    @gen.coroutine
    def get(self):
        log.info("Test handler get")
        self._request_future = Future()
        mobius_id = int(self.get_argument("mobius_id", default=1))

        user_id = self.current_user.id
        params = JSONObject()
        params.mobius_id = mobius_id
        params.user_id = user_id
        params.http_params = {Parameter.QUANTITY.name: 1,
                              Parameter.SCALE.name: 0.1,
                              Parameter.UNIT.name: "cm"}
#                              Parameter.MATERIAL.name: "metal_cast_silver_sanded"}

        request = Request(command=Command.QUOTE.value,
                          params=params.json_string)
        self._request_dealer.send(request)

        log.info("Lets wait here one second.")
        yield self._request_future
        log.info("One second should have passed.")

        response = self._request_future.result()
        state = response.state
        if state.state_id == ERROR:
            self.set_status(500)
            self.write(state.error)
        elif state.state_id == RESULT:
            self.set_status(200)
            self.write(state.response)
        else:
            self.set_status(500)
            self.write("Unexpected error occurred.")
        self._request_future = None


class UploadToProvider(BaseHandler):
    '''
    Upload the file associated with the given mobius id to all providers.
    '''
    def initialize(self, loop):
        self._loop = loop
        self._request_dealer = SocketFactory.dealer_socket("/request/local",
                                                           on_recv=self._process_result,
                                                           transport=stream.INPROC,
                                                           bind=False,
                                                           loop=loop)
        self._request_future = None

    def _process_result(self, envelope, msgs):
        response = msgs[-1]
        self._request_future.set_result(response)

    @gen.coroutine
    def get(self):
        log.info("UploadToProvider handler get")
        self._request_future = Future()
        mobius_id = int(self.get_argument("mobius_id", default=0))
        user_id = self.current_user.id

        params = JSONObject()
        params.mobius_id = mobius_id
        params.user_id = user_id
        request = Request(command=Command.UPLOAD.value,
                          params=params.json_string)
        self._request_dealer.send(request)

        log.info("Lets wait here one second.")
        yield self._request_future
        log.info("One second should have passed.")

        response = self._request_future.result()
        state = response.state
        while state.state_id == UPLOADING:
            result = JSONObject(state.response)
            log.info("Progress: {}".format(result.progress))
            self._request_future = Future()
            yield self._request_future
            response = self._request_future.result()
            state = response.state

        if state.state_id == ERROR:
            self.set_status(500)
            self.write(state.error)
        elif state.state_id == RESULT:
            self.set_status(200)
            self.write(state.response)
        else:
            self.set_status(500)
            self.write("Unexpected error occurred.")
        self._request_future = None


class Session:
    """
    A user's session with a system.
    This utility class contains no functionality, but is used to
    represent a session.
    @ivar uid: A unique identifier for the session, C{bytes}.
    @ivar _reactor: An object providing L{IReactorTime} to use for scheduling
        expiration.
    @ivar sessionTimeout: timeout of a session, in seconds.
    """
    sessionTimeout = 900

    _expireCall = None

    def __init__(self, app, uid, loop=None):
        """
        Initialize a session with a unique ID for that session.
        """
        self._loop = zmq.eventloop.IOLoop.instance() if loop is None else loop

        self.app = app
        self.uid = uid
        self.expireCallbacks = []
        self.touch()
        self.sessionNamespaces = {}

    def startCheckingExpiration(self):
        """
        Start expiration tracking.
        @return: C{None}
        """
        self._expireCall = self._reactor.callLater(
            self.sessionTimeout, self.expire)

    def notifyOnExpire(self, callback):
        """
        Call this callback when the session expires or logs out.
        """
        self.expireCallbacks.append(callback)

    def expire(self):
        """
        Expire/logout of the session.
        """
        del self.site.sessions[self.uid]
        for c in self.expireCallbacks:
            c()
        self.expireCallbacks = []
        if self._expireCall and self._expireCall.active():
            self._expireCall.cancel()
            # Break reference cycle.
            self._expireCall = None

    def touch(self):
        """
        Notify session modification.
        """
        self.lastModified = self._reactor.seconds()
        if self._expireCall is not None:
            self._expireCall.reset(self.sessionTimeout)


class MobiusApplication(Application):
    '''
    Mobius application that defines all request handlers.
    '''
    def __init__(self, loop):
        self._loop = loop

        db_url = "postgresql://{usr}:{pswd}@{host}/{db}".format(usr=username,
                                                                pswd=authentication,
                                                                host=host,
                                                                db=dbname)
        self._db_handle = db.DBHandle(db_url, verbose=False)
        handlers = [
            # Static file handlers
            (r'/(favicon.ico)', StaticFileHandler, {"path": ""}),

            # File upload handler
            (r'/upload', upload.StreamHandler, {"loop": self._loop}),

            (r'/quote', QuoteHandler, {"loop": self._loop}),
            (r'/provider_upload', UploadToProvider, {"loop": self._loop}),

            (r'/ws/upload_progress', UploadProgressWS),
            (r'/ws/provider_upload_progress', ProviderUploadProgressWS),

            # Page handlers
            (r"/", MainHandler, {"db_handle": self._db_handle}),
            (r"/auth/create", AuthCreateHandler, {"loop": self._loop}),
            (r"/auth/login", AuthLoginHandler, {"loop": self._loop}),
            (r"/auth/logout", AuthLogoutHandler, {"loop": self._loop}),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            cookie_secret=base64.encodebytes(uuid.uuid4().bytes + uuid.uuid4().bytes),
            login_url="/auth/login",
            debug=True,
        )
        self._sessions = {}
        self._web_socks = {}
        super().__init__(handlers, **settings)

    @property
    def sessions(self):
        '''
        Get all user sessions associated with this application.
        '''
        return self._sessions


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


def main():
    '''
    Main routine, what more do you want?
    '''

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
        loop = zmq.eventloop.IOLoop.instance()
        local_proxy = stream.LocalRequestProxy(front_end_name="/request/local",
                                               back_end_name="/request/request",
                                               loop=loop)
        app = MobiusApplication(loop=loop)
        server = HTTPServer(app, max_body_size=get_max_request_buffer())

        @eventloop
        def start_loop(loop):
            log.info("Mobius server running on port {} started.".format(args.port))
            server.listen(args.port)
            loop.start()

        start_loop(loop)

    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to interrupt...")
    except Exception as e:
        log.exception(e)


if __name__ == "__main__":
        main()
