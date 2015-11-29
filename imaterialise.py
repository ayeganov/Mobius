#!/usr/bin/env python

import io
import base64
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
import logging

#import http.client
#http.client.HTTPConnection.debuglevel = 1
#logging.basicConfig() # you need to initialize logging, otherwise you will not see anything from requests
#logging.getLogger().setLevel(logging.DEBUG)
#requests_log = logging.getLogger("requests.packages.urllib3")
#requests_log.setLevel(logging.DEBUG)
#requests_log.propagate = True


PRICE_URL = "https://imatsandbox.materialise.net/web-api/pricing/model"
UPLOAD_URL = "https://imatsandbox.materialise.net/web-api/tool/{tool_id}/model"

API_CODE = "c37a867e-1f80-4873-8049-8b1b33b4a171"
TOOL_ID = "3694d823-dfbc-4542-a609-04abb7234635"

STL_FILE = "/tmp/3dobject.bin"
#STL_FILE = "tiny.stl"


price_message = {
   "models":[
      {
         "modelID":"147C7A82-56C1-4547-8262-D2C869BD355E",
         "materialID":"035f4772-da8a-400b-8be4-2dd344b28ddb",
         "finishID":"bba2bebb-8895-4049-aeb0-ab651cee2597",
         "quantity":"1",
         "scale":"1.0"
      }
   ],
   "shipmentInfo":
    {
        "countryCode": "BE",
        "stateCode": "",
        "city": "Leuven",
        "zipCode":  "3001"
    },
    "currency":"USD"
}

import time

class ProgressBytesIO(io.BytesIO):
    '''
    This class is used for tracking the progress of the file being read when
    uploading it to a service provider.
    '''
    def __init__(self, data, progress_cb=None):
        '''
        Initialize instance of ProgressBytesIO.

        @param data - byte array of data to be streamed as bytes objects.
        @param progress_cb - callback to be invoked whenever a read occurs. Its signature:
                             progress_cb(num_chars_read, total_buffer_size)
        '''
        super().__init__(data)
        self._progress_cb = progress_cb
        self._total_size = len(data)
        self._progress = 0

    def read(self, size=None):
        '''
        Override of the read method in BytesIO to count the bytes read.

        @param size - number of bytes requested to be read.
        '''
        chars_read = super().read(size)
        self._progress += len(chars_read)

        if self._progress_cb is not None and callable(self._progress_cb):
            try:
                self._progress_cb(self._progress, self._total_size)
            except Exception as e:
                print(e)
                raise

        return chars_read

before_100 = time.time()
after_100 = None
def progress(monitor):
    global before_100, after_100
    so_far = int(100 * monitor.bytes_read / monitor.encoder.len)
    if so_far == 100 and after_100 is None:
        after_100 = time.time()
        print("Getting to 100% took {} seconds".format(time.time() - before_100))
    print("Bytes read: {}%".format(so_far))


UPLOAD_URL = "https://www.sculpteo.com/en/upload_design/a/3D/"
def sculpteo_upload():
    with open(STL_FILE, "rb") as stl_file:
        headers = {"X-Requested-With": "XMLHttpRequest"}
        params = {"name": "test_file",
                  "designer": "bobik",
                  "password": "password",
                  "share": "0",
                  "print_authorization": "0",
                  "file": ("mobius_file.stl", stl_file)}
        me = MultipartEncoder(fields=params)
        m = MultipartEncoderMonitor(me, callback=progress)
        print("Content type: {}, length: {}".format(m.content_type, me.len))
        headers['Content-Type'] = m.content_type
        response = requests.post(url=UPLOAD_URL, data=m, headers=headers)
        print("Bullshit time is {} seconds".format(time.time() - after_100))
        print(response.text)


def prog_cb(current, total):
    print("Progress: {}".format(100 * current / total))

def sculpteo_upload_orig():
    start = time.time()
    with open(STL_FILE, "rb") as stl_file:
        prog_file = ProgressBytesIO(stl_file.read(), prog_cb)
        headers = {"X-Requested-With": "XMLHttpRequest"}
        files = {"file": ("mobius_file.stl", prog_file)}
        params = {"name": "bullshit_name",
                  "designer": "bobik",
                  "password": "password",
                  "share": 0,
                  "print_authorization": 0}
        response = requests.post(url=UPLOAD_URL, files=files, data=params, headers=headers, stream=True)
        print(response.text)
    print("Upload took {} seconds.".format(time.time() - start))


def main():
    sculpteo_upload()


def main2():
    headers =\
        {'content-type': "application/json", "Accept": "application/json", "APICode": API_CODE}

#    r = requests.post(PRICE_URL, data=price_message, headers=headers)
#    if r.status_code == 200:
#        print("Price check succeeded.")

    mobius_upload_url = UPLOAD_URL.format(tool_id=TOOL_ID)
    with open(STL_FILE, "rb") as f:
        encoder = MultipartEncoder({"file": (STL_FILE, f, 'application/octet-stream'),
                                    "fileUnits": "mm"})
        headers = {"Content-Type": encoder.content_type}
        r = requests.post(mobius_upload_url, data=encoder, headers=headers)

    if r.status_code == 200:
        print("Upload succeeded.")
        print(r.text)
    else:
        print(r.text)


if __name__ == "__main__":
    main()
