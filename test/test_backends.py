import pytest

import hip
from hip.backends import Backend
from hip._backends._loader import normalize_backend, load_backend


requires_async_pool_manager = pytest.mark.skipif(
    not hasattr(hip, "AsyncPoolManager"),
    reason="async backends require AsyncPoolManager",
)


class TestNormalizeBackend(object):
    """
    Assert that we fail correctly if we attempt to use an unknown or incompatible backend.
    """

    def test_unknown(self):
        with pytest.raises(ValueError) as excinfo:
            normalize_backend("_unknown", async_mode=False)

        assert "unknown backend specifier _unknown" == str(excinfo.value)

    def test_sync(self):
        assert normalize_backend(Backend("sync"), async_mode=False) == Backend("sync")
        assert normalize_backend("sync", async_mode=False) == Backend("sync")
        assert normalize_backend(None, async_mode=False) == Backend("sync")

        with pytest.raises(ValueError) as excinfo:
            normalize_backend(Backend("anyio"), async_mode=False)
        assert "anyio backend needs to be run in async mode" == str(excinfo.value)

        with pytest.raises(ValueError) as excinfo:
            normalize_backend(Backend("trio"), async_mode=False)
        assert "trio backend needs to be run in async mode" == str(excinfo.value)

    @requires_async_pool_manager
    def test_async(self):
        assert normalize_backend(Backend("anyio"), async_mode=True) == Backend("anyio")
        assert normalize_backend(Backend("trio"), async_mode=True) == Backend("trio")

        with pytest.raises(ValueError) as excinfo:
            normalize_backend(Backend("sync"), async_mode=True)
        assert "sync backend needs to be run in sync mode" == str(excinfo.value)


class TestLoadBackend(object):
    """
    Assert that we can load a normalized backend
    """

    def test_sync(self):
        load_backend(normalize_backend("sync", async_mode=False))
