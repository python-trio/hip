import collections
import contextlib
from threading import Thread, Event

import pytest
from tornado import web, ioloop
import trustme

from dummyserver.handlers import TestingApp
from dummyserver.server import DEFAULT_CERTS, run_tornado_app

try:
    import asyncio
except ImportError:
    asyncio = None

ServerConfig = collections.namedtuple("ServerConfig", ["host", "port", "ca_certs"])

test_all_backends = pytest.mark.parametrize(
    "backend",
    [
        pytest.param(
            "trio", id="trio-native", marks=[pytest.mark.anyio(backend="trio")]
        ),
        pytest.param(
            "anyio", id="anyio-trio", marks=[pytest.mark.anyio(backend="trio")]
        ),
        pytest.param(
            "anyio", id="anyio-curio", marks=[pytest.mark.anyio(backend="curio")]
        ),
        pytest.param(
            "anyio", id="anyio-asyncio", marks=[pytest.mark.anyio(backend="asyncio")]
        ),
    ],
)


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
def http_server():
    with run_server_in_thread("http", "localhost", None, DEFAULT_CERTS) as cfg:
        yield cfg


@pytest.fixture
def no_san_server(tmp_path_factory):
    tmpdir = tmp_path_factory.mktemp("certs")
    ca = trustme.CA()
    # only common name, no subject alternative names
    server_cert = ca.issue_cert(common_name=u"localhost")

    ca_cert_path = str(tmpdir / "ca.pem")
    server_cert_path = str(tmpdir / "server.pem")
    server_key_path = str(tmpdir / "server.key")
    ca.cert_pem.write_to_path(ca_cert_path)
    server_cert.private_key_pem.write_to_path(server_key_path)
    server_cert.cert_chain_pems[0].write_to_path(server_cert_path)

    with run_server_in_thread(
        "https",
        "localhost",
        ca_cert_path,
        {"keyfile": server_key_path, "certfile": server_cert_path},
    ) as cfg:
        yield cfg
