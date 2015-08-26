import zmq

from mobius.comm import builder
from mobius.utils import Singleton


class StreamError(Exception):
    '''
    Class representing stream errors.
    '''


class StreamInfo:
    '''
    This class contains all of the necessary information to create a stream.
    '''
    def __init__(self, name, send_type, resp_type=None):
        '''
        Initializes the instance of StreamInfo.

        @param name - name of this stream
        @param send_type - type of message to be sent over this stream
        @param resp_type - type of message to receive in response.
        '''
        self._name = name
        self._send_type = send_type
        self._resp_type = resp_type

    @property
    def name(self):
        '''
        Return name of this stream
        '''
        return self._name

    @property
    def send_type(self):
        '''
        Message type that can be sent over this stream.
        '''
        return self._send_type

    @property
    def resp_type(self):
        '''
        Message type that can be received in response over this stream.
        '''
        return self._resp_type


class StreamMap(metaclass=Singleton):
    '''
    This class contains all information about the available channels.
    '''
    def __init__(self):
        '''
        Initializes the instance of StreamMap.
        '''
        self._stream_infos = builder.create_stream_map()

    def get_channel_info(self, chan_name):
        '''
        Look up the stream info associated with the given channel name

        @param chan_name - name of the channel
        @return StreamInfo associated with the given channel name, or None
        '''
        return self._stream_infos.get(chan_name, None)


class ZmqAddress:
    '''
    Represents a ZMQ address path - abstracts away the transports being used in
    socket creation.
    '''
    def __init__(self, transport="ipc", host=None, topic=None, port=None):
        '''
        @param transport - one of "IPC", "INPROC", "TCP"
        @param host - ip address, or hostname of server to connect to
        @param topic - socket namepath to be used with "IPC" and "INPROC"
                       (eg:/tmp/bla)
        @param port - int port value. To be used with "TCP"
        '''
        self._transport = transport.lower()
        self._host = host
        self._topic = topic
        self._port = port

        self._is_ipc = self._transport in ("ipc", "inproc")
        self._is_tcp = self._transport == "tcp"
        self._is_pgm = self._transport in ("pgm", "epgm")

        if self._is_pgm:
            raise Stream("Pragmatic general multicast not supported.")

        if self._is_ipc and topic is None:
            raise StreamError("'%s' transport requires a topic." % self._transport)

        if self._is_tcp and (port is None or host is None):
            raise StreamError("'%s' transport requires a port and a host." % self._transport)

        if not (self._is_ipc | self._is_tcp | self._is_pgm):
            raise StreamError("Incorrect transport specified: '%s'" % transport)

    def __repr__(self):
        '''
        String representation of the end point.
        '''
        if self._is_ipc:
            name = self._topic.lstrip('/').replace('/', '_')
            return "{0}://{1}".format(self._transport, name)
        if self._is_tcp:
            return "{0}://{1}:{2}".format(self._transport, self._host, self._port)

    @property
    def address_string(self):
        '''
        Returns full zmq socket address string.
        '''
        return repr(self)


class Stream:
    '''
    This is the main class that interacts with the zmq library to send, and
    receive messages.
    '''
    def __init__(self, name, path, send_type, resp_type=None):
        '''
        Initializes instance of Stream.

        @param name - name of this channel
        @param path - path to the socket on the disk
        @param send_type - type of message that can be sent over this stream
        @param resp_type - optional type of message expected in response to
                           sent message.(useful when dealing with REQ/REP
                           socket types.)
        '''


