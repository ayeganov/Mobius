from collections import defaultdict
import mock
import unittest

import tornado.gen
import tornado.web

from mobius.www.utils import PostContentHandler
from mobius.utils import test


DISPOSITION = "Content-Disposition"


class TestContentHandler(PostContentHandler):

    def __init__(self, test_case):
        self.app = tornado.web.Application()
        self.test_case = test_case
        super(TestContentHandler, self).__init__(self.app, mock.Mock())

    def receive_data(self, headers, data):
        field_name = headers[DISPOSITION]["params"]["name"]
        self.test_case.content[field_name] += data

        if headers not in self.test_case.headers:
            self.test_case.headers.append(headers)

    @tornado.gen.coroutine
    def request_done(self):
        self.test_case.request_done = True


class TestPostContentHandler(test.TornadoTestCase):
    def setUp(self):
        super(TestPostContentHandler, self).setUp()
        self.content = defaultdict(bytes)
        self.headers = []
        self.content_handler = TestContentHandler(self)
        self.request_done = False
        self.test_binary = b'''------test_boundary\r\nContent-Disposition: form-data; name="fileID"; filename="test.stl"\r\nContent-Type: application/octet-stream\r\n\r\ntest content\r\n------test_boundary\r\nContent-Disposition: form-data; name="fileName"\r\n\r\ntest file\r\n------test_boundary--\r\n'''

    def test_content_and_headers(self):
        '''
        Verify the content is delivered correctly.
        '''

        function = lambda: self.content_handler.data_received(self.test_binary)
        self.run_sync(function)
        self.assertEqual(self.content['fileID'], b'test content')
        self.assertEqual(self.content['fileName'], b'test file')
        self.assertTrue(self.request_done)

        self.assertEqual(2, len(self.headers))
        first_header = self.headers[0]
        cont_disp = first_header[DISPOSITION]
        self.assertEqual('form-data', cont_disp['value'])
        self.assertEqual(DISPOSITION, cont_disp['name'])
        params = cont_disp['params']
        self.assertEqual('test.stl', params['filename'])
        self.assertEqual('fileID', params['name'])


if __name__ == "__main__":
    unittest.main()
