import io
import pytest
import trio
import anyio
from ahip import PoolManager
from ahip.exceptions import UnrewindableBodyError

from test.with_dummyserver import conftest


class TestFileUploads:
    @conftest.test_all_backends
    async def test_upload_anyio_async_files(self, http_server, backend, anyio_backend):
        """Uploading a file opened via 'anyio.aopen()' should be possible"""
        base_url = "http://{}:{}".format(http_server.host, http_server.port)

        with open(__file__, mode="rb") as f:
            data = f.read()
            content_length = len(data)

        headers = {
            "Content-Length": str(content_length),
        }
        url = "%s/echo" % base_url

        with PoolManager(backend=backend) as http:
            async with await anyio.aopen(__file__, mode="rb") as f:
                resp = await http.urlopen("PUT", url, headers=headers, body=f)
                assert resp.status == 200
                assert resp.data == data

    @pytest.mark.trio
    async def test_upload_trio_wrapped_files(self, http_server):
        """Uploading a file wrapped via 'trio.wrap_file()' should be possible"""
        base_url = "http://{}:{}".format(http_server.host, http_server.port)

        with open(__file__, mode="rb") as f:
            data = f.read()
            content_length = len(data)

        headers = {
            "Content-Length": str(content_length),
        }
        url = "%s/echo" % base_url

        with PoolManager(backend="trio") as http:
            with open(__file__, mode="rb") as f:
                f = trio.wrap_file(f)
                resp = await http.urlopen("PUT", url, headers=headers, body=f)
                assert resp.status == 200
                assert resp.data == data

    @conftest.test_all_backends
    async def test_redirect_with_failed_async_tell(
        self, http_server, backend, anyio_backend
    ):
        """Abort request if failed to get a position from async tell()"""

        base_url = "http://{}:{}".format(http_server.host, http_server.port)

        class BadTellObject(io.BytesIO):
            async def tell(self):
                raise IOError

        body = BadTellObject(b"the data")
        url = "%s/redirect?target=/successful_retry" % base_url
        # httplib uses fileno if Content-Length isn't supplied,
        # which is unsupported by BytesIO.
        headers = {"Content-Length": "8"}

        with PoolManager() as http:
            with pytest.raises(UnrewindableBodyError) as e:
                await http.urlopen("PUT", url, headers=headers, body=body)
            assert "Unable to record file position for" in str(e.value)

    @conftest.test_all_backends
    async def test_redirect_with_failed_async_seek(
        self, http_server, backend, anyio_backend
    ):
        """Abort request if failed to restore position with async seek()"""

        base_url = "http://{}:{}".format(http_server.host, http_server.port)

        class BadSeekObject(io.BytesIO):
            async def seek(self, *_):
                raise IOError

        body = BadSeekObject(b"the data")
        url = "%s/redirect?target=/successful_retry" % base_url
        # httplib uses fileno if Content-Length isn't supplied,
        # which is unsupported by BytesIO.
        headers = {"Content-Length": "8"}

        with PoolManager() as http:
            with pytest.raises(UnrewindableBodyError) as e:
                await http.urlopen("PUT", url, headers=headers, body=body)
            assert (
                "An error occurred when rewinding request body for redirect/retry."
                == str(e.value)
            )
