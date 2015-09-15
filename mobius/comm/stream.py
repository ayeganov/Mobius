import logging
import os

import zmq
from zmq.eventloop.zmqstream import ZMQStream

from mobius.comm import comm_config
from mobius.utils import get_zmq_dir

log = logging.getLogger(__name__)

IPC = "ipc"
INPROC = "inproc"
TCP = "tcp"
PGM = "pgm"
EPGM = "epgm"


class StreamError(Exception):
    '''
    Class representing stream errors.
    '''


class ZmqAddress:
    '''
    Represents a ZMQ address path - abstracts away the transports being used in
    socket creation.
    '''
    def __init__(self, transport=IPC, host=None, chan_name=None, port=None):
        '''
        @param transport - one of "IPC", "INPROC", "TCP"
        @param host - ip address, or hostname of server to connect to
        @param chan_name - socket namepath to be used with "IPC" and "INPROC"
                       (eg:/tmp/bla)
        @param port - int port value. To be used with "TCP"
        '''
        self._transport = transport.lower()
        self._host = host
        self._chan_name = chan_name
        self._port = port

        self._is_ipc = self._transport in (IPC, INPROC)
        self._is_tcp = self._transport == TCP
        self._is_pgm = self._transport in (PGM, EPGM)

        if self._is_pgm:
            raise StreamError("Pragmatic general multicast not supported.")

        if self._is_ipc and chan_name is None:
            raise StreamError("'%s' transport requires a chan_name." % self._transport)

        if self._is_tcp and (port is None or host is None):
            raise StreamError("'%s' transport requires a port and a host." % self._transport)

        if not (self._is_ipc | self._is_tcp | self._is_pgm):
            raise StreamError("Incorrect transport specified: '%s'" % transport)

    def zmq_url(self):
        '''
        String representation of the end point.
        '''
        if self._is_ipc:
            name = self._chan_name.lstrip('/').replace('/', '_')
            full_name = os.path.join(get_zmq_dir(), name)
            return "{0}://{1}".format(self._transport, full_name)
        if self._is_tcp:
            return "{0}://{1}:{2}".format(self._transport, self._host, self._port)


class Stream:
    '''
    This is the main class that interacts with the zmq library to send, and
    receive messages.
    '''
    def __init__(self, socket, stream_info, path, on_recv=None, on_send=None, loop=None):
        '''
        Initializes instance of Stream.

        @param socket - zmq socket that has alredy been bound
        @param stream_info - this streams definition from the yaml config
        @param path - path to the socket on the disk
        @param loop - loop this socket will belong to. Default is global async loop.
        '''
        self._path = path
        self._stream_info = stream_info
        self._on_recv = on_recv
        self._on_send = on_send

        self._stream = ZMQStream(socket, io_loop=loop)

        if self._on_recv is not None:
            self._stream.on_recv(self._recv_wrapper)
        if self._on_send is not None:
            self._stream.on_send(self._send_wrapper)

    def on_send(self, callback):
        '''
        Set the callback to be invoked on every send command. on_send(None)
        disables this callback.

        @param callback - Callback must take exactly two arguments, which will
                          be the message being sent (always a list), and the
                          return result of socket.send_multipart(msg) -
                          MessageTracker or None.
        '''
        self._on_send = callback
        if callback is None:
            self._stream.on_send(None)
        else:
            self._stream.on_send(self._send_wrapper)

    def on_recv(self, callback):
        '''
        Register a callback for when a message is ready to recv. There can be
        only one callback registered at a time, so each call to on_recv
        replaces previously registered callbacks.  on_recv(None) disables recv
        event polling.

        @param callback - callback must take exactly one argument, which will
                          be a list, as returned by socket.recv_multipart()
                          if callback is None, recv callbacks are disabled.
        '''
        self._on_recv = callback
        if callback is None:
            self._stream.on_recv(None)
        else:
            self._stream.on_recv(self._recv_wrapper)

    def flush(self, flag=3, limit=None):
        '''
        Flush pending messages.

        This method safely handles all pending incoming and/or outgoing
        messages, bypassing the inner loop, passing them to the registered
        callbacks.

        A limit can be specified, to prevent blocking under high load.

        flush will return the first time ANY of these conditions are met:
        No more events matching the flag are pending.
        the total number of events handled reaches the limit.

        @param flag - 0MQ poll flags. If flag|POLLIN, recv events will be
                      flushed. If flag|POLLOUT, send events will be flushed.
                      Both flags can be set at once, which is the default.
        @param limit - None, or int. Optional. The maximum number of messages
                       to send or receive. Both send and receive count against
                       this limit
        @returns int - count of events handled
        '''
        return self._stream.flush(flag, limit)

    def send(self, msg, **kwds):
        '''
        Send the given message on this stream. The message type must match that
        specified in the streams config, or a ValueError will be raised.

        @param msg - Google protocol buffer msg to send over this stream
        @param kwds - extra keywords that zmq's stream send accepts.
        '''
        if not isinstance(msg, self._stream_info.send_type):
            raise ValueError("Wrong message type being sent. {0} is not {1}"
                             .format(type(msg), type(self._stream_info.send_type)))

        data = msg.SerializeToString()
        self._stream.send(data, **kwds)

    @staticmethod
    def _callback_wrapper(data, msg_type, callback):
        '''
        Helper method to parse serialized messages that are being sent and
        received for the respective callbacks.

        @param msg_type - type of message to parse
        @param callback - method to invoke
        '''
        msgs = []
        for d in data:
            msg = msg_type()
            try:
                msg.ParseFromString(d)
            except:
                # We are dealing with the envelope frames, simply add them to
                # the message list
                msg = d
            msgs.append(msg)

        if msgs:
            callback(msgs)

    def _recv_wrapper(self, data):
        self._callback_wrapper(data, self._stream_info.recv_type, self._on_recv)

    def _send_wrapper(self, data, _):
        self._callback_wrapper(data, self._stream_info.send_type, self._on_send)

    def close(self):
        '''
        Close this stream.
        '''
        self._stream.close()


