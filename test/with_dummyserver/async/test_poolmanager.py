import io
import pytest
from ahip import PoolManager, Retry
from ahip.exceptions import UnrewindableBodyError

from test.with_dummyserver import conftest


class TestPoolManager:
    @conftest.test_all_backends
    async def test_redirect(self, http_server, backend, anyio_backend):
        base_url = "http://{}:{}".format(http_server.host, http_server.port)
        with PoolManager(backend=backend) as http:
            r = await http.request(
                "GET",
                "%s/redirect" % base_url,
                fields={"target": "%s/" % base_url},
                redirect=False,
            )
            assert r.status == 303

            r = await http.request(
                "GET", "%s/redirect" % base_url, fields={"target": "%s/" % base_url}
            )

            assert r.status == 200
            assert r.data == b"Dummy server!"


class TestFileUploads:
    @conftest.test_all_backends
    async def test_redirect_put_file(self, http_server, backend, anyio_backend):
        """PUT with file object should work with a redirection response"""
        base_url = "http://{}:{}".format(http_server.host, http_server.port)
        retry = Retry(total=3, status_forcelist=[418])
        # httplib reads in 8k chunks; use a larger content length
        content_length = 65535
        data = b"A" * content_length
        uploaded_file = io.BytesIO(data)
        headers = {
            "test-name": "test_redirect_put_file",
            "Content-Length": str(content_length),
        }
        url = "%s/redirect?target=/echo&status=307" % base_url

        with PoolManager(backend=backend) as http:
            resp = await http.urlopen(
                "PUT", url, headers=headers, retries=retry, body=uploaded_file
            )
            assert resp.status == 200
            assert resp.data == data

    @conftest.test_all_backends
    async def test_retries_put_filehandle(self, http_server, backend, anyio_backend):
        """HTTP PUT retry with a file-like object should not timeout"""
        base_url = "http://{}:{}".format(http_server.host, http_server.port)
        retry = Retry(total=3, status_forcelist=[418])
        # httplib reads in 8k chunks; use a larger content length
        content_length = 65535
        data = b"A" * content_length
        uploaded_file = io.BytesIO(data)
        headers = {
            "test-name": "test_retries_put_filehandle",
            "Content-Length": str(content_length),
        }

        with PoolManager(backend=backend) as http:
            resp = await http.urlopen(
                "PUT",
                "%s/successful_retry" % base_url,
                headers=headers,
                retries=retry,
                body=uploaded_file,
                redirect=False,
            )
            assert resp.status == 200

    @conftest.test_all_backends
    async def test_redirect_with_failed_tell(self, http_server, backend, anyio_backend):
        """Abort request if failed to get a position from tell()"""

        base_url = "http://{}:{}".format(http_server.host, http_server.port)

        class BadTellObject(io.BytesIO):
            def tell(self):
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
    async def test_redirect_with_failed_seek(self, http_server, backend, anyio_backend):
        """Abort request if failed to restore position with seek()"""

        base_url = "http://{}:{}".format(http_server.host, http_server.port)

        class BadSeekObject(io.BytesIO):
            def seek(self, *_):
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
