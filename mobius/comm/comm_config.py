import re

from mobius.comm import msg_pb2
from mobius.utils import Singleton


STREAM_MAP =\
    {
        "/db/request": dict(
            send_type=msg_pb2.Request,
            reply_type=msg_pb2.Response
        ),
        "/mobius/upload_progress": dict(
            send_type=msg_pb2.UInt32,
            reply_type=msg_pb2.UInt32
        ),
        "/request/local": dict(
            send_type=msg_pb2.Request,
            reply_type=msg_pb2.Response
        ),
        "/request/request": dict(
            send_type=msg_pb2.Request,
        ),
        "/request/do_work": dict(
            send_type=msg_pb2.Request,
        ),
        "/request/result": dict(
            send_type=msg_pb2.Response,
        ),
        "dynamic": {
            "/worker/state/(.+)": dict(
                send_type=msg_pb2.WorkerState,
            )
        }
    }


class StreamConfigError(Exception):
    '''
    Errors in stream configuration
    '''


class StreamInfo:
    '''
    This class contains all of the necessary information to create a stream.
    '''
    def __init__(self, name, send_type, recv_type=None, reply_type=None):
        '''
        Initializes the instance of StreamInfo.

        @param name - name of this stream
        @param send_type - type of message to be sent over this stream
        @param recv_type - type of message to receive, if the channel will be
                           used for listening only. (Subscriber case)
        @param reply_type - type of message to receive in reply.
        '''
        self._name = name
        self._send_type = send_type
        self._recv_type = send_type if (recv_type is None) else recv_type
        self._reply_type = send_type if (reply_type is None) else reply_type

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
    def recv_type(self):
        '''
        Message type that can be received in response over this stream.
        '''
        return self._recv_type

    @property
    def reply_type(self):
        '''
        Message type that can be received when waiting for a response over this
        stream.
        '''
        return self._reply_type


class StreamMap(metaclass=Singleton):
    '''
    This class contains all information about the available channels.
    '''
    def __init__(self):
        '''
        Initializes the instance of StreamMap.
        '''
        self._stream_infos = {name: self._create_stream_info(name, msg)
                              for name, msg in STREAM_MAP.items()
                              if name != "dynamic"}
        dynamic = STREAM_MAP["dynamic"]
        dynamic = {re.compile(name): params for name, params in dynamic.items()}
        STREAM_MAP["dynamic"] = dynamic

    def _create_stream_info(self, chan_name, params):
        '''
        Helper method to turn a config entry into a stream info object.

        @param chan_name - name of the channel
        @param params - types of messages associated with this channel etc
        '''
        stream_info = StreamInfo(chan_name, **params)
        return stream_info

    def _get_dynamic_info(self, chan_name):
        '''
        Look up a dynamic info stream.

        @param chan_name - name of the channel
        @return StreamInfo associated with the given channel name, or raises an
                exception
        '''
        dynamics = STREAM_MAP["dynamic"]
        for name, params in dynamics.items():
            match = name.match(chan_name)
            if match is not None:
                return self._create_stream_info(chan_name, params)
        raise ValueError("Channel '{}' doesn't exist.".format(chan_name))

    def get_stream_info(self, chan_name):
        '''
        Look up the stream info associated with the given channel name

        @param chan_name - name of the channel
        @return StreamInfo associated with the given channel name, or raises an
                exception
        '''
        try:
            return self._stream_infos.get(chan_name, None) or self._get_dynamic_info(chan_name)
        except ValueError:
            raise StreamConfigError("Channel '{0}' doesn't exist.".format(chan_name))
