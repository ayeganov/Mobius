#!/usr/bin/env python3

import requests
import json

DESIGN_PRICE_URL = "http://www.sculpteo.com/en/api/design/3D/price_by_uuid/"

UPLOAD_URL = "https://www.sculpteo.com/en/upload_design/a/3D/"
#UPLOAD_URL = "http://httpbin.org/post"

def main():
#    model_id = "uuid=N7SnJwCL"
#    url_request = "?".join((DESIGN_PRICE_URL, model_id))

#    response = requests.get(url=url_request).json()
#    print(response)

    with open("serpent.stl", "rb") as f:
        headers = {"X-Requested-With" : "XMLHttpRequest"}
        files = {"file" : ("serpent.stl", f)}
        params = {"name" : "test", "designer" : "bobik", "password" : "password"}
        upload_stat = requests.post(url=UPLOAD_URL, files=files, data=params, headers=headers)

    print(upload_stat.json())

if __name__ == "__main__":
    main()
