import unittest

from mobius.comm import builder
from mobius.comm import stream


class TestBuilder(unittest.TestCase):
    '''
    Test the builder of the channel map.
    '''
    def test_build_stream_map(self):
        stream_infos = builder.create_stream_map()
        si = stream_infos.popitem()[1]
        self.assertIsInstance(si, stream.StreamInfo)

    def test_create_stream_info(self):
        name = "hello"
        msg_types = dict(send_type=str, resp_type=int)
        self.assertIsNotNone(builder.create_stream_info(name, msg_types))

        del msg_types['resp_type']
        self.assertIsInstance(builder.create_stream_info(name, msg_types), stream.StreamInfo)

        with self.assertRaises(TypeError):
            builder.create_stream_info(name)


if __name__ == "__main__":
    unittest.main()
