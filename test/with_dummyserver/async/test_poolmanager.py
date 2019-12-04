import pytest

from hip import AsyncPoolManager


@pytest.mark.parametrize(
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
async def test_redirect(dummy_server_url, backend):
    with AsyncPoolManager(backend=backend) as http:
        r = await http.request(
            "GET",
            "%s/redirect" % dummy_server_url,
            fields={"target": "%s/" % dummy_server_url},
            redirect=False,
        )
        assert r.status == 303

        r = await http.request(
            "GET",
            "%s/redirect" % dummy_server_url,
            fields={"target": "%s/" % dummy_server_url},
        )

        assert r.status == 200
        assert await r.read() == b"Dummy server!"
