import multiprocessing.pool
import logging
import os

import zmq.eventloop

from mobius.comm.stream import SocketFactory
from mobius.db import db
from mobius.service import AbstractCommand, AbstractFactory, BaseService, Command
from mobius.utils import set_up_logging, JSONObject
from mobius.utils import eventloop

log = logging.getLogger(__name__)


NUM_WORKERS = 2
username = "vagrant"
authentication = "tmp"
dbname = "mydb"
host = "localhost"


class DBServiceError(Exception):
    '''
    All errors associated with Database service should extend this class.
    '''


class SaveFile(AbstractCommand):
    '''
    This command saves a file to the database.
    '''
    def __init__(self, path, filename, user_id, db_handle):
        '''
        Initialize the SaveFile command.

        @param path - full path to the file to be saved
        @param filename - name of the file provided by the user
        @param user_id - id of the user
        @param db_handle - handle to the database
        '''
        self._path = path
        self._filename = filename
        self._user_id = user_id
        # If ever decide to change SaveFile to run in a new process move
        # db_handle initialization to initialize()
        self._db_handle = db_handle

    def initialize(self):
        '''
        Nothing to do here.
        '''

    def run(self):
        '''
        Save the passed in file in the database.
        '''
        with self._db_handle.session_scope() as session:
            with open(self._path, "rb") as f:
                contents = f.read()
            file_3d = db.File(user_id=self._user_id, name=self._filename, data=contents)

            session.add(file_3d)
            session.commit()
            log.debug("File saved, removing it: {0}".format(self._path))
            try:
                os.remove(self._path)
            except OSError:
                log.error("Unable to delete file: {0}".format(self._path))
            result = JSONObject()
            result.model_id = file_3d.id
            return result.json_string


class FindUser(AbstractCommand):
    '''
    This command finds the user information in the database, and returns it to
    the requestor.
    '''
    def __init__(self, user_email, db_handle):
        self._user_email = user_email
        self._db_handle = db_handle

    def initialize(self):
        '''
        Nothing to do here.
        '''

    def run(self):
        '''
        Retrieve the user by their email.
        '''
        with self._db_handle.session_scope() as session:
            user = session.query(db.User)\
                                 .filter_by(email=self._user_email)\
                                 .one()
            result = JSONObject()
            result.id = user.id
            result.email = user.email
            result.password = user.password
            result.date_created = str(user.date_created).split(" ", 1)[0]
            return result.json_string


class CreateUser(AbstractCommand):
    '''
    Creates a new user.
    '''
    def __init__(self, user_email, user_pass, db_handle):
        self._user_email = user_email
        self._user_pass = user_pass
        self._db_handle = db_handle

    def initialize(self):
        '''
        Nothing to do here.
        '''

    def run(self):
        '''
        Do the thing.
        '''
        with self._db_handle.session_scope() as session:
            user = db.User(email=self._user_email,
                           password=self._user_pass)

            session.add(user)
            session.commit()

            json_user = JSONObject()
            json_user.id = user.id
            json_user.email = user.email
            json_user.date_created = str(user.date_created).split(" ", 1)[0]
            return json_user.json_string


class DBCommandFactory(AbstractFactory):
    '''
    This factory knows how to create commands for the database service.
    '''
    def __init__(self):
        '''
        Initialize the instance of DBCommandFactory.
        '''
        self._commands = {
            Command.SAVE_FILE: self.make_save_command,
            Command.FIND_USER: self.make_find_user_command,
            Command.CREATE_USER: self.make_create_user_command
        }

    @property
    def commands(self):
        return self._commands

    def make_save_command(self, envelope, request, context):
        '''
        Lets save provided file to the database.
        '''
        db_handle = context['db_handle']
        params = JSONObject(request.params)
        return SaveFile(params.path, params.filename, params.user_id, db_handle)

    def make_find_user_command(self, envelope, request, context):
        '''
        Fetch the user from the db.
        '''
        db_handle = context['db_handle']
        params = JSONObject(request.params)
        return FindUser(params.email, db_handle)

    def make_create_user_command(self, envelope, request, context):
        '''
        Create new user.
        '''
        db_handle = context['db_handle']
        params = JSONObject(request.params)
        return CreateUser(params.email, params.password, db_handle)


class DBService(BaseService):
    '''
    Database service responsible for CRUD operations on the database.

    Create channel:
        /db/request: Expects a DBRequest to be received. Stores the file
                     specified in the DB, and associates it with a proper user.
    '''
    def __init__(self, url, executor, loop):
        '''
        Initialize instance of DBService

        @param url - the URL encodes the database type(postgresql, sqlite,
                     etc), user, password and database name.
        @param executor - thread, or process pool to send work to
        @param loop - zmq event loop
        '''
        self._db_handle = db.DBHandle(url)
        self._db_request = SocketFactory.router_socket("/db/request",
                                                       on_recv=self.process_request,
                                                       loop=loop)
        self._db_factory = DBCommandFactory()
        super().__init__(executor, loop)

    @property
    def response_stream(self):
        return self._db_request

    @property
    def receive_stream(self):
        return self._db_request

    @property
    def name(self):
        return "DBService"

    @property
    def cmd_factory(self):
        return self._db_factory

    def handle_worker_state(self, msgs):
        pass

    def get_service_context(self):
        '''
        Database context must contain the handle to the database.
        '''
        return {"db_handle": self._db_handle}


def main():
    set_up_logging()

    loop = zmq.eventloop.IOLoop.instance()

    @eventloop
    def start_loop(loop):
        log.info("Database Service IOLoop started.")

    db_url = "postgresql://{usr}:{pswd}@{host}/{db}".format(usr=username,
                                                            pswd=authentication,
                                                            host=host,
                                                            db=dbname)
    with multiprocessing.pool.ThreadPool(NUM_WORKERS) as executor:
        dbserve = DBService(db_url, executor, loop)
        start_loop(loop)


if __name__ == "__main__":
    main()
