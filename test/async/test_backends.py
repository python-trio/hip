import asyncio
import curio
import trio

from hip._backends._loader import normalize_backend


def test_sniff_backends():
    async def _test_sniff_async(expected_name):
        backend = normalize_backend(None, async_mode=True)
        assert backend.name == expected_name

    trio.run(_test_sniff_async, "trio")
    curio.run(_test_sniff_async, "anyio")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_test_sniff_async("anyio"))
