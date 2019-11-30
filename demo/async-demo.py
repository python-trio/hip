# This should work on python 3.6+

import hip
from hip.backends import Backend

URL = "http://httpbin.org/uuid"

async def main(backend=None):
    with hip.AsyncPoolManager(backend=backend) as http:
        print("URL:", URL)
        r = await http.request("GET", URL, preload_content=False)
        print("Status:", r.status)
        print("Data:", await r.read())

print("--- hip using Trio ---")
import trio
trio.run(main)

print("\n--- hip using asyncio (via AnyIO) ---")
import asyncio
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
loop.close()

print("\n--- hip using curio (via AnyIO) ---")
import curio
curio.run(main)

print("\n--- hip using Twisted ---")
from twisted.internet.task import react
from twisted.internet.defer import ensureDeferred
def twisted_main(reactor):
    return ensureDeferred(main(Backend("twisted", reactor=reactor)))
react(twisted_main)
