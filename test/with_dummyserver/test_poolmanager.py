import json
import time

import pytest

from dummyserver.server import HAS_IPV6
from dummyserver.testcase import HTTPDummyServerTestCase, IPv6HTTPDummyServerTestCase
from hip.base import DEFAULT_PORTS
from hip.poolmanager import PoolManager
from hip.exceptions import MaxRetryError, NewConnectionError
from hip.util.retry import Retry, RequestHistory

from test import LONG_TIMEOUT

# Retry failed tests
pytestmark = pytest.mark.flaky


class TestPoolManager(HTTPDummyServerTestCase):
    @classmethod
    def setup_class(cls):
        super(TestPoolManager, cls).setup_class()
        cls.base_url = "http://%s:%d" % (cls.host, cls.port)
        cls.base_url_alt = "http://%s:%d" % (cls.host_alt, cls.port)

    def test_redirect(self):
        with PoolManager() as http:
            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/" % self.base_url},
                redirect=False,
            )

            assert r.status == 303

            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/" % self.base_url},
            )

            assert r.status == 200
            assert r.data == b"Dummy server!"

    def test_redirect_twice(self):
        with PoolManager() as http:
            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/redirect" % self.base_url},
                redirect=False,
            )

            assert r.status == 303

            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={
                    "target": "%s/redirect?target=%s/" % (self.base_url, self.base_url)
                },
            )

            assert r.status == 200
            assert r.data == b"Dummy server!"

    def test_redirect_to_relative_url(self):
        with PoolManager() as http:
            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "/redirect"},
                redirect=False,
            )

            assert r.status == 303

            r = http.request(
                "GET", "%s/redirect" % self.base_url, fields={"target": "/redirect"}
            )

            assert r.status == 200
            assert r.data == b"Dummy server!"

    def test_cross_host_redirect(self):
        with PoolManager() as http:
            cross_host_location = "%s/echo?a=b" % self.base_url_alt
            with pytest.raises(MaxRetryError):
                http.request(
                    "GET",
                    "%s/redirect" % self.base_url,
                    fields={"target": cross_host_location},
                    timeout=LONG_TIMEOUT,
                    retries=0,
                )

            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/echo?a=b" % self.base_url_alt},
                timeout=LONG_TIMEOUT,
                retries=1,
            )

            assert r._pool.host == self.host_alt

    def test_too_many_redirects(self):
        with PoolManager() as http:
            with pytest.raises(MaxRetryError):
                http.request(
                    "GET",
                    "%s/redirect" % self.base_url,
                    fields={
                        "target": "%s/redirect?target=%s/"
                        % (self.base_url, self.base_url)
                    },
                    retries=1,
                )

            with pytest.raises(MaxRetryError):
                http.request(
                    "GET",
                    "%s/redirect" % self.base_url,
                    fields={
                        "target": "%s/redirect?target=%s/"
                        % (self.base_url, self.base_url)
                    },
                    retries=Retry(total=None, redirect=1),
                )

    def test_redirect_cross_host_remove_headers(self):
        with PoolManager() as http:
            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/headers" % self.base_url_alt},
                headers={"Authorization": "foo"},
            )

            assert r.status == 200

            data = json.loads(r.data.decode("utf-8"))

            assert "Authorization" not in data

            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/headers" % self.base_url_alt},
                headers={"authorization": "foo"},
            )

            assert r.status == 200

            data = json.loads(r.data.decode("utf-8"))

            assert "authorization" not in data
            assert "Authorization" not in data

    def test_redirect_cross_host_no_remove_headers(self):
        with PoolManager() as http:
            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "%s/headers" % self.base_url_alt},
                headers={"Authorization": "foo"},
                retries=Retry(remove_headers_on_redirect=[]),
            )

            assert r.status == 200

            data = json.loads(r.data.decode("utf-8"))

            assert data["Authorization"] == "foo"

    def test_redirect_cross_host_set_removed_headers(self):
        with PoolManager() as http:
            r = http.request(
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

            r = http.request(
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

    def test_raise_on_redirect(self):
        with PoolManager() as http:
            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={
                    "target": "%s/redirect?target=%s/" % (self.base_url, self.base_url)
                },
                retries=Retry(total=None, redirect=1, raise_on_redirect=False),
            )

            assert r.status == 303

    def test_raise_on_status(self):
        with PoolManager() as http:
            with pytest.raises(MaxRetryError):
                # the default is to raise
                r = http.request(
                    "GET",
                    "%s/status" % self.base_url,
                    fields={"status": "500 Internal Server Error"},
                    retries=Retry(total=1, status_forcelist=range(500, 600)),
                )

            with pytest.raises(MaxRetryError):
                # raise explicitly
                r = http.request(
                    "GET",
                    "%s/status" % self.base_url,
                    fields={"status": "500 Internal Server Error"},
                    retries=Retry(
                        total=1, status_forcelist=range(500, 600), raise_on_status=True
                    ),
                )

            # don't raise
            r = http.request(
                "GET",
                "%s/status" % self.base_url,
                fields={"status": "500 Internal Server Error"},
                retries=Retry(
                    total=1, status_forcelist=range(500, 600), raise_on_status=False
                ),
            )

            assert r.status == 500

    @pytest.mark.parametrize(
        ["target", "expected_target"],
        [
            ("/echo_uri?q=1#fragment", b"/echo_uri?q=1"),
            ("/echo_uri?#", b"/echo_uri?"),
            ("/echo_uri#?", b"/echo_uri"),
            ("/echo_uri#?#", b"/echo_uri"),
            ("/echo_uri??#", b"/echo_uri??"),
            ("/echo_uri?%3f#", b"/echo_uri?%3F"),
            ("/echo_uri?%3F#", b"/echo_uri?%3F"),
            ("/echo_uri?[]", b"/echo_uri?%5B%5D"),
        ],
    )
    def test_encode_http_target(self, target, expected_target):
        with PoolManager() as http:
            url = "http://%s:%d%s" % (self.host, self.port, target)
            r = http.request("GET", url)
            assert r.data == expected_target

    def test_missing_port(self):
        # Can a URL that lacks an explicit port like ':80' succeed, or
        # will all such URLs fail with an error?

        with PoolManager() as http:
            # By globally adjusting `DEFAULT_PORTS` we pretend for a moment
            # that HTTP's default port is not 80, but is the port at which
            # our test server happens to be listening.
            DEFAULT_PORTS["http"] = self.port
            try:
                r = http.request("GET", "http://%s/" % self.host, retries=0)
            finally:
                DEFAULT_PORTS["http"] = 80

            assert r.status == 200
            assert r.data == b"Dummy server!"

    def test_headers(self):
        with PoolManager(headers={"Foo": "bar"}) as http:
            r = http.request("GET", "%s/headers" % self.base_url)
            returned_headers = json.loads(r.data.decode())
            assert returned_headers.get("Foo") == "bar"

            r = http.request("POST", "%s/headers" % self.base_url)
            returned_headers = json.loads(r.data.decode())
            assert returned_headers.get("Foo") == "bar"

            r = http.request_encode_url("GET", "%s/headers" % self.base_url)
            returned_headers = json.loads(r.data.decode())
            assert returned_headers.get("Foo") == "bar"

            r = http.request_encode_body("POST", "%s/headers" % self.base_url)
            returned_headers = json.loads(r.data.decode())
            assert returned_headers.get("Foo") == "bar"

            r = http.request_encode_url(
                "GET", "%s/headers" % self.base_url, headers={"Baz": "quux"}
            )
            returned_headers = json.loads(r.data.decode())
            assert returned_headers.get("Foo") is None
            assert returned_headers.get("Baz") == "quux"

            r = http.request_encode_body(
                "GET", "%s/headers" % self.base_url, headers={"Baz": "quux"}
            )
            returned_headers = json.loads(r.data.decode())
            assert returned_headers.get("Foo") is None
            assert returned_headers.get("Baz") == "quux"

    def test_http_with_ssl_keywords(self):
        with PoolManager(ca_certs="REQUIRED") as http:
            r = http.request("GET", "http://%s:%s/" % (self.host, self.port))
            assert r.status == 200

    def test_http_with_ca_cert_dir(self):
        with PoolManager(ca_certs="REQUIRED", ca_cert_dir="/nosuchdir") as http:
            r = http.request("GET", "http://%s:%s/" % (self.host, self.port))
            assert r.status == 200

    def test_cleanup_on_connection_error(self):
        """
        Test that connections are recycled to the pool on
        connection errors where no http response is received.
        """
        poolsize = 3

        with PoolManager(maxsize=poolsize, block=True) as http:
            pool = http.connection_from_host(self.host, self.port)
            assert pool.pool.qsize() == poolsize

            # force a connection error by supplying a non-existent
            # url. We won't get a response for this  and so the
            # conn won't be implicitly returned to the pool.
            url = "%s/redirect" % self.base_url
            with pytest.raises(MaxRetryError):
                http.request("GET", url, fields={"target": "/"}, retries=0)

            r = http.request("GET", url, fields={"target": "/"}, retries=1)
            r.release_conn()

            # the pool should still contain poolsize elements
            assert pool.pool.qsize() == poolsize


class TestRetry(HTTPDummyServerTestCase):
    @classmethod
    def setup_class(self):
        super(TestRetry, self).setup_class()
        self.base_url = "http://%s:%d" % (self.host, self.port)
        self.base_url_alt = "http://%s:%d" % (self.host_alt, self.port)

    def test_max_retry(self):
        with PoolManager() as http:
            with pytest.raises(MaxRetryError):
                http.request(
                    "GET",
                    "%s/redirect" % self.base_url,
                    fields={"target": "/"},
                    retries=0,
                )

    def test_disabled_retry(self):
        """ Disabled retries should disable redirect handling. """
        with PoolManager() as http:
            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "/"},
                retries=False,
            )
            assert r.status == 303

            r = http.request(
                "GET",
                "%s/redirect" % self.base_url,
                fields={"target": "/"},
                retries=Retry(redirect=False),
            )
            assert r.status == 303

            with pytest.raises(NewConnectionError):
                http.request(
                    "GET",
                    "http://thishostdoesnotexist.invalid/",
                    timeout=0.001,
                    retries=False,
                )

    def test_read_retries(self):
        """ Should retry for status codes in the whitelist """
        retry = Retry(read=1, status_forcelist=[418])

        with PoolManager() as http:
            resp = http.request(
                "GET",
                "%s/successful_retry" % self.base_url,
                headers={"test-name": "test_read_retries"},
                retries=retry,
            )
            assert resp.status == 200

    def test_read_total_retries(self):
        """ HTTP response w/ status code in the whitelist should be retried """
        headers = {"test-name": "test_read_total_retries"}
        retry = Retry(total=1, status_forcelist=[418])

        with PoolManager() as http:
            resp = http.request(
                "GET",
                "%s/successful_retry" % self.base_url,
                headers=headers,
                retries=retry,
            )
            assert resp.status == 200

    def test_retries_wrong_whitelist(self):
        """HTTP response w/ status code not in whitelist shouldn't be retried"""
        retry = Retry(total=1, status_forcelist=[202])

        with PoolManager() as http:
            resp = http.request(
                "GET",
                "%s/successful_retry" % self.base_url,
                headers={"test-name": "test_wrong_whitelist"},
                retries=retry,
            )
            assert resp.status == 418

    def test_default_method_whitelist_retried(self):
        """Hip should retry methods in the default method whitelist"""
        retry = Retry(total=1, status_forcelist=[418])

        with PoolManager() as http:
            resp = http.request(
                "OPTIONS",
                "%s/successful_retry" % self.base_url,
                headers={"test-name": "test_default_whitelist"},
                retries=retry,
            )
            assert resp.status == 200

    def test_retries_wrong_method_list(self):
        """Method not in our whitelist should not be retried, even if code matches"""
        headers = {"test-name": "test_wrong_method_whitelist"}
        retry = Retry(total=1, status_forcelist=[418], method_whitelist=["POST"])

        with PoolManager() as http:
            resp = http.request(
                "GET",
                "%s/successful_retry" % self.base_url,
                headers=headers,
                retries=retry,
            )
            assert resp.status == 418

    def test_read_retries_unsuccessful(self):
        headers = {"test-name": "test_read_retries_unsuccessful"}

        with PoolManager() as http:
            resp = http.request(
                "GET", "%s/successful_retry" % self.base_url, headers=headers, retries=1
            )
            assert resp.status == 418

    def test_retry_reuse_safe(self):
        """ It should be possible to reuse a Retry object across requests """
        headers = {"test-name": "test_retry_safe"}
        retry = Retry(total=1, status_forcelist=[418])

        with PoolManager() as http:
            resp = http.request(
                "GET",
                "%s/successful_retry" % self.base_url,
                headers=headers,
                retries=retry,
            )
            assert resp.status == 200
            resp = http.request(
                "GET",
                "%s/successful_retry" % self.base_url,
                headers=headers,
                retries=retry,
            )
            assert resp.status == 200

    def test_retry_return_in_response(self):
        headers = {"test-name": "test_retry_return_in_response"}
        retry = Retry(total=2, status_forcelist=[418])

        with PoolManager() as http:
            resp = http.request(
                "GET",
                "%s/successful_retry" % self.base_url,
                headers=headers,
                retries=retry,
            )
            assert resp.status == 200
            assert resp.retries.total == 1
            assert resp.retries.history == (
                RequestHistory("GET", "/successful_retry", None, 418, None),
            )

    def test_retry_redirect_history(self):
        with PoolManager() as http:
            resp = http.request(
                "GET", "%s/redirect" % self.base_url, fields={"target": "/"}
            )
            assert resp.status == 200
            assert resp.retries.history == (
                RequestHistory(
                    "GET", self.base_url + "/redirect?target=%2F", None, 303, "/"
                ),
            )

    def test_multi_redirect_history(self):
        with PoolManager() as http:
            r = http.request(
                "GET",
                "%s/multi_redirect" % self.base_url,
                fields={"redirect_codes": "303,302,200"},
                redirect=False,
            )
            assert r.status == 303
            assert r.retries.history == tuple()

            r = http.request(
                "GET",
                "%s/multi_redirect" % self.base_url,
                retries=10,
                fields={"redirect_codes": "303,302,301,307,302,200"},
            )
            assert r.status == 200
            assert r.data == b"Done redirecting"

            expected = [
                (303, "/multi_redirect?redirect_codes=302,301,307,302,200"),
                (302, "/multi_redirect?redirect_codes=301,307,302,200"),
                (301, "/multi_redirect?redirect_codes=307,302,200"),
                (307, "/multi_redirect?redirect_codes=302,200"),
                (302, "/multi_redirect?redirect_codes=200"),
            ]
            actual = [
                (history.status, history.redirect_location)
                for history in r.retries.history
            ]
            assert actual == expected


