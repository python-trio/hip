from dummyserver.testcase import HTTPDummyServerTestCase
from urllib3 import AsyncPoolManager


class TestPoolManager(HTTPDummyServerTestCase):
    @classmethod
    def setup_class(self):
        super(TestPoolManager, self).setup_class()
        self.base_url = "http://%s:%d" % (self.host, self.port)
        self.base_url_alt = "http://%s:%d" % (self.host_alt, self.port)

    async def test_redirect(self):
        with AsyncPoolManager() as http:
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
