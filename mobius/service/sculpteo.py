#!/usr/bin/env python3

from concurrent.futures import ProcessPoolExecutor
import json
import logging
import requests

from zmq.eventloop import IOLoop

from mobius.service import ICommand, ProviderFactory, BaseService
from mobius.utils import set_up_logging


log = logging.getLogger(__name__)


DESIGN_PRICE_URL = "http://www.sculpteo.com/en/api/design/3D/price_by_uuid/"
UPLOAD_URL = "https://www.sculpteo.com/en/upload_design/a/3D/"

NUM_WORKERS = 5


class QuoteCommand(ICommand):
    '''
    Issue a request to sculpteo service to get the price of the provided model.
    '''
    def __init__(self, model_id):
        '''
        Initialize QuoteService instance.

        @param model_id - mobius id of the file to quote
        '''
#        self._model_id = model_id
        self._model_id = "N7SnJwCL"
        # TODO: Make connection to the database
        self._db = None

    def __call__(self):
        sculpteo_id = self._get_sculpteo_id()
        url_request = "?".join((DESIGN_PRICE_URL, sculpteo_id))
        response = requests.get(url=url_request).json()
        return json.dumps(response)
    __call__.__doc__ == ICommand.__call__.__doc__

    def _get_sculpteo_id(self):
        '''
        Retrieve the sculpteo id associated with the provided mobius id.

        @returns str
            sculpteo id
        '''
        return "uuid={0}".format(self._model_id)


class UploadCommand(ICommand):
    '''
    Retrieves the file data from the database associated with the provided
    mobius file id then uploads this file to Sculpteo.
    '''
    def __init__(self, mobius_id):
        '''
        @param mobius_id - database id of the file to be uploaded to Sculpteo
        '''
        self._mobius_id = mobius_id
        # TODO: Make connection to the database
        self._db = None

    def __call__(self):
        headers = {"X-Requested-With": "XMLHttpRequest"}
        file_handle = self._get_file_handle()
        files = {"file": ("mobius_file", file_handle)}
        params = {"name": "test", "designer": "bobik", "password": "password", "share": 0}
        upload_stat = requests.post(url=UPLOAD_URL, files=files, data=params, headers=headers)
        return json.dumps(upload_stat.json())
    __call__.__doc__ == ICommand.__call__.__doc__

    def _get_file_handle(self):
        '''
        Reads the file data from the database and returns a file handle to it.

        @returns binary file handle
        '''
        return self._db.fetch_file(self._mobius_id)


class SculpteoFactory(ProviderFactory):
    '''
    Sculpteo command factory that creates Sculpteo specific commands.
    '''
    def make_upload_command(self, request, context=None):
        return UploadCommand(request.model.id)
    make_upload_command.__doc__ = ProviderFactory.make_upload_command.__doc__

    def make_quote_command(self, request, context=None):
        return QuoteCommand(request.model.id)
    make_quote_command.__doc__ = ProviderFactory.make_quote_command.__doc__


class Sculpteo(BaseService):
    '''
    This service implements the details of communicating with the Sculpteo.com.
    '''
    def __init__(self, executor, loop):
        '''
        Initialize instance of Sculpteo service
        '''
        super(Sculpteo, self).__init__(executor, loop)
        self._name = "Sculpteo"
        self._factory = SculpteoFactory()

    @property
    def name(self):
        return self._name

    @property
    def cmd_factory(self):
        return self._factory


def main():
    try:
        set_up_logging()
        loop = IOLoop.instance()
        with ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
            service = Sculpteo(executor, loop)
            log.info("Sculpteo service started.")
            service.start()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to system interrupt...")


if __name__ == "__main__":
    main()
