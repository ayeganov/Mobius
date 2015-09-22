from mobius.comm import msg_pb2
from mobius.utils import Singleton


STREAM_MAP =\
    {
        "/upload/ready": dict(
            send_type=msg_pb2.UploadFile
        ),
        "/mobius/model": dict(
            send_type=msg_pb2.MobiusModel
        ),
        "/request/local": dict(
            send_type=msg_pb2.Request,
            recv_type=msg_pb2.Response
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
    }


class StreamConfigError(Exception):
    '''
    Errors in stream configuration
    '''


class StreamInfo:
    '''
    This class contains all of the necessary information to create a stream.
    '''
    def __init__(self, name, send_type, recv_type=None):
        '''
        Initializes the instance of StreamInfo.

        @param name - name of this stream
        @param send_type - type of message to be sent over this stream
        @param recv_type - type of message to receive in response.
        '''
        self._name = name
        self._send_type = send_type
        if recv_type is None:
            self._recv_type = send_type
        else:
            self._recv_type = recv_type

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


class StreamMap(metaclass=Singleton):
    '''
    This class contains all information about the available channels.
    '''
    def __init__(self):
        '''
        Initializes the instance of StreamMap.
        '''
        self._stream_infos = {name: self._create_stream_info(name, msg)
                              for name, msg in STREAM_MAP.items()}

    def _create_stream_info(self, chan_name, params):
        '''
        Helper method to turn a config entry into a stream info object.

        @param chan_name - name of the channel
        @param params - types of messages associated with this channel etc
        '''
        stream_info = StreamInfo(chan_name, **params)
        return stream_info

    def get_stream_name(self, chan_name):
        '''
        Look up the stream info associated with the given channel name

        @param chan_name - name of the channel
        @return StreamInfo associated with the given channel name, or None
        '''
        try:
            return self._stream_infos[chan_name]
        except KeyError:
            raise StreamConfigError("Channel '{0}' doesn't exist.".format(chan_name))
