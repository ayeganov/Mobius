from concurrent.futures import ThreadPoolExecutor
import logging
import os

import zmq.eventloop

from mobius.comm.msg_pb2 import MobiusModel, DBResponse
from mobius.comm.stream import SocketFactory
from mobius.db import db
from mobius.service import ICommand, AbstractFactory, BaseService, Command
from mobius.utils import set_up_logging
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


class SaveFile(ICommand):
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
        self._db_handle = db_handle

    def __call__(self):
        with self._db_handle.session_scope() as session:
            with open(self._path, "rb") as f:
                contents = f.read()
            file_3d = db.File(user_id=self._user_id, name=self._filename, data=contents)

            session.add(file_3d)
            session.commit()
            log.debug("File saved, removing path: {0}".format(self._path))
            os.remove(self._path)
            return file_3d.id
    __call__.__doc__ == ICommand.__call__.__doc__


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
        }

    @property
    def commands(self):
        return self._commands

    def make_save_command(self, request, context):
        '''
        Lets save provided file to the database.
        '''
        db_handle = context['db_handle']
        return SaveFile(request.path, request.filename, request.user_id, db_handle)


class DBService(BaseService):
    '''
    Database service responsible for CRUD operations on the database.

    Create channel:
        /db/new_file: Expects a DBRequest to be received. Stores the file
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
        self._executor = executor
        self._loop = loop
        self._new_file_rep = SocketFactory.router_socket("/db/new_file",
                                                         on_recv=self.process_request,
                                                         loop=loop)
        self._db_factory = DBCommandFactory()
        self._futures = {}

    @property
    def name(self):
        return "DBService"

    @property
    def cmd_factory(self):
        return self._db_factory

    def respond_success(self, envelope, request, result):
        log.debug("Responding successfully to {0} with {1}".format(request, result))
        model = MobiusModel(id=result, user_id=request.user_id)
        response = DBResponse(success=True, model=model)
        self._new_file_rep.reply(envelope, response)
    respond_success.__doc__ = BaseService.respond_success.__doc__

    def respond_error(self, envelope, request, error):
        log.debug("Responding with error to {0} with {1}".format(request, error))
        response = DBResponse(success=False, error=str(error))
        self._new_file_rep.reply(envelope, response)
    respond_error.__doc__ = BaseService.respond_error.__doc__

    def get_service_context(self):
        '''
        Database context must contain the handle to the database.
        '''
        return {"db_handle": self._db_handle}

    def _get_user(self, session, user_id):
        '''
        Fetches the user object from the database.

        @param session - database session
        @param user_id - id of the user in question
        @returns User instance
        @raises DBServiceError if user doesn't exist
        '''
        user = session.query(db.User).filter_by(id=user_id).first()
        if user is None:
            raise DBServiceError("Non-existant user id: {0}".format(user_id))
        return user

    def _save_file_to_db(self, path, filename, user_id):
        '''
        Reads the file from the given path, and stores in the database.

        @param path - file path
        @param filename - name of the file given by user
        @param user_id - id of the user who is uploading the file
        '''
        with self._db_handle.session_scope() as session:
            user = self._get_user(session, user_id)
            with open(path, "rb") as f:
                contents = f.read()
            file_3d = db.File(name=filename, data=contents)
            user.files.append(file_3d)

            session.add(user)
            session.commit()
            return file_3d.id


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
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        dbserve = DBService(db_url, executor, loop)
        start_loop(loop)


if __name__ == "__main__":
    main()