class TestRetryAfter(HTTPDummyServerTestCase):
    @classmethod
    def setup_class(self):
        super(TestRetryAfter, self).setup_class()
        self.base_url = "http://%s:%d" % (self.host, self.port)
        self.base_url_alt = "http://%s:%d" % (self.host_alt, self.port)

    def test_retry_after(self):
        url = "%s/retry_after" % self.base_url
        with PoolManager() as http:
            # Request twice in a second to get a 429 response.
            r = http.request(
                "GET", url, fields={"status": "429 Too Many Requests"}, retries=False
            )
            r = http.request(
                "GET", url, fields={"status": "429 Too Many Requests"}, retries=False
            )
            assert r.status == 429

            r = http.request(
                "GET", url, fields={"status": "429 Too Many Requests"}, retries=True
            )
            assert r.status == 200

            # Request twice in a second to get a 503 response.
            r = http.request(
                "GET", url, fields={"status": "503 Service Unavailable"}, retries=False
            )
            r = http.request(
                "GET", url, fields={"status": "503 Service Unavailable"}, retries=False
            )
            assert r.status == 503

            r = http.request(
                "GET", url, fields={"status": "503 Service Unavailable"}, retries=True
            )
            assert r.status == 200

            # Ignore Retry-After header on status which is not defined in
            # Retry.RETRY_AFTER_STATUS_CODES.
            r = http.request(
                "GET", url, fields={"status": "418 I'm a teapot"}, retries=True
            )
            assert r.status == 418

    def test_redirect_after(self):
        with PoolManager() as http:
            r = http.request("GET", "%s/redirect_after" % self.base_url, retries=False)
            assert r.status == 303

            t = time.time()
            r = http.request("GET", "%s/redirect_after" % self.base_url)
            assert r.status == 200
            delta = time.time() - t
            assert delta >= 1

            t = time.time()
            timestamp = t + 2
            r = http.request(
                "GET", self.base_url + "/redirect_after?date=" + str(timestamp)
            )
            assert r.status == 200
            delta = time.time() - t
            assert delta >= 1

            # Retry-After is past
            t = time.time()
            timestamp = t - 1
            r = http.request(
                "GET", self.base_url + "/redirect_after?date=" + str(timestamp)
            )
            delta = time.time() - t
            assert r.status == 200
            assert delta < 1


@pytest.mark.skipif(not HAS_IPV6, reason="IPv6 is not supported on this system")
class TestIPv6PoolManager(IPv6HTTPDummyServerTestCase):
    @classmethod
    def setup_class(cls):
        super(TestIPv6PoolManager, cls).setup_class()
        cls.base_url = "http://[%s]:%d" % (cls.host, cls.port)

    def test_ipv6(self):
        with PoolManager() as http:
            http.request("GET", self.base_url)
