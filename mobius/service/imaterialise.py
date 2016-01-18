#!/usr/bin/env python3

import io
import json
import logging
import multiprocessing as mp
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor

from sqlalchemy.orm.exc import MultipleResultsFound
from zmq.eventloop import IOLoop

from mobius.comm import msg_pb2
from mobius.comm.stream import SocketFactory
from mobius.db import db
from mobius.db import ProviderID
from mobius.service import (
    BaseService,
    MobiusCommand,
    Parameter,
    ProviderFactory,
    ServiceError,
    UploadResponse,
    make_param_string)
from mobius.utils import set_up_logging, JSONObject


log = logging.getLogger(__name__)


PRICE_URL = "https://imatsandbox.materialise.net/web-api/pricing/model"
UPLOAD_URL = "https://imatsandbox.materialise.net/web-api/tool/{tool_id}/model"
TOOL_ID = "d192ffb1-c4d1-4c3a-b25f-71cfd1bb2c17"

NUM_WORKERS = 5
username = "vagrant"
authentication = "tmp"
dbname = "mydb"
host = "localhost"


MATERIALISE_PARAM_MAP = {
    Parameter.ID.name: "uuid",
    Parameter.QUANTITY.name: "quantity",
    Parameter.SCALE.name: "scale",
    Parameter.UNIT.name: "unit",
    Parameter.CURRENCY.name: "currency",
    Parameter.MATERIAL.name: "productname"}


class QuoteCommand(MobiusCommand):
    '''
    Issue a request to i.materialise service to get the price of the provided model.
    '''
    def __init__(self, envelope, mobius_id, http_params):
        '''
        Initialize QuoteService instance.

        @param params - json encoded string containing the parameters for this
                        command
        '''
        self._envelope = envelope
        self._mobius_id = mobius_id
        self._http_params = http_params
        self._db_url = "postgresql://{usr}:{pswd}@{host}/{db}".format(usr=username,
                                                                      pswd=authentication,
                                                                      host=host,
                                                                      db=dbname)
        self._db = None

    @property
    def envelope(self):
        return self._envelope

    def initialize(self):
        '''
        Create a connection to the database within the new process space.
        '''
        self._db = db.DBHandle(self._db_url)

    def run(self):
        '''
        Request the price from sculpteo based on the sculpteo id.
        Sculpteo price API parameters:

        uuid: UUID of the design on which to get printing price
        quantity: number of copies (default ‘1’)
        scale: scale of the design (default ‘1.0’)
        unit: unit of the design (‘mm’, ‘cm’, ‘m’, ‘in’, ‘ft’, ‘yd’, default ‘cm’)
        currency: currency in which price is returned (ISO-4217: ‘EUR’, ‘USD’,
                  ‘GBP’ are supported, defaults to currency from geolocalized IP of the
                  request)
        productname: printing material (see product list below, default
                     ‘white_plastic’ or ‘color_plastic’ if design has colors or textures)

        Sculpteo returns their result in the following format:
            {
               "error" : {
                  "id" : 0,
                  "description" : "no error"
               },
               "body" : {
                  "scale" : 1,
                  "material" : "white_plastic",
                  "price" : {
                     "profit_raw" : "0.00",
                     "total_cost_raw" : "6.19",
                     "unit_price" : "$6.19",
                     "unit_price_without_discount" : "$6.19",
                     "unit_price_without_discount_raw" : "6.19",
                     "total_cost" : "$6.19",
                     "has_tax" : false,
                     "unit_price_raw" : "6.19",
                     "unit_price_round" : "$6",
                     "discount" : 0,
                     "total_cost_without_discount_raw" : "6.19",
                     "total_cost_without_discount" : "$6.19"
                  },
                  "success" : true,
                  "currency" : "USD",
                  "delivery" : {
                     "receipt_timer" : "15 hours and 54 minutes",
                     "shipped_delta" : 1,
                     "receipt_date" : "2015-10-12"
                  },
                  "volume" : 3.26209375
               }
            }

        @returns json response from Sculpteo
        '''
        provider_info = self._get_sculpteo_info()
        self._http_params[Parameter.ID.name] = provider_info.remote_id
        param_string = make_param_string(SCULPTEO_PARAM_MAP, self._http_params)
        url_request = DESIGN_PRICE_URL + "?" + param_string

        log.debug("Quote request: {0}".format(url_request))
        response = requests.get(url=url_request).json()
        error = response['error']

        if error['id']:
            raise ServiceError(error['description'])

        body = response['body']
        price = body['price']

        result = JSONObject()
        result.total_cost = price['total_cost_raw']
        result.currency = body['currency']
        result.has_tax = price['has_tax']
        result.scale = body['scale']
        result.material = body['material']
        return result.json_string

    def _get_sculpteo_info(self):
        '''
        Retrieve the sculpteo id associated with the provided mobius id.

        @returns ProviderInfo
        '''
        with self._db.session_scope() as session:
            try:
                return session.query(db.ProviderInfo)\
                                     .filter_by(mobius_id=self._mobius_id,
                                                provider_id=ProviderID.SCULPTEO.value)\
                                     .one()
            except MultipleResultsFound:
                log.exception()
                log.error("Unique constraint violated with mobius id: {0}"
                          .format(self._mobius_id))
                raise ServiceError("More than one file was found for mobius id: {0}"
                                   .format(self._mobius_id))


