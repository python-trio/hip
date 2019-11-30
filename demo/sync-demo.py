# This should work on all versions of Python 2 and 3

from __future__ import print_function

import hip

URL = "http://httpbin.org/uuid"

print("--- hip using synchronous sockets ---")
with hip.PoolManager() as http:
    print("URL:", URL)
    r = http.request("GET", URL, preload_content=False)
    print("Status:", r.status)
    print("Data: {!r}".format(r.data))
