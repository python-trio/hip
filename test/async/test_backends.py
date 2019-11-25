import trio
from urllib3._backends._loader import normalize_backend


def test_sniff_async():
    async def main():
        backend = normalize_backend(None, async_mode=True)
        assert backend.name == "trio"

    trio.run(main)