class UploadCommand(MobiusCommand):
    '''
    Retrieves the file data from the database associated with the provided
    mobius file id then uploads this file to i.materialise.
    '''
    def __init__(self, envelope, mobius_id, user_id):
        '''
        @param envelope - address of the command initiator
        @param params - json encoded string containing the parameters for this
                        command
            @param mobius_id - database id of the file to be uploaded to Sculpteo
            @param user_id - id of the user owning the file
        '''
        self._envelope = envelope
        self._mobius_id = mobius_id
        self._user_id = user_id
        self._db = None
        self._db_url = "postgresql://{usr}:{pswd}@{host}/{db}".format(usr=username,
                                                                      pswd=authentication,
                                                                      host=host,
                                                                      db=dbname)

    @property
    def envelope(self):
        return self._envelope

    def initialize(self):
        '''
        Create a connection to the database within the new process space.
        '''
        super().initialize("i.materialise")
        self._db = db.DBHandle(self._db_url)

    def _get_provider_info(self, mob_file):
        '''
        Fetch i.materialise provider info object.

        @param mob_file - database handle to the file contents
        @returns Sculpteo provider info if it exists, None otherwise
        '''
        for pi in mob_file.provider_info:
            if pi.mobius_id == self._mobius_id:
                return pi
        return None

    def _report_progress(self, monitor):
        '''
        This is a callback to MultipartEncoderMonitor to monitor the progress of a file upload.

        @param monitor - MultipartEncoderMonitor observing the file upload process
        '''
        try:
            progress = int(100 * monitor.bytes_read / monitor.encoder.len)
            response = json.dumps({"progress": progress})
            progress_msg = msg_pb2.WorkerState(state_id=msg_pb2.UPLOADING, response=response)
    #        log.info("Uploading: {}".format(str(progress_msg)))
            self.send_async_data(progress_msg)
        except Exception as e:
            log.exception("Bad stuff when reporting progress: {}".format(e))

    def _upload_file(self, mob_file):
        '''
        Upload the mobius file to Sculpteo.

        @param mob_file - database handle to the file contents
        @return json response from Sculpteo:

            uuid:   unique identifier of the design
            name:   name of the design
            scale:  default scale of the design
            unit:   default unit of the design
            dimx:   dimension of the axis-aligned bounding box along the X dimension in model units
            dimy:   dimension of the axis-aligned bounding box along the Y dimension in model units
            dimz:   dimension of the axis-aligned bounding box along the Z dimension in model units
        '''
        try:
            file_handle = io.BytesIO(mob_file.data)

            headers = {"X-Requested-With": "XMLHttpRequest"}
            params = {"name": mob_file.name,
                      "designer": "bobik",
                      "password": "password",
                      "share": "0",
                      "print_authorization": "0",
                      "file": ("mobius_file.stl", file_handle, "application/octet-stream")}
            me = MultipartEncoder(fields=params)
            mem = MultipartEncoderMonitor(me, callback=self._report_progress)
            headers['Content-Type'] = mem.content_type
            response = requests.post(url=UPLOAD_URL, data=mem, headers=headers, verify=False)

            return response.json()
        except Exception as e:
            log.info("Bad stuff when uploading.")
            log.exception(e)
            return json.dumps("{}")

    def _save_provider_info(self, provider_json):
        '''
        Save the provider info to the database. Future quote look ups will use
        that information to query for prices.

        @param provider_json - json response from the provider after uploading
                               the file
        '''
        with self._db.session_scope() as session:
            prov_info = db.ProviderInfo(provider_id=db.ProviderID.SCULPTEO.value,
                                        mobius_id=self._mobius_id,
                                        remote_id=provider_json['uuid'])
            session.add(prov_info)
            session.commit()

    def run(self):
        '''
        Upload the file associated with the provided mobius id to Sculpteo.
        '''
        mob_file = self._get_mobius_file()

        sculpteo_pi = self._get_provider_info(mob_file)
        if sculpteo_pi is not None:
            log.debug("File for mobid {0} has already been uploaded.".format(self._mobius_id))
            upload_response = UploadResponse(sculpteo_pi.remote_id, mob_file.name)
        else:
            log.debug("Uploading mobid {0} file to Sculpteo...".format(self._mobius_id))
            # TODO save this json to DB
            response_json = self._upload_file(mob_file)
            if "error" in response_json:
                raise ServiceError(response_json['error'])

            self._save_provider_info(response_json)
            upload_response = UploadResponse(response_json['uuid'], mob_file.name)

        return json.dumps(vars(upload_response))

    def _get_mobius_file(self):
        '''
        Finds the file in the database and returns File handle to it.

        @returns db.File
        '''
        with self._db.session_scope() as session:
            try:
                return session.query(db.File).filter_by(id=self._mobius_id,
                                                        user_id=self._user_id).one()
            except MultipleResultsFound:
                log.exception()
                log.error("Unique constraint violated with mobius id: {0}"
                          .format(self._mobius_id))
                raise ServiceError("More than one file was found for mobius id: {0}"
                                   .format(self._mobius_id))


