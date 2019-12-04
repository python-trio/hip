from threading import Thread, Event

import pytest
from tornado import web, ioloop

from dummyserver.handlers import TestingApp
from dummyserver.server import DEFAULT_CERTS, run_tornado_app

try:
    import asyncio
except ImportError:
    asyncio = None


@pytest.fixture
def dummy_server_url():
    def run_server_in_thread():
        nonlocal io_loop, server, port

        # The event loop MUST be instantiated in the worker thread, or it will interfere with the
        # tests targeting asyncio
        if asyncio:
            asyncio.set_event_loop(asyncio.new_event_loop())

        io_loop = ioloop.IOLoop.current()
        server, port = run_tornado_app(app, io_loop, DEFAULT_CERTS, scheme, host)
        ready_event.set()
        io_loop.start()

    scheme = "http"
    host = "localhost"
    app = web.Application([(r".*", TestingApp)])
    io_loop = server = port = None
    ready_event = Event()
    server_thread = Thread(target=run_server_in_thread)
    server_thread.start()
    ready_event.wait(5)
    yield "{}://{}:{}".format(scheme, host, port)

    io_loop.add_callback(server.stop)
    io_loop.add_callback(io_loop.stop)
    server_thread.join()
