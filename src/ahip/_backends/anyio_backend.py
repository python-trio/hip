from ssl import SSLContext

import anyio

from ._common import is_readable, LoopAbort
from .async_backend import AsyncBackend, AsyncSocket

BUFSIZE = 65536


# XX support connect_timeout and read_timeout


class AnyIOBackend(AsyncBackend):
    async def connect(
        self, host, port, connect_timeout, source_address=None, socket_options=None
    ):
        bind_host, bind_port = source_address or (None, None)
        stream = await anyio.connect_tcp(
            host, port, bind_host=bind_host, bind_port=bind_port
        )
        for (level, optname, value) in socket_options:
            stream.setsockopt(level, optname, value)

        return AnyIOSocket(stream)


# XX it turns out that we don't need SSLStream to be robustified against
# cancellation, but we probably should do something to detect when the stream
# has been broken by cancellation (e.g. a timeout) and make is_readable return
# True so the connection won't be reused.


class AnyIOSocket(AsyncSocket):
    def __init__(self, stream: anyio.SocketStream):
        self._stream = stream

    async def start_tls(self, server_hostname, ssl_context: SSLContext):
        await self._stream.start_tls(
            ssl_context, suppress_ragged_eofs=True, server_hostname=server_hostname
        )
        return self

    def getpeercert(self, binary_form=False):
        return self._stream.getpeercert(binary_form=binary_form)

    async def receive_some(self, read_timeout):
        return await self._stream.receive_some(BUFSIZE)

    async def send_and_receive_for_a_while(
        self, produce_bytes, consume_bytes, read_timeout
    ):
        async def sender():
            while True:
                outgoing = await produce_bytes()
                if outgoing is None:
                    break
                await self._stream.send_all(outgoing)

        async def receiver():
            while True:
                incoming = await self._stream.receive_some(BUFSIZE)
                consume_bytes(incoming)

        try:
            async with anyio.create_task_group() as tg:
                await tg.spawn(sender)
                await tg.spawn(receiver)
        except LoopAbort:
            pass

    # We want this to be synchronous, and don't care about graceful teardown
    # of the SSL/TLS layer.
    def forceful_close(self):
        self._stream._socket._raw_socket.close()

    def is_readable(self):
        return is_readable(self._stream._socket._raw_socket)

    def set_readable_watch_state(self, enabled):
        pass
