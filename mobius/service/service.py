import abc
import collections
import enum
import itertools
import json
import logging

import zmq

from mobius.comm.stream import SocketFactory, Socket
from mobius.comm.msg_pb2 import Response, RESULT, ERROR, WorkerState

log = logging.getLogger(__name__)


UploadResponse = collections.namedtuple('UploadResponse', ['provider_id', 'model_name'])


class ServiceError(Exception):
    '''
    All service errors should use this exception type.
    '''


class ParamError(ServiceError):
    '''
    Error converting parameters.
    '''


class Command(enum.IntEnum):
    '''
    This list all commands that services can understand, and execute.
    '''
    QUOTE = 1
    UPLOAD = 2
    SAVE_FILE = 3
    FIND_USER = 4
    CREATE_USER = 5


class Parameter(enum.IntEnum):
    '''
    Mobius parameter types.
    '''
    ID = 1
    QUANTITY = 2
    SCALE = 3
    UNIT = 4
    CURRENCY = 5
    MATERIAL = 6

    def __repr__(self):
        return self.name


def make_param_string(provider_map, params):
    '''
    Given the parameters dictionary containing keys and values.

    @param provider_map - mapping of mobius params to provider params
    @param params - parameters with accompanying values
    @returns parameter string to be appended to the URL
    '''
    try:
        params = ("=".join((provider_map[key], str(value))) for key, value in params.items())
        param_string = "&".join(params)
        return param_string
    except KeyError as ke:
        raise ParamError("Unable to convert parameter: {0}".format(ke.args[0]))


class AbstractCommand(metaclass=abc.ABCMeta):
    """
    This is the interface that all commands must implement to work with mobius
    worker services.
    """
    def __call__(self):
        """
        Execute this command. By the time this method is invoked command must
        contain all the necessary information for the execution to succeed.
        """
        self.initialize()
        return self.run()

    @abc.abstractmethod
    def initialize(self):
        '''
        This method will be called within the new process/thread, so all
        resources must be acquired here, especially if the command runs in a new
        process.
        '''

    @abc.abstractmethod
    def run(self):
        '''
        Execute the command.
        '''


class MobiusCommand(AbstractCommand):
    '''
    Mobius command can communicate back to the service that spawned it.
    '''
    def initialize(self, parent):
        '''
        Initialize MobiusCommand - this method creates a zmq socket to talk
        back to the parent process.

        @param parent - parent service of this command that spawned it.
        '''
        self._work_state = Socket("/worker/state/{}".format(parent),
                                  sock_type=zmq.DEALER,
                                  bind=False)

    @abc.abstractproperty
    def envelope(self):
        '''
        Address of the command requestor.
        '''

    def send_async_data(self, gpb_msg):
        '''
        Send data back to the parent process.

        @param gpb_msg - google protocol buffer message to be sent to the
                         parent process.
        '''
        self._work_state.reply(self.envelope, gpb_msg)


class AbstractFactory(metaclass=abc.ABCMeta):
    '''
    Factory for creating command objects.

    Takes in a Request message, and based on its type creates an appropriate
    Command object. Implementers must provide the commands dictionary mapping
    Command enums to appropriate methods creating the requested commands.
    '''
    @abc.abstractproperty
    def commands(self):
        '''
        Dictionary of the commands this factory knows how to create. The keys
        must match the Command enum entries.
        '''

    def create_command(self, envelope, request, context=None):
        '''
        Create a command object based on the provided request message.

        @param envelope - address of the requestor
        @param request - an instance of Request message defined in msg.proto
        @param context - context containing extra data to be passed to commands
        @returns a concrete instance of AbstractCommand interface
        '''
        try:
            return self.commands[request.command](envelope, request, context=context)
        except KeyError:
            raise ServiceError("{0} does not support command {1}"
                               .format(self.__class__.__name__, Command(request.command)))
        except Exception as e:
            log.exception(e)
            raise e


class ProviderFactory(AbstractFactory):
    '''
    This factory knows how to make commands for 3D providers. Look at Command
    for a list of commands. Currently supported commands:

        make_upload_command
        make_quote_command
    '''
    def __init__(self):
        '''
        Initialize instance of ProviderFactory.
        '''
        self._commands = {
            Command.QUOTE: self.make_quote_command,
            Command.UPLOAD: self.make_upload_command
        }

    @property
    def commands(self):
        return self._commands

    @abc.abstractmethod
    def make_upload_command(self, request, context=None):
        '''
        Create an instance of the upload command

        @param request - an instance of Request message defined in msg.proto
        @param context - context containing extra data maybe needed by this
                         command
        '''

    @abc.abstractmethod
    def make_quote_command(self, request, context=None):
        '''
        Create an instance of the quote command

        @param request - an instance of Request message defined in msg.proto
        @param context - context containing extra data maybe needed by this
                         command
        '''

    def get_service_context(self):
        '''
        Default implementation doesn't have any context.
        '''
        return None


