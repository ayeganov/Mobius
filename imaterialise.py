#!/usr/bin/env python

import base64
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
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

STL_FILE = "L_joint_combinte.STL"
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


def main():
    headers = {'content-type': "application/json", "Accept": "application/json", "APICode": API_CODE}

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
