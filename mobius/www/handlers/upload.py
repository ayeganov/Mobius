import tempfile

# Mobius
from mobius.www.utils import PostContentHandler
from mobius.comm.msg_pb2 import UploadFile


class StreamHandler(PostContentHandler):
    '''
    Upload file request handler. It downloads the file in streaming mode from
    the client, and stores the downloaded files in the provided temporary
    directory.
    '''
    DISPOSITION = "Content-Disposition"
    FILE_FIELD = "fileID"
    POST_SUCCESS = 201

    def initialize(self, tmp_dir, upload_pub):
        '''
        The initialization method for this request handler.

        @param tmp_dir - directory to store temporary files in.
        '''
        super(StreamHandler, self).initialize()
        self._tmp_file = tempfile.NamedTemporaryFile(dir=tmp_dir, delete=False)
        self._upload_pub = upload_pub
        self._cur_headers = None
        self._file_started = False

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

    def _get_field_name(self, headers):
        '''
        Retrieve the name of the field from the given headers.

        @param headers - HTTP headers
        @returns name of the field specified on the page
        '''
        try:
            return headers[self.DISPOSITION]["params"]["name"]
        except KeyError:
            return None

    def receive_data(self, headers, chunk):
        '''
        Receive part of the data being sent by the client.

        @param chunk - portion of the payload data.
        '''
        if self._cur_headers != headers:
            self._cur_headers = headers
            if self._file_started:
                # Changing header, and file has already been started - file was downloaded
                self._upload_pub.send(UploadFile(path=self._tmp_file.name))
            self._file_started = self._get_field_name(self._cur_headers) == self.FILE_FIELD
        try:
            # Process different content types differently
            if self._file_started:
                self._write_file_data(self._cur_headers, chunk)
        except KeyError:
            self._process_form_field(self._cur_headers, chunk)