class IService(metaclass=abc.ABCMeta):
    '''
    This is a service interface that defines the core service methods. This
    interface assumes the usage of 0MQ sockets as the driving mechanism of
    execution.
    '''
    @abc.abstractproperty
    def cmd_factory(self):
        '''
        Return the factory which knows how to create commands for this service.
        '''

    @abc.abstractproperty
    def receive_stream(self):
        '''
        ZMQ stream which is responsible for receiving service requests.
        '''

    @abc.abstractproperty
    def response_stream(self):
        '''
        ZMQ stream which is responsible for transmitting request responses.
        '''

    @abc.abstractmethod
    def get_service_context(self):
        '''
        Return service specific context with extra data that needs to be passed
        down to the workers.
        '''

    @abc.abstractmethod
    def process_request(self, envelope, request):
        '''
        Determine the request type and issue an appropriate command.

        @param envelope - 0MQ socket ids to respond back to the correct requestor
        @param request - original request message
        @param result - result of the computation
        '''

    @abc.abstractmethod
    def respond_success(self, envelope, request, result):
        '''
        Given the original request, and produced result create a message to
        respond back to the requestor.

        @param envelope - 0MQ socket ids to respond back to the correct requestor
        @param request - the original request message
        @param result - result of the computation
        '''

    @abc.abstractmethod
    def respond_error(self, envelope, request, error):
        '''
        Given the original request, and error produced during computatoin
        create a message to respond back to the requestor.

        @param envelope - 0MQ socket ids to respond back to the correct requestor
        @param request - the original request message
        @param error - error encountered during computation
        '''

    @abc.abstractmethod
    def handle_worker_state(self, _, msgs):
        '''
        When workers report their state of execution this method will receive
        WorkerState.

        @param msgs - a list of worker states messages
        '''

    @abc.abstractmethod
    def worker_id(self):
        '''
        A unique worker id to be given to a newly spawned command process.
        '''


class BaseService(IService):
    '''
    This service accepts a message with command attribute and replies with a
    user specified message message. Extenders must define a self.cmd_factory
    property, which must return a concrete instance of CommandFactory. Extender
    must implement their own version of CommandFactory.
    '''
    def __init__(self, executor, loop):
        '''
        Initialize instance of base service

        @param executor - an instance of ProcessPoolExecutor, or ThreadPoolExecutor
        @param loop - zmq eventloop
        '''
        self._loop = loop
        self.receive_stream.on_recv(self.process_request)
        self._worker_state = SocketFactory.dealer_socket("/worker/state/%s" % self.name,
                                                         on_recv=self.handle_worker_state,
                                                         bind=True,
                                                         loop=loop)
        self._executor = executor
        self._futures = {}
        self._worker_id = itertools.count(start=1)

    @abc.abstractproperty
    def name(self):
        '''
        Return the name of this service.
        '''

    def worker_id(self):
        return next(self._worker_id)
    worker_id.__doc__ = IService.worker_id.__doc__

    def respond_error(self, envelope, request, error):
        log.debug("Responding with error to {0} with {1}".format(request, error))
        json_error = json.dumps({"error": str(error)})

        work_state = WorkerState(state_id=ERROR, error=json_error)
        response = Response(service_name=self.name,
                            state=work_state)
        self.response_stream.reply(envelope, response)
    respond_error.__doc__ = IService.respond_error.__doc__

    def respond_success(self, envelope, request, result):
        log.debug("Responding successfully to {0} with {1}".format(request, result))
        work_state = WorkerState(state_id=RESULT, response=result)
        response = Response(service_name=self.name,
                            state=work_state)
        self.response_stream.reply(envelope, response)
    respond_success.__doc__ = IService.respond_success.__doc__

    def process_request(self, envelope, msgs):
        request = msgs[-1]
        try:
            log.debug("Got work request: {0} from {1})"
                      .format(request, envelope))
            context = self.get_service_context()
            worker = self.cmd_factory.create_command(envelope, request, context)

            work_id = self.worker_id()

            done_callback = lambda _: self._finish_request(work_id)
            future = self._executor.apply_async(worker,
                                                callback=done_callback,
                                                error_callback=done_callback)

            self._futures[work_id] = (envelope, request, future)
        except Exception as e:
            log.exception(e)
            self.respond_error(envelope, request, e)
    process_request.__doc__ = IService.process_request.__doc__

    def _finish_request(self, work_id):
        '''
        After request is processed return the result to the requestor

        @param future - result of work
        '''
        envelope, request, future = self._futures[work_id]

        def finish_up():
            try:
                log.debug("Finished work for {0}".format(str(request)))
                result = future.get(timeout=0)
                self.respond_success(envelope, request, result)
            except Exception as e:
                log.exception(e)
                self.respond_error(envelope, request, e)
            finally:
                self._futures.pop(work_id)

        self._loop.add_callback(finish_up)

    def start(self):
        self._loop.start()
