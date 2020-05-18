import io
import json
import pytest
from ahip import PoolManager, Retry
from ahip.exceptions import MaxRetryError, UnrewindableBodyError

from test.with_dummyserver import conftest
from dummyserver.testcase import HTTPDummyServerTestCase

from test import LONG_TIMEOUT


class TestPoolManager(HTTPDummyServerTestCase):
    @classmethod
    def setup_class(cls):
        super(TestPoolManager, cls).setup_class()
        cls.base_url = "http://%s:%d" % (cls.host, cls.port)
        cls.base_url_alt = "http://%s:%d" % (cls.host_alt, cls.port)

    @conftest.test_all_backends
    async def test_redirect(self, backend, anyio_backend):
        with PoolManager(backend=backend) as http:
            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/" % self.base_url},
                redirect=False,
            )
            assert r.status == 303

            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/" % self.base_url},
            )

            assert r.status == 200
            assert r.data == b"Dummy server!"

    @conftest.test_all_backends
    async def test_redirect_twice(self, backend, anyio_backend):
        with PoolManager(backend=backend) as http:
            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/redirect" % self.base_url},
                redirect=False,
            )

            assert r.status == 303

            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={
                    "target": "%s/redirect?target=%s/" % (self.base_url, self.base_url)
                },
            )

            assert r.status == 200
            assert r.data == b"Dummy server!"

    @conftest.test_all_backends
    async def test_redirect_to_relative_url(self, backend, anyio_backend):
        with PoolManager(backend=backend) as http:
            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "/redirect"},
                redirect=False,
            )

            assert r.status == 303

            r = await http.request(
                "GET", "%s/redirect" % self.base_url, fields={"target": "/redirect"}
            )

            assert r.status == 200
            assert r.data == b"Dummy server!"

    @conftest.test_all_backends
    async def test_cross_host_redirect(self, backend, anyio_backend):
        with PoolManager(backend=backend) as http:
            cross_host_location = "%s/echo?a=b" % self.base_url_alt
            with pytest.raises(MaxRetryError):
                await http.request(
                    "GET",
                    "%s/redirect" % self.base_url,
                    fields={"target": cross_host_location},
                    timeout=LONG_TIMEOUT,
                    retries=0,
                )

            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/echo?a=b" % self.base_url_alt},
                timeout=LONG_TIMEOUT,
                retries=1,
            )

            assert r._pool.host == self.host_alt

    @conftest.test_all_backends
    async def test_too_many_redirects(self, backend, anyio_backend):
        with PoolManager(backend=backend) as http:
            with pytest.raises(MaxRetryError):
                await http.request(
                    "GET",
                    "%s/redirect" % self.base_url,
                    fields={
                        "target": "%s/redirect?target=%s/"
                        % (self.base_url, self.base_url)
                    },
                    retries=1,
                )

            with pytest.raises(MaxRetryError):
                await http.request(
                    "GET",
                    "%s/redirect" % self.base_url,
                    fields={
                        "target": "%s/redirect?target=%s/"
                        % (self.base_url, self.base_url)
                    },
                    retries=Retry(total=None, redirect=1),
                )

    @conftest.test_all_backends
    async def test_redirect_cross_host_remove_headers(self, backend, anyio_backend):
        with PoolManager(backend=backend) as http:
            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/headers" % self.base_url_alt},
                headers={"Authorization": "foo"},
            )

            assert r.status == 200

            data = json.loads(r.data.decode("utf-8"))

            assert "Authorization" not in data

            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/headers" % self.base_url_alt},
                headers={"authorization": "foo"},
            )

            assert r.status == 200

            data = json.loads(r.data.decode("utf-8"))

            assert "authorization" not in data
            assert "Authorization" not in data

    @conftest.test_all_backends
    async def test_redirect_cross_host_no_remove_headers(self, backend, anyio_backend):
        with PoolManager(backend=backend) as http:
            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/headers" % self.base_url_alt},
                headers={"Authorization": "foo"},
                retries=Retry(remove_headers_on_redirect=[]),
            )

            assert r.status == 200

            data = json.loads(r.data.decode("utf-8"))

            assert data["Authorization"] == "foo"

    @conftest.test_all_backends
    async def test_redirect_cross_host_set_removed_headers(
        self, backend, anyio_backend
    ):
        with PoolManager(backend=backend) as http:
            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/headers" % self.base_url_alt},
                headers={"X-API-Secret": "foo", "Authorization": "bar"},
                retries=Retry(remove_headers_on_redirect=["X-API-Secret"]),
            )

            assert r.status == 200

            data = json.loads(r.data.decode("utf-8"))

            assert "X-API-Secret" not in data
            assert data["Authorization"] == "bar"

            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/headers" % self.base_url_alt},
                headers={"x-api-secret": "foo", "authorization": "bar"},
                retries=Retry(remove_headers_on_redirect=["X-API-Secret"]),
            )

            assert r.status == 200

            data = json.loads(r.data.decode("utf-8"))

            assert "x-api-secret" not in data
            assert "X-API-Secret" not in data
            assert data["Authorization"] == "bar"

    @conftest.test_all_backends
    async def test_raise_on_redirect(self, backend, anyio_backend):
        with PoolManager(backend=backend) as http:
            r = await http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={
                    "target": "%s/redirect?target=%s/" % (self.base_url, self.base_url)
                },
                retries=Retry(total=None, redirect=1, raise_on_redirect=False),
            )

            assert r.status == 303


