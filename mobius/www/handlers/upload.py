import tempfile

# Mobius
from utils import PostContentHandler


class StreamHandler(PostContentHandler):
    '''
    Upload file request handler. It downloads the file in streaming mode from
    the client, and stores the downloaded files in the provided temporary
    directory.
    '''
    FILE_CONTENT_TYPE = "application/octet-stream"
    CONTENT_KEY = "Content-Type"
    POST_SUCCESS = 201

    def initialize(self, tmp_dir):
        '''
        The initialization method for this request handler.

        @param tmp_dir - directory to store temporary files in.
        '''
        super(StreamHandler, self).initialize()
        self._tmp_file = tempfile.NamedTemporaryFile(dir=tmp_dir, delete=False)
        self._cur_headers = None

    def on_finish(self):
        '''
        Do the clean ups here.
        '''
        self._tmp_file.close()

    def post(self):
        '''
        Overriden post method to respond to the client.
        '''
        self.set_header("Content-Type", "text/plain")
        self.set_status(self.POST_SUCCESS)
        self.write("Good job")
        self.finish()

    def _write_file_data(self, headers, data):
        '''
        Writes the data to the temporary file.

        @param headers - HTTP headers for this file
        @param data - a chunk of file data
        '''
        self._tmp_file.write(data)

    def _process_form_field(self, headers, data):
        '''
        Saves the data entered into the upload form.

        @param headers - HTTP headers for this form field
        @param data - data entered into the field.
        '''

    def receive_data(self, headers, chunk):
        '''
        Receive part of the data being sent by the client.

        @param chunk - portion of the payload data.
        '''
        if self._cur_headers != headers:
            self._cur_headers = headers
            try:
                # Process different content types differently
                if self._cur_headers[self.CONTENT_KEY]['value'] == self.FILE_CONTENT_TYPE:
                    self._write_file_data(self._cur_headers, chunk)
            except KeyError:
                self._process_form_field(self._cur_headers, chunk)
