import collections
import contextlib
from threading import Thread, Event

import pytest
from tornado import web, ioloop

from dummyserver.handlers import TestingApp
from dummyserver.server import NO_SAN_CA, NO_SAN_CERTS, run_tornado_app

try:
    import asyncio
except ImportError:
    asyncio = None

ServerConfig = collections.namedtuple("ServerConfig", ["host", "port", "ca_certs"])


@contextlib.contextmanager
def run_server_in_thread(scheme, host, ca_certs, server_certs):
    def _run_server_in_thread():
        # The event loop MUST be instantiated in the worker thread, or it will interfere
        # with the tests targeting asyncio
        if asyncio:
            asyncio.set_event_loop(asyncio.new_event_loop())

        ctx["io_loop"] = ioloop.IOLoop.current()
        ctx["server"], ctx["port"] = run_tornado_app(
            app, ctx["io_loop"], server_certs, scheme, host
        )
        ready_event.set()
        ctx["io_loop"].start()

    ctx = {"io_loop": None, "server": None, "port": None}
    app = web.Application([(r".*", TestingApp)])
    ready_event = Event()
    server_thread = Thread(target=_run_server_in_thread)
    server_thread.start()
    ready_event.wait(5)

    yield ServerConfig(host, ctx["port"], ca_certs)

    ctx["io_loop"].add_callback(ctx["server"].stop)
    ctx["io_loop"].add_callback(ctx["io_loop"].stop)
    server_thread.join()


@pytest.fixture
def no_san_server():
    with run_server_in_thread("https", "localhost", NO_SAN_CA, NO_SAN_CERTS) as cfg:
        yield cfg
