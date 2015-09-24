import abc
import enum
import json
import logging

from mobius.comm.stream import SocketFactory
from mobius.comm.msg_pb2 import Response

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


class CommandFactory:
    '''
    Factory for creating command objects.

    Takes in a Request message, and based on its type creates an appropriate
    Command object.
    '''
    def __init__(self, service_name):
        '''
        Initialize instance of CommandFactory.

        @param service_name - name of the service using this instance of factory
        '''
        self._service_name = service_name

        self._commands = {
            Command.QUOTE: self.make_quote_command,
            Command.UPLOAD: self.make_upload_command
        }

    def create_command(self, request):
        '''
        Create a command object based on the provided request message.

        @param request - an instance of Request message defined in msg.proto
        @returns a concrete instance of ICommand interface
        '''
        try:
            return self._commands[request.command](request)
        except KeyError:
            raise ServiceError("{0} does not support command {1}"
                               .format(self._service_name, str(request.command)))

    @abc.abstractmethod
    def make_upload_command(self, request):
        '''
        Create an instance of the upload command

        @param request - an instance of Request message defined in msg.proto
        '''

    @abc.abstractmethod
    def make_quote_command(self, request):
        '''
        Create an instance of the quote command

        @param request - an instance of Request message defined in msg.proto
        '''


class BaseService:
    '''
    This service accepts a Request message and responds with a Response
    message. Extenders must define a self.cmd_factory property, which must
    return a concrete instance of CommandFactory. Extender must implement their
    own version of CommandFactory.
    '''

    def __init__(self, executor, loop):
        '''
        Initialize instance of Sculpteo service

        @param executor - an instance of ProcessPoolExecutor, or ThreadPoolExecutor
        @param loop - zme eventloop
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

    @abc.abstractproperty
    def cmd_factory(self):
        '''
        Return the factory which knows how to create commands for this service.
        '''

    def _respond_error(self, request, error):
        '''
        Respond with error to the given request.

        @param request - request that failed to be processed
        @param error - exception describing the failure
        '''
        log.debug("Responding with error to {0} with {1}".format(request, error))
        json_error = json.dumps({"error": str(error)})

        server_id, request_id, request = request
        response = Response(service_name=self.name,
                            error=json_error)
        self._work_result.reply([server_id, request_id],
                                response)

    def _respond_success(self, request, result):
        '''
        Return the result of the computation to the requestor.

        @param request - original request message
        @param result - result of the computation
        '''
        log.debug("Responding successfully to {0} with {1}".format(request, result))
        server_id, request_id, request = request
        response = Response(service_name=self.name,
                            response=result)
        self._work_result.reply([server_id, request_id],
                                response)

    def process_request(self, msgs):
        '''
        Process the new request message.

        @param msgs - a request to do some work
        '''
        request_id, server_id, request = msgs
        try:
            log.debug("Got work request: {0} from server {1} request {2}"
                      .format(request, server_id, request_id))
            worker = self.cmd_factory.create_command(request)
            future = self._executor.submit(worker)
            self._futures[future] = (request_id, server_id, request)
            future.add_done_callback(self._finish_request)
        except Exception as e:
            log.exception(e)
            self._respond_error(request, e)

    def _finish_request(self, future):
        '''
        After request is processed return the result to the requestor

        @param future - result of work
        '''
        request = self._futures[future]

        def finish_up():
            try:
                log.debug("Finished work for {0}".format(str(request)))
                result = future.result(timeout=0)
                self._respond_success(request, result)
            except Exception as e:
                log.exception(e)
                self._respond_error(request, e)
            finally:
                self._futures.pop(future)

        self._loop.add_callback(finish_up)

    def start(self):
        self._loop.start()
