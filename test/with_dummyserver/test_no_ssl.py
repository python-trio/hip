"""
Test connections without the builtin ssl module

Note: Import hip inside the test functions to get the importblocker to work
"""
import pytest
from ..test_no_ssl import TestWithoutSSL

from dummyserver.testcase import HTTPDummyServerTestCase, HTTPSDummyServerTestCase

import hip

# Retry failed tests
pytestmark = pytest.mark.flaky


class TestHTTPWithoutSSL(HTTPDummyServerTestCase, TestWithoutSSL):
    @pytest.mark.skip(
        reason=(
            "TestWithoutSSL mutates sys.modules."
            "This breaks the backend loading code which imports modules at runtime."
            "See discussion at https://github.com/python-trio/hip/pull/42"
        )
    )
    def test_simple(self):
        with hip.HTTPConnectionPool(self.host, self.port) as pool:
            r = pool.request("GET", "/")
            assert r.status == 200, r.data


class TestHTTPSWithoutSSL(HTTPSDummyServerTestCase, TestWithoutSSL):
    def test_simple(self):
        try:
            pool = hip.HTTPSConnectionPool(self.host, self.port, cert_reqs="NONE")
        except hip.exceptions.SSLError as e:
            assert "SSL module is not available" in str(e)
        finally:
            pool.close()