class SocketFactory:
    '''
    Convenience class for creating different types of zmq sockets.
    '''

    @staticmethod
    def _make_stream(socket,
                     chan_name,
                     on_recv=None,
                     on_send=None,
                     host=None,
                     transport=IPC,
                     port=None,
                     bind=True,
                     loop=None):
        '''
        Helper method to create streams.
        '''
        zmq_address = ZmqAddress(transport=transport, host=host, chan_name=chan_name, port=port)

        if bind:
            socket.bind(zmq_address.zmq_url())
        else:
            socket.connect(zmq_address.zmq_url())

        stream_info = comm_config.StreamMap().get_stream_name(chan_name)

        stream = Stream(socket,
                        stream_info,
                        zmq_address.zmq_url(),
                        on_recv=on_recv,
                        on_send=on_send,
                        loop=loop)
        return stream

    @staticmethod
    def pub_socket(chan_name, on_send=None, host=None, transport=IPC, port=None, bind=True, loop=None):
        '''
        Create a publish socket on the specified chan_name.

        @param chan_name - chan_name of this socket
        @param on_send - callback when messages are sent on this socket.
                         It will be called as `on_send([msg1,...,msgN])`
                         Status is either a positive value indicating
                         number of bytes sent, or -1 indicating an error.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param port - port number to connect to
        @param bind - should this socket bind, or connect
        @param loop - loop this socket will belong to.
        @returns Stream
        '''
        context = zmq.Context.instance()
        socket = context.socket(zmq.PUB)
        return SocketFactory._make_stream(socket, chan_name, on_recv, on_send, host, transport, port, bind, loop)

    @staticmethod
    def sub_socket(chan_name, on_recv=None, host=None, transport=IPC, port=None, bind=False, loop=None):
        '''
        Create a subscriber socket on the specified chan_name.

        @param chan_name - chan_name of this socket
        @param on_recv - callback when messages are received on this socket.
                         It will be called as `on_recv([msg1,...,msgN])`
                         If set to None - no data will be read from this socket.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param port - port number to connect to
        @param bind - should this socket bind, or connect
        @param loop - loop this socket will belong to.
        @returns Stream
        '''
        context = zmq.Context.instance()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b'')

        return SocketFactory._make_stream(socket, chan_name, on_recv, on_send, host, transport, port, bind, loop)

    @staticmethod
    def req_socket(chan_name, on_send=None, on_recv=None, host=None, transport=IPC, port=None, bind=False, loop=None):
        '''
        Create a request socket on the specified chan_name.

        @param chan_name - chan_name of this socket
        @param on_send - callback when messages are sent on this socket.
                         It will be called as `on_send([msg1,...,msgN])`
                         Status is either a positive value indicating
                         number of bytes sent, or -1 indicating an error.
        @param on_recv - callback when messages are received on this socket.
                         It will be called as `on_recv([msg1,...,msgN])`
                         If set to None - no data will be read from this socket.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param port - port number to connect to
        @param bind - should this socket bind, or connect
        @param loop - loop this socket will belong to. Default is global async loop.
        @returns Stream
        '''
        context = zmq.Context.instance()
        socket = context.socket(zmq.REQ)

        return SocketFactory._make_stream(socket, chan_name, on_recv, on_send, host, transport, port, bind, loop)

    @staticmethod
    def rep_socket(chan_name, on_send=None, on_recv=None, host=None, transport=IPC, port=None, bind=True, loop=None):
        '''
        Create a reply socket on the specified chan_name.

        @param chan_name - chan_name of this socket
        @param on_send - callback when messages are sent on this socket.
                         It will be called as `on_send([msg1,...,msgN])`
                         Status is either a positive value indicating
                         number of bytes sent, or -1 indicating an error.
        @param on_recv - callback when messages are received on this socket.
                         It will be called as `on_recv([msg1,...,msgN])`
                         If set to None - no data will be read from this socket.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param port - port number to connect to
        @param bind - should this socket bind, or connect
        @param loop - loop this socket will belong to. Default is global async loop.
        @returns Stream
        '''
        context = zmq.Context.instance()
        socket = context.socket(zmq.REP)

        return SocketFactory._make_stream(socket, chan_name, on_recv, on_send, host, transport, port, bind, loop)

    @staticmethod
    def router_socket(chan_name, on_send=None, on_recv=None, host=None, transport=IPC, port=None, bind=True, loop=None):
        '''
        Create a router socket on the specified chan_name.

        @param chan_name - chan_name of this socket
        @param on_send - callback when messages are sent on this socket.
                         It will be called as `on_send([msg1,...,msgN])`
                         Status is either a positive value indicating
                         number of bytes sent, or -1 indicating an error.
        @param on_recv - callback when messages are received on this socket.
                         It will be called as `on_recv([msg1,...,msgN])`
                         If set to None - no data will be read from this socket.
                         The first message will always be the ID of the sender.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param port - port number to connect to
        @param bind - should this socket bind, or connect
        @param loop - loop this socket will belong to. Default is global async loop.
        @returns Stream
        '''
        context = zmq.Context.instance()
        socket = context.socket(zmq.ROUTER)

        return SocketFactory._make_stream(socket, chan_name, on_recv, on_send, host, transport, port, bind, loop)

    @staticmethod
    def dealer_socket(chan_name, on_send=None, on_recv=None, host=None, transport=IPC, port=None, bind=True, loop=None):
        '''
        Create a dealer socket on the specified chan_name.

        @param chan_name - chan_name of this socket
        @param on_send - callback when messages are sent on this socket.
                         It will be called as `on_send([msg1,...,msgN])`
                         Status is either a positive value indicating
                         number of bytes sent, or -1 indicating an error.
        @param on_recv - callback when messages are received on this socket.
                         It will be called as `on_recv([msg1,...,msgN])`
                         If set to None - no data will be read from this socket.
        @param host - hostname, or ip address on which this socket will communicate
        @param transport - what kind of transport to use for messaging(inproc, ipc, tcp etc)
        @param port - port number to connect to
        @param bind - should this socket bind, or connect
        @param loop - loop this socket will belong to. Default is global async loop.
        @returns Stream
        '''
        context = zmq.Context.instance()
        socket = context.socket(zmq.DEALER)

        return SocketFactory._make_stream(socket, chan_name, on_recv, on_send, host, transport, port, bind, loop)