class TestFileUploads(HTTPDummyServerTestCase):
    @classmethod
    def setup_class(cls):
        super(TestFileUploads, cls).setup_class()
        cls.base_url = "http://%s:%d" % (cls.host, cls.port)
        cls.base_url_alt = "http://%s:%d" % (cls.host_alt, cls.port)

    @conftest.test_all_backends
    async def test_redirect_put_file(self, backend, anyio_backend):
        """PUT with file object should work with a redirection response"""
        retry = Retry(total=3, status_forcelist=[418])
        # httplib reads in 8k chunks; use a larger content length
        content_length = 65535
        data = b"A" * content_length
        uploaded_file = io.BytesIO(data)
        headers = {
            "test-name": "test_redirect_put_file",
            "Content-Length": str(content_length),
        }
        url = "%s/redirect?target=/echo&status=307" % self.base_url

        with PoolManager(backend=backend) as http:
            resp = await http.urlopen(
                "PUT", url, headers=headers, retries=retry, body=uploaded_file
            )
            assert resp.status == 200
            assert resp.data == data

    @conftest.test_all_backends
    async def test_retries_put_filehandle(self, backend, anyio_backend):
        """HTTP PUT retry with a file-like object should not timeout"""
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
                "%s/successful_retry" % self.base_url,
                headers=headers,
                retries=retry,
                body=uploaded_file,
                redirect=False,
            )
            assert resp.status == 200

    @conftest.test_all_backends
    async def test_redirect_with_failed_tell(self, backend, anyio_backend):
        """Abort request if failed to get a position from tell()"""

        class BadTellObject(io.BytesIO):
            def tell(self):
                raise IOError

        body = BadTellObject(b"the data")
        url = "%s/redirect?target=/successful_retry" % self.base_url
        # httplib uses fileno if Content-Length isn't supplied,
        # which is unsupported by BytesIO.
        headers = {"Content-Length": "8"}

        with PoolManager(backend=backend) as http:
            with pytest.raises(UnrewindableBodyError) as e:
                await http.urlopen("PUT", url, headers=headers, body=body)
            assert "Unable to record file position for" in str(e.value)

    @conftest.test_all_backends
    async def test_redirect_with_failed_seek(self, backend, anyio_backend):
        """Abort request if failed to restore position with seek()"""

        class BadSeekObject(io.BytesIO):
            def seek(self, *_):
                raise IOError

        body = BadSeekObject(b"the data")
        url = "%s/redirect?target=/successful_retry" % self.base_url
        # httplib uses fileno if Content-Length isn't supplied,
        # which is unsupported by BytesIO.
        headers = {"Content-Length": "8"}

        with PoolManager(backend=backend) as http:
            with pytest.raises(UnrewindableBodyError) as e:
                await http.urlopen("PUT", url, headers=headers, body=body)
            assert (
                "An error occurred when rewinding request body for redirect/retry."
                == str(e.value)
            )
