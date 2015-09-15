import logging

from mobius.comm.stream import SocketFactory


log = logging.getLogger(__name__)

class RequestProxy:
    '''
    This class is responsible for routing traffic from the tornado servers to
    service workers.
    '''
    def __init__(self, loop):
        '''
        Initializes an instance of RequestProxy.

        @param loop - loop to be used by this instance
        '''
        self._loop = loop
        self._server_in = SocketFactory.router_socket(
                          "/request/request",
                          on_recv=self._route_request,
                          loop=loop)

        self._server_out = SocketFactory.pub_socket(
                          "/request/do_work",
                          loop=loop)

        self._service_in = SocketFactory.router_socket(
                           "/request/result",
                           on_recv=self._route_result,
                           loop=loop)

    def _route_request(self, msgs):
        '''
        Route the request to all of the service workers.

        @param msgs - a list requst messages.
        '''
