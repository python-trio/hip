import time

import pytest

from dummyserver.server import HAS_IPV6
from dummyserver.testcase import HTTPDummyServerTestCase, IPv6HTTPDummyServerTestCase
from hip.poolmanager import PoolManager

# Retry failed tests
pytestmark = pytest.mark.flaky


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
