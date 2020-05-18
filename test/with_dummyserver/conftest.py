import pytest

test_all_backends = pytest.mark.parametrize(
    "backend, anyio_backend",
    [
        pytest.param("trio", "trio", id="trio-native"),
        pytest.param("anyio", "trio", id="anyio-trio"),
        pytest.param("anyio", "curio", id="anyio-curio"),
        pytest.param("anyio", "asyncio", id="anyio-asyncio"),
    ],
)


test_sync_backend = pytest.mark.parametrize("backend, anyio_backend", [("sync", None)])
