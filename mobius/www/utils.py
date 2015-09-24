#!/usr/bin/env python
"""Post data streamer for tornadoweb 4.0"""
import abc
import re

import tornado.gen
from tornado.web import RequestHandler, stream_request_body


def get_max_request_buffer():
    '''
    This function returns the size of the maximum file that can be uploaded to
    mobius.
    '''
    return (1024 * 1024) * 60


class SizeLimitError(Exception):
    '''
    In case trying to retrieve extremely large values.
    '''


@stream_request_body
class PostContentHandler(RequestHandler, metaclass=abc.ABCMeta):
    '''
    This class is responsible for processing the streaming content of a POST
    file request. It separates headers from actual file contents, and makes
    them available for inspection. The file content will be written in to a
    temporary file located in the given directory.

    Users must provide implementation for the following methods:

        receive_data(headers, data)
    '''
    BOUNDARY_SEARCH_BUF_SIZE = 1000
    SEP = b'\r\n'
    LSEP = len(SEP)
    EOH_SEP = b'\r\n\r\n'
    PAT_HEADERVALUE = re.compile(r"([^:]+):\s+([^\s;]+)(.*)")
    PAT_HEADERPARAMS = re.compile(r";\s*([^=]+)=\"(.*?)\"")
    HEADER_ENCODING = "UTF-8"

    def initialize(self):
        '''
        Initializes an instance of the PostContentHandler.

        @param content_length - length of the whole requst body, including
                                headers.
        @param tmp_dir - temporary directory to contain the file being
                         uploaded.
        '''
        self._boundary = None
        self._receiving_data = False
        self.header_list = []
        self._buffer = b""
        self._count = 0
        self._total = 1

    @tornado.gen.coroutine
    def _extract_boundary(self, cont_buf):
        '''
        Extracts the boundary from the content buffer.

        @param cont_buf - buffered HTTP request
        @returns boundary string and updated buffer
        '''
        try:
            boundary, new_buffer = cont_buf.split(self.SEP, 1)
        except ValueError:
            boundary, new_buffer = (None, cont_buf)
        return (boundary, new_buffer)

    @tornado.gen.coroutine
    def _read_data(self, cont_buf):
        '''
        Read the file data.

        @param cont_buf - buffered HTTP request
        @param boolean indicating whether data is still being read and new
               buffer
        '''
        # Check only last characters of the buffer guaranteed to be large
        # enough to contain the boundary
        end_of_data_idx = cont_buf.find(self._boundary)

        if end_of_data_idx >= 0:
            data = cont_buf[:(end_of_data_idx - self.LSEP)]
            self.receive_data(self.header_list[-1], data)
            new_buffer = cont_buf[(end_of_data_idx + len(self._boundary)):]
            return False, new_buffer
        else:
            self.receive_data(self.header_list[-1], cont_buf)
            return True, b""

    @tornado.gen.coroutine
    def _parse_params(self, param_buf):
        '''
        Parse HTTP header parameters.

        @param param_buf - string buffer containing the parameters.
        @returns parameters dictionary
        '''
        params = dict()
        param_res = self.PAT_HEADERPARAMS.findall(param_buf)
        if param_res:
            for name, value in param_res:
                params[name] = value
        elif param_buf:
            params['value'] = param_buf
        return params

    @tornado.gen.coroutine
    def _parse_header(self, header_buf):
        '''
        Parses a buffer containing an individual header with parameters.

        @param header_buf - header buffer containing a single header
        @returns header dictionary
        '''
        res = self.PAT_HEADERVALUE.match(header_buf)
        header = dict()
        if res:
            name, value, tail = res.groups()
            header = {'name': name, 'value': value,
                      'params': (yield self._parse_params(tail))}
        elif header_buf:
            header = {"value": header_buf}
        return header

    @tornado.gen.coroutine
    def _read_headers(self, cont_buf):
        '''
        Read HTTP headers from content buffer.

        @param cont_buf - buffered HTTP request
        '''
        res_headers = dict()
        try:
            headers, new_buffer = cont_buf.split(self.EOH_SEP, 1)

            header_list = headers.split(self.SEP)
            for header in header_list:
                header_dict = yield self._parse_header(
                    header.decode(self.HEADER_ENCODING))
                if header_dict:
                    try:
                        res_headers[header_dict['name']] = header_dict
                    except KeyError:
                        res_headers.setdefault('unknown', []).append(header_dict)
        except ValueError:
            new_buffer = cont_buf

        return res_headers, new_buffer

    def _is_end_of_request(self, cont_buf):
        '''
        Is this the end of the HTTP request content.

        @param cont_but - buffered HTTP request.
        @returns True if end of request, False otherwise.
        '''
        return cont_buf == (b"--" + self.SEP)

    def _is_end_of_data(self, cont_buf):
        '''
        Is this the end of the end of this chunk data? There is likely more to
        come, but this chunk has been exhausted.

        @param cont_buf - buffered HTTP request.
        @returns True if end of data, False otherwise
        '''
        return cont_buf == b""

    @tornado.gen.coroutine
    def data_received(self, chunk):
        '''
        Processes a chunk of content body.

        @param chunk - a piece of content body.
        '''
        self._count += len(chunk)
        self._buffer += chunk
        # Has boundary been established?
        if not self._boundary:
            self._boundary, self._buffer =\
                (yield self._extract_boundary(self._buffer))

            if (not self._boundary
                    and len(self._buffer) > self.BOUNDARY_SEARCH_BUF_SIZE):
                raise RuntimeError("Cannot find multipart delimiter.")

        while True:
            if self._receiving_data:
                self._receiving_data, self._buffer = yield self._read_data(self._buffer)
                if self._is_end_of_request(self._buffer) or self._is_end_of_data(self._buffer):
                    break
            else:
                headers, self._buffer = yield self._read_headers(self._buffer)
                if headers:
                    self.header_list.append(headers)
                    self._receiving_data = True
                else:
                    break

    def prepare(self):
        '''
        Prepares this request by getting the content length of the upload.
        '''
        self._total = int(self.request.headers['Content-Length'])

    @property
    def progress(self):
        '''
        Provide current progress of the upload in the form of an integer.
        '''
        return (self._count * 100) // self._total

    @abc.abstractmethod
    def receive_data(self):
        '''
        Override this method to write or process data from the request. Form
        submissions apply separate headers to each field. Once the headers
        change you are dealing with the next field.

        @param headers - headers for the given data
        @param data - data to be processed
        '''
