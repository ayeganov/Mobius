#!/usr/bin/env python3

import os
import requests
import uuid

from mobius.comm.stream import SocketFactory

DESIGN_PRICE_URL = "http://www.sculpteo.com/en/api/design/3D/price_by_uuid/"
UPLOAD_URL = "https://www.sculpteo.com/en/upload_design/a/3D/"

upload_file = "/tmp/full_wind_thing.STL"


class Sculpteo:
    '''
    This service accepts a Mobius Model message and responds with a Quote
    message.
    '''
    def __init__(self):
        '''
        Initialize instance of Sculpteo
        '''
        self._mob_id_sub = SocketFactory.sub_socket("/mobius/model/", on_recv=self._recv_model)

    def _recv_model(self, msgs):
        '''
        Handle the new model message.

        @param msgs - a list of mobius model messages.
        '''


def main():
#    model_id = "uuid=N7SnJwCL"
#    url_request = "?".join((DESIGN_PRICE_URL, model_id))

#    response = requests.get(url=url_request).json()
#    print(response)

    progress_id = uuid.uuid4()
    print("Progress id: {0}".format(progress_id))
    with open(upload_file, "rb") as f:
        headers = {"X-Requested-With": "XMLHttpRequest", "X-Progress-ID": str(progress_id)}
        files = {"file": (os.path.basename(upload_file), f)}
        params = {"name": "test", "designer": "bobik", "password": "password", "share": 0}
        upload_stat = requests.post(url=UPLOAD_URL, files=files, data=params, headers=headers)

    print(upload_stat.json())


if __name__ == "__main__":
    main()
