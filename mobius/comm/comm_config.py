import os

import yaml

from mobius.comm import stream

CHANNEL_MAP = os.path.join(os.path.dirname(__file__), "channel_map.yaml")


def create_stream_info(chan_name, msg_types):
    stream_info = stream.StreamInfo(chan_name, **msg_types)
    return stream_info


def create_stream_map():
    try:
        with open(CHANNEL_MAP, "r") as f:
            file_contents = f.read()

        channels = yaml.load(file_contents)

        streams = {chan: create_stream_info(chan, msg) for chan, msg in channels.items()}
        return streams
    except Exception as e:
        print(e)
        return None
