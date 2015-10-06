import abc
import enum
import json
import logging

from mobius.comm.stream import SocketFactory
from mobius.comm.msg_pb2 import ProviderResponse

log = logging.getLogger(__name__)


class ServiceError(Exception):
    '''
    All service errors should use this exception type.
    '''


class Command(enum.IntEnum):
    '''
    This list all commands that services can understand, and execute.
    '''
    QUOTE = 1
    UPLOAD = 2
    SAVE_FILE = 3


class ICommand(metaclass=abc.ABCMeta):
    """
    This is the interface that all commands must implement to work with mobius
    worker services.
    """
    @abc.abstractmethod
    def __call__(self):
        """
        Execute this command. By the time this method is invoked command must
        contain all the necessary information for the execution to succeed.
        """


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

    def create_command(self, request, context=None):
        '''
        Create a command object based on the provided request message.

        @param request - an instance of Request message defined in msg.proto
        @param context - context containing extra data to be passed to commands
        @returns a concrete instance of ICommand interface
        '''
        try:
            return self.commands[request.command](request, context=context)
        except KeyError:
            raise ServiceError("{0} does not support command {1}"
                               .format(self.__class__.__name__, Command(request.command)))


class ProviderFactory(AbstractFactory):
    '''
    This factory knows how to make commands for 3D providers.
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
        self._work_sub = SocketFactory.sub_socket("/request/do_work",
                                                  on_recv=self.process_request,
                                                  loop=loop)
        self._work_result = SocketFactory.pub_socket("/request/result",
                                                     bind=False,
                                                     loop=loop)
        self._executor = executor
        self._futures = {}

    @abc.abstractproperty
    def name(self):
        '''
        Return the name of this service.
        '''

    def respond_error(self, envelope, request, error):
        log.debug("Responding with error to {0} with {1}".format(request, error))
        json_error = json.dumps({"error": str(error)})

        response = ProviderResponse(service_name=self.name,
                                    error=json_error)
        self._work_result.reply(envelope, response)
    respond_error.__doc__ = IService.respond_error.__doc__

    def respond_success(self, envelope, request, result):
        log.debug("Responding successfully to {0} with {1}".format(request, result))
        response = ProviderResponse(service_name=self.name,
                                    response=result)
        self._work_result.reply(envelope, response)
    respond_success.__doc__ = IService.respond_success.__doc__

    def process_request(self, envelope, msgs):
        request = msgs[-1]
        try:
            log.debug("Got work request: {0} from {1})"
                      .format(request, envelope))
            context = self.get_service_context()
            worker = self.cmd_factory.create_command(request, context)
            future = self._executor.submit(worker)
            self._futures[future] = (envelope, request)
            future.add_done_callback(self._finish_request)
        except Exception as e:
            log.exception(e)
            self.respond_error(envelope, request, e)
    process_request.__doc__ = IService.process_request.__doc__

    def _finish_request(self, future):
        '''
        After request is processed return the result to the requestor

        @param future - result of work
        '''
        envelope, request = self._futures[future]

        def finish_up():
            try:
                log.debug("Finished work for {0}".format(str(request)))
                result = future.result(timeout=0)
                self.respond_success(envelope, request, result)
            except Exception as e:
                log.exception(e)
                self.respond_error(envelope, request, e)
            finally:
                self._futures.pop(future)

        self._loop.add_callback(finish_up)

    def start(self):
        self._loop.start()
