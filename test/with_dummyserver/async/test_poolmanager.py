from hip import AsyncPoolManager

from test.with_dummyserver import conftest


class TestPoolManager:
    @conftest.test_all_backends
    async def test_redirect(self, http_server, backend):
        base_url = "http://{}:{}".format(http_server.host, http_server.port)
        with AsyncPoolManager(backend=backend) as http:
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
