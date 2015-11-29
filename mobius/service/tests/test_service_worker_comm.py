import mock
import multiprocessing as mp
import unittest

from zmq import eventloop
from zmq.eventloop.ioloop import IOLoop

from mobius.comm import msg_pb2
from mobius.service import (
    BaseService,
    MobiusCommand,
    ProviderFactory,)


eventloop.ioloop.install()


class TestUpload(MobiusCommand):
    '''
    Simulates upload and communicates progress to TestService.
    '''
    def __init__(self, envelope, size):
        '''
        @param size - size of data to "upload"
        '''
        self._envelope = envelope
        self._size = size

    @property
    def envelope(self):
        return self._envelope

    def initialize(self):
        '''
        Create a connection to the database within the new process space.
        '''
        super().initialize("TestService")

    def run(self):
        '''
        Perform the "upload" and report progress back.
        '''
        msgs = (msg_pb2.WorkerState(progress=v) for v in range(1, self._size))
        for msg in msgs:
            self.send_async_data(msg)
        return "Hello"


class TestFactory(ProviderFactory):
    '''
    Test command factory that creates Test specific commands.
    '''
    def make_upload_command(self, envelope, request, context=None):
        return TestUpload(envelope, request.size)
    make_upload_command.__doc__ = ProviderFactory.make_upload_command.__doc__

    def make_quote_command(self, envelope, request, context=None):
        return None
    make_quote_command.__doc__ = ProviderFactory.make_quote_command.__doc__


class TestService(BaseService):
    def __init__(self, executor, loop):
        '''
        Initialize instance of TestService
        '''
        self._mock_stream = mock.Mock()
        self._factory = TestFactory()
        super().__init__(executor, loop)

    def handle_worker_state(self, _, msgs):
        msg = msgs[-1]
        if msg.progress == 100:
            self._loop.stop()

    handle_worker_state.__doc__ = BaseService.handle_worker_state.__doc__

    def get_service_context(self):
        return None

    @property
    def response_stream(self):
        return self._mock_stream

    @property
    def receive_stream(self):
        return self._mock_stream

    @property
    def name(self):
        return "TestService"

    @property
    def cmd_factory(self):
        return self._factory


class Request:
    size = 101
    command = 2


class ProcessToServiceCommunication(unittest.TestCase):
    '''
    Verify the mobius process is able to communicate with service process.
    '''
    def test_service_communication(self):
        loop = IOLoop.instance()
        executor = mp.Pool(1)
        ts = TestService(executor, loop)

        failure = False

        def test_failed():
            nonlocal failure
            loop.stop()
            failure = True

        loop.add_callback(lambda: ts.process_request(b'1', [Request()]))
        loop.call_later(2, test_failed)
        loop.start()
        self.assertFalse(failure)
        executor.close()
        executor.terminate()


if __name__ == "__main__":
    unittest.main()