class SculpteoFactory(ProviderFactory):
    '''
    Sculpteo command factory that creates Sculpteo specific commands.
    '''
    def make_upload_command(self, envelope, request, context=None):
        params = JSONObject(request.params)
        return UploadCommand(envelope, params.mobius_id, params.user_id)
    make_upload_command.__doc__ = ProviderFactory.make_upload_command.__doc__

    def make_quote_command(self, envelope, request, context=None):
        params = JSONObject(request.params)
        return QuoteCommand(envelope, params.mobius_id, params.http_params)
    make_quote_command.__doc__ = ProviderFactory.make_quote_command.__doc__


class IMaterialise(BaseService):
    '''
    This service implements the details of communicating with the i.materialise.com.
    '''
    def __init__(self, executor, loop):
        '''
        Initialize instance of i.materialise service
        '''
        self._work_sub = SocketFactory.sub_socket("/request/do_work",
                                                  on_recv=self.process_request,
                                                  loop=loop)
        self._work_result = SocketFactory.pub_socket("/request/result",
                                                     bind=False,
                                                     loop=loop)
        self._factory = SculpteoFactory()
        super(IMaterialise, self).__init__(executor, loop)

    @property
    def receive_stream(self):
        return self._work_sub

    @property
    def response_stream(self):
        return self._work_result

    def handle_worker_state(self, envelope, msgs):
        msg = msgs[-1]
        response = msg_pb2.Response(service_name=self.name,
                                    state=msg)
        self.response_stream.reply(envelope, response)
    handle_worker_state.__doc__ = BaseService.handle_worker_state.__doc__

    def get_service_context(self):
        return None

    @property
    def name(self):
        return "i.materialise"

    @property
    def cmd_factory(self):
        return self._factory


def main():
    try:
        set_up_logging()
        loop = IOLoop.instance()
        with mp.Pool(NUM_WORKERS) as executor:
            service = IMaterialise(executor, loop)
            log.info("i.materialise service started.")
            service.start()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to system interrupt...")


if __name__ == "__main__":
    main()
