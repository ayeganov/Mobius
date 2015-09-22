#!/usr/bin/env python3

from concurrent.futures import CancelledError
from concurrent.futures import ProcessPoolExecutor
import json
import logging
import os
import requests
import time

from zmq.eventloop import IOLoop

from mobius.comm.stream import SocketFactory
from mobius.comm.msg_pb2 import Response
from mobius.service import UPLOAD, QUOTE, TEST
from mobius.utils import set_up_logging


log = logging.getLogger(__name__)


DESIGN_PRICE_URL = "http://www.sculpteo.com/en/api/design/3D/price_by_uuid/"
UPLOAD_URL = "https://www.sculpteo.com/en/upload_design/a/3D/"

upload_file = "/tmp/upper_wing_right.stl"

NUM_WORKERS = 20


def _get_quote(model_id):
    '''
    Issue a request to sculpteo service to get the price of the model.

    @param model_id - id of the file in the sculpteo system
    '''
    url_request = "?".join((DESIGN_PRICE_URL, model_id))
    response = requests.get(url=url_request).json()
    return response


def _upload_file(file_id):
    '''
    Retrieves the file data from the database associated with the provided
    file_id then uploads this file to Sculpteo.

    @param file_id - database id of the file to be uploaded to Sculpteo
    '''
    # Establish connection to PostgreSQL and retrieve the file data
    with open(upload_file, "rb") as f:
        headers = {"X-Requested-With": "XMLHttpRequest"}
        files = {"file": (os.path.basename(upload_file), f)}
        params = {"name": "test", "designer": "bobik", "password": "password", "share": 0}
        upload_stat = requests.post(url=UPLOAD_URL, files=files, data=params, headers=headers)
        return json.dumps(upload_stat.json())


def _test(model):
    print("Testing model: {0}".format(model))
    time.sleep(1)
    return "SUCCESS"


WORKERS = {
    QUOTE: _get_quote,
    UPLOAD: _upload_file,
    TEST: _test
}


class ServiceError(Exception):
    '''
    All service errors should use this exception type.
    '''


class Sculpteo:
    '''
    This service accepts a Request message and responds with a Response
    message.
    '''
    NAME = "SCULPTEO"

    def __init__(self, executor, loop):
        '''
        Initialize instance of Sculpteo service
        '''
        self._loop = loop
        self._work_sub = SocketFactory.sub_socket("/request/do_work",
                                                  on_recv=self.process_request,
                                                  loop=loop)
        self._work_result = SocketFactory.pub_socket("/request/result",
                                                     bind=False,
                                                     loop=loop)
        self._executor = executor
        self._futures = {}

    def _respond_error(self, request, error):
        '''
        Respond with error to the given request.

        @param request - request that failed to be processed
        @param error - exception describing the failure
        '''
        log.debug("Responding with error to {0} with {1}".format(request, error))
        json_error = json.dumps({"error": str(error)})

        server_id, request_id, request = request
        response = Response(service_name=Sculpteo.NAME,
                            error=json_error)
        self._work_result.reply([server_id, request_id],
                                response)

    def _respond_success(self, request, result):
        '''
        Return the result of the computation to the requestor.

        @param request - original request message
        @param result - result of the computation
        '''
        log.debug("Responding successfully to {0} with {1}".format(request, result))
        server_id, request_id, request = request
        response = Response(service_name=Sculpteo.NAME,
                            response=result)
        self._work_result.reply([server_id, request_id],
                                response)

    def process_request(self, msgs):
        '''
        Process the new request message.

        @param msgs - a request to do some work
        '''
        request_id, server_id, request = msgs
        try:
            log.debug("Got work request: {0} from server {1} request {2}"
                      .format(request, server_id, request_id))
            worker = WORKERS[request.type]
            future = self._executor.submit(worker, request.model.id)
            self._futures[future] = (request_id, server_id, request)
            future.add_done_callback(self._finish_request)
        except KeyError:
            log.exception()
            self._respond_error(request,
                                ServiceError("Unknown request type: {0}".format(request.type)))
        except Exception as e:
            log.exception(e)
            self._respond_error(request)

    def _finish_request(self, future):
        '''
        After request is procesed return the result to the requestor

        @param future - result of work
        '''
        request = self._futures[future]

        def finish_up():
            try:
                log.debug("Finished work for {0}".format(request))
                result = future.result(timeout=0)
                self._respond_success(request, result)
            except CancelledError as ce:
                log.exception(ce)
                self._respond_error(request, ce)
            except Exception as e:
                log.exception(e)
                self._respond_error(request, e)
            finally:
                self._futures.pop(future)

        self._loop.add_callback(finish_up)

    def start(self):
        self._loop.start()


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