class SocketFactory:
    '''
    Convenience class for creating different types of zmq sockets.
    '''
    @staticmethod
    def pub_socket(topic=None, on_send=None, host=None, transport="ipc", port=None, loop=None):
        '''
        Create a publish socket on the specified topic.

        @param topic - topic of this socket
        @param on_send - callback when messages are sent on this socket.
                         It will be called as `on_send([msg1,...,msgN])`
                         Status is either a positive value indicating
                         number of bytes sent, or -1 indicating an error.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param loop - loop this socket will belong to. Default is global async loop.
        @param port - port number to connect to
        @returns AIOZMQSocket
        '''
        # TODO: Once topics have a clear definition do a lookup of the socket
        # path against definition table
        context = zmq.Context.instance()
        socket = context.socket(zmq.PUB)
        zmq_address = ZmqAddress(transport=transport, host=host, topic=topic, port=port)

        print(zmq_address)
        socket.bind(zmq_address.address_string)

        async_sock = AIOZMQSocket(socket, loop=loop)
        async_sock.on_send(on_send)

        return async_sock

    @staticmethod
    def sub_socket(topic=None, on_recv=None, host=None, transport="ipc", port=None, loop=None):
        '''
        Create a subscriber socket on the specified topic.

        @param topic - topic of this socket
        @param on_recv - callback when messages are received on this socket.
                         It will be called as `on_recv([msg1,...,msgN])`
                         If set to None - no data will be read from this socket.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param loop - loop this socket will belong to. Default is global async loop.
        @param port - port number to connect to
        @returns AIOZMQSocket
        '''
        # TODO: Once topics have a clear definition do a lookup of the socket
        # path against definition table
        context = zmq.Context.instance()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b'')

        zmq_address = ZmqAddress(transport=transport, host=host, topic=topic, port=port)
        socket.connect(zmq_address.address_string)

        print(zmq_address)
        async_sock = AIOZMQSocket(socket, loop=loop)
        async_sock.on_recv(on_recv)

        return async_sock

    @staticmethod
    def req_socket(topic=None, on_send=None, on_recv=None, host=None, transport="ipc", port=None, loop=None):
        '''
        Create a subscriber socket on the specified topic.

        @param topic - topic of this socket
        @param on_send - callback when messages are sent on this socket.
                         It will be called as `on_send([msg1,...,msgN])`
                         Status is either a positive value indicating
                         number of bytes sent, or -1 indicating an error.
        @param on_recv - callback when messages are received on this socket.
                         It will be called as `on_recv([msg1,...,msgN])`
                         If set to None - no data will be read from this socket.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param loop - loop this socket will belong to. Default is global async loop.
        @param port - port number to connect to
        @returns AIOZMQSocket
        '''
        # TODO: Once topics have a clear definition do a lookup of the socket
        # path against definition table
        context = zmq.Context.instance()
        socket = context.socket(zmq.REQ)

        zmq_address = ZmqAddress(transport=transport, host=host, topic=topic, port=port)
        socket.connect(zmq_address.address_string)

        async_sock = AIOZMQSocket(socket, loop=loop)
        async_sock.on_send(on_send)
        async_sock.on_recv(on_recv)

        return async_sock

    @staticmethod
    def rep_socket(topic=None, on_send=None, on_recv=None, host=None, transport="ipc", port=None, loop=None):
        '''
        Create a subscriber socket on the specified topic.

        @param topic - topic of this socket
        @param on_send - callback when messages are sent on this socket.
                         It will be called as `on_send([msg1,...,msgN])`
                         Status is either a positive value indicating
                         number of bytes sent, or -1 indicating an error.
        @param on_recv - callback when messages are received on this socket.
                         It will be called as `on_recv([msg1,...,msgN])`
                         If set to None - no data will be read from this socket.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param loop - loop this socket will belong to. Default is global async loop.
        @param port - port number to connect to
        @returns AIOZMQSocket
        '''
        # TODO: Once topics have a clear definition do a lookup of the socket
        # path against definition table
        context = zmq.Context.instance()
        socket = context.socket(zmq.REP)

        zmq_address = ZmqAddress(transport=transport, host=host, topic=topic, port=port)
        socket.bind(zmq_address.address_string)

        async_sock = AIOZMQSocket(socket, loop=loop)
        async_sock.on_send(on_send)
        async_sock.on_recv(on_recv)

        return async_sock
