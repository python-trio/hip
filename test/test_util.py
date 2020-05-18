# coding: utf-8
import hashlib
import warnings
import logging
import io
import ssl
import socket
from itertools import chain

from mock import patch, Mock
import pytest

from hip import add_stderr_logger, disable_warnings
from hip.util.request import make_headers, rewind_body, _FAILEDTELL
from hip.util.retry import Retry
from hip.util.timeout import Timeout
from hip.util.url import parse_url, Url
from hip.util.ssl_ import (
    resolve_cert_reqs,
    resolve_ssl_version,
    ssl_wrap_socket,
    _const_compare_digest_backport,
)
from hip.exceptions import (
    LocationParseError,
    TimeoutStateError,
    InsecureRequestWarning,
    SNIMissingWarning,
    InvalidHeader,
    UnrewindableBodyError,
)
from hip.util.connection import allowed_gai_family, _has_ipv6
from hip.util import ssl_
from hip.packages import six

from . import clear_warnings

from test import onlyPy3, onlyPy2, onlyBrotlipy, notBrotlipy

# This number represents a time in seconds, it doesn't mean anything in
# isolation. Setting to a high-ish value to avoid conflicts with the smaller
# numbers used for timeouts
TIMEOUT_EPOCH = 1000


class TestUtil(object):

    # TODO: Add more tests
    @pytest.mark.parametrize(
        "location",
        [
            "http://google.com:foo",
            "http://::1/",
            "http://::1:80/",
            "http://google.com:-80",
            six.u("http://google.com:\xb2\xb2"),  # \xb2 = ^2
        ],
    )
    def test_invalid_host(self, location):
        with pytest.raises(LocationParseError):
            parse_url(location)

    @pytest.mark.parametrize(
        "url",
        [
            # Invalid IDNA labels
            u"http://\uD7FF.com",
            u"http://❤️",
            # Unicode surrogates
            u"http://\uD800.com",
            u"http://\uDC00.com",
        ],
    )
    def test_invalid_url(self, url):
        with pytest.raises(LocationParseError):
            parse_url(url)

    @pytest.mark.parametrize(
        "url, expected_normalized_url",
        [
            ("HTTP://GOOGLE.COM/MAIL/", "http://google.com/MAIL/"),
            (
                "http://user@domain.com:password@example.com/~tilde@?@",
                "http://user%40domain.com:password@example.com/~tilde@?@",
            ),
            (
                "HTTP://JeremyCline:Hunter2@Example.com:8080/",
                "http://JeremyCline:Hunter2@example.com:8080/",
            ),
            ("HTTPS://Example.Com/?Key=Value", "https://example.com/?Key=Value"),
            ("Https://Example.Com/#Fragment", "https://example.com/#Fragment"),
            ("[::1%25]", "[::1%25]"),
            ("[::Ff%etH0%Ff]/%ab%Af", "[::ff%etH0%FF]/%AB%AF"),
            (
                "http://user:pass@[AaAa::Ff%25etH0%Ff]/%ab%Af",
                "http://user:pass@[aaaa::ff%etH0%FF]/%AB%AF",
            ),
            # Invalid characters for the query/fragment getting encoded
            (
                'http://google.com/p[]?parameter[]="hello"#fragment#',
                "http://google.com/p%5B%5D?parameter%5B%5D=%22hello%22#fragment%23",
            ),
            # Percent encoding isn't applied twice despite '%' being invalid
            # but the percent encoding is still normalized.
            (
                "http://google.com/p%5B%5d?parameter%5b%5D=%22hello%22#fragment%23",
                "http://google.com/p%5B%5D?parameter%5B%5D=%22hello%22#fragment%23",
            ),
        ],
    )
    def test_parse_url_normalization(self, url, expected_normalized_url):
        """Assert parse_url normalizes the scheme/host, and only the scheme/host"""
        actual_normalized_url = parse_url(url).url
        assert actual_normalized_url == expected_normalized_url

    @pytest.mark.parametrize("char", [chr(i) for i in range(0x00, 0x21)] + ["\x7F"])
    def test_control_characters_are_percent_encoded(self, char):
        percent_char = "%" + (hex(ord(char))[2:].zfill(2).upper())
        url = parse_url(
            "http://user{0}@example.com/path{0}?query{0}#fragment{0}".format(char)
        )

        assert url == Url(
            "http",
            auth="user" + percent_char,
            host="example.com",
            path="/path" + percent_char,
            query="query" + percent_char,
            fragment="fragment" + percent_char,
        )

    parse_url_host_map = [
        ("http://google.com/mail", Url("http", host="google.com", path="/mail")),
        ("http://google.com/mail/", Url("http", host="google.com", path="/mail/")),
        ("http://google.com/mail", Url("http", host="google.com", path="mail")),
        ("google.com/mail", Url(host="google.com", path="/mail")),
        ("http://google.com/", Url("http", host="google.com", path="/")),
        ("http://google.com", Url("http", host="google.com")),
        ("http://google.com?foo", Url("http", host="google.com", query="foo")),
        # Path/query/fragment
        ("", Url()),
        ("/", Url(path="/")),
        ("#?/!google.com/?foo", Url(fragment="?/!google.com/?foo")),
        ("/foo", Url(path="/foo")),
        ("/foo?bar=baz", Url(path="/foo", query="bar=baz")),
        (
            "/foo?bar=baz#banana?apple/orange",
            Url(path="/foo", query="bar=baz", fragment="banana?apple/orange"),
        ),
        (
            "/redirect?target=http://localhost:61020/",
            Url(path="redirect", query="target=http://localhost:61020/"),
        ),
        # Port
        ("http://google.com/", Url("http", host="google.com", path="/")),
        ("http://google.com:80/", Url("http", host="google.com", port=80, path="/")),
        ("http://google.com:80", Url("http", host="google.com", port=80)),
        # Auth
        (
            "http://foo:bar@localhost/",
            Url("http", auth="foo:bar", host="localhost", path="/"),
        ),
        ("http://foo@localhost/", Url("http", auth="foo", host="localhost", path="/")),
        (
            "http://foo:bar@localhost/",
            Url("http", auth="foo:bar", host="localhost", path="/"),
        ),
        # Unicode type (Python 2.x)
        (
            u"http://foo:bar@localhost/",
            Url(u"http", auth=u"foo:bar", host=u"localhost", path=u"/"),
        ),
        (
            "http://foo:bar@localhost/",
            Url("http", auth="foo:bar", host="localhost", path="/"),
        ),
        (
            "http://user:password@127.0.0.1:1234",
            Url(scheme="http", auth="user:password", host="127.0.0.1", port=1234),
        ),
        (
            "http://google.com/foo=http://bar:42/baz",
            Url(scheme="http", host="google.com", path="/foo=http://bar:42/baz"),
        ),
        (
            "http://google.com?foo=http://bar:42/baz",
            Url(scheme="http", host="google.com", query="foo=http://bar:42/baz"),
        ),
        (
            "http://google.com#foo=http://bar:42/baz",
            Url(scheme="http", host="google.com", fragment="foo=http://bar:42/baz"),
        ),
        # IPv4
        ("173.194.35.7", Url(scheme=None, host="173.194.35.7")),
        ("http://173.194.35.7", Url(scheme="http", host="173.194.35.7")),
        (
            "http://173.194.35.7/test",
            Url(scheme="http", host="173.194.35.7", path="/test"),
        ),
        ("http://173.194.35.7:80", Url(scheme="http", host="173.194.35.7", port=80)),
        (
            "http://173.194.35.7:80/test",
            Url(scheme="http", host="173.194.35.7", port=80, path="/test"),
        ),
        # IPv6
        ("[2a00:1450:4001:c01::67]", Url(auth=None, host="[2a00:1450:4001:c01::67]")),
        (
            "http://[2a00:1450:4001:c01::67]",
            Url(scheme="http", host="[2a00:1450:4001:c01::67]"),
        ),
        (
            "http://[2a00:1450:4001:c01::67]/test",
            Url(scheme="http", host="[2a00:1450:4001:c01::67]", path="/test"),
        ),
        (
            "http://[2a00:1450:4001:c01::67]:80",
            Url(scheme="http", host="[2a00:1450:4001:c01::67]", port=80),
        ),
        (
            "http://[2a00:1450:4001:c01::67]:80/test",
            Url(scheme="http", host="[2a00:1450:4001:c01::67]", port=80, path="/test"),
        ),
        # More IPv6 from http://www.ietf.org/rfc/rfc2732.txt
        (
            "http://[fedc:ba98:7654:3210:fedc:ba98:7654:3210]:8000/index.html",
            Url(
                scheme="http",
                host="[fedc:ba98:7654:3210:fedc:ba98:7654:3210]",
                port=8000,
                path="/index.html",
            ),
        ),
        (
            "http://[1080:0:0:0:8:800:200c:417a]/index.html",
            Url(scheme="http", host="[1080:0:0:0:8:800:200c:417a]", path="/index.html"),
        ),
        (
            "http://[3ffe:2a00:100:7031::1]",
            Url(scheme="http", host="[3ffe:2a00:100:7031::1]"),
        ),
        (
            "http://[1080::8:800:200c:417a]/foo",
            Url(scheme="http", host="[1080::8:800:200c:417a]", path="/foo"),
        ),
        (
            "http://[::192.9.5.5]/ipng",
            Url(scheme="http", host="[::192.9.5.5]", path="/ipng"),
        ),
        (
            "http://[::ffff:129.144.52.38]:42/index.html",
            Url(
                scheme="http",
                host="[::ffff:129.144.52.38]",
                port=42,
                path="/index.html",
            ),
        ),
        (
            "http://[2010:836b:4179::836b:4179]",
            Url(scheme="http", host="[2010:836b:4179::836b:4179]"),
        ),
        # Hosts
        ("google.com/mail", Url(scheme=None, host="google.com", path="/mail")),
        (
            "http://google.com:8000/mail/",
            Url(scheme="http", host="google.com", port=8000, path="/mail/"),
        ),
        (
            "http://user:password@example.com:1234",
            Url(scheme="http", auth="user:password", host="example.com", port=1234),
        ),
        ("173.194.35.7", Url(scheme=None, host="173.194.35.7")),
        ("http://173.194.35.7", Url(scheme="http", host="173.194.35.7")),
        (
            "http://[2a00:1450:4001:c01::67]:80/test",
            Url(scheme="http", host="[2a00:1450:4001:c01::67]", port=80, path="/test"),
        ),
        (
            "http://[fedc:ba98:7654:3210:fedc:ba98:7654:3210]:8000/index.html",
            Url(
                scheme="http",
                host="[fedc:ba98:7654:3210:fedc:ba98:7654:3210]",
                port=8000,
                path="/index.html",
            ),
        ),
        (
            "https://[1080:0:0:0:8:800:200c:417a]/index.html",
            Url(
                scheme="https", host="[1080:0:0:0:8:800:200c:417a]", path="/index.html"
            ),
        ),
        (
            "about://eXamPlE.com?info=1",
            Url(scheme="about", host="eXamPlE.com", query="info=1"),
        ),
        (
            "http+unix://%2fvar%2frun%2fSOCKET/path",
            Url(scheme="http+unix", host="%2fvar%2frun%2fSOCKET", path="/path"),
        ),
    ]

    non_round_tripping_parse_url_host_map = [
        # Path/query/fragment
        ("?", Url(query="")),
        ("#", Url(fragment="")),
        # Path normalization
        ("/abc/../def", Url(path="/def")),
        # Empty Port
        ("http://google.com:", Url("http", host="google.com")),
        ("http://google.com:/", Url("http", host="google.com", path="/")),
        # Uppercase IRI
        (
            u"http://Königsgäßchen.de/straße",
            Url("http", host="xn--knigsgchen-b4a3dun.de", path="/stra%C3%9Fe"),
        ),
        # Percent-encode in userinfo
        (
            u"http://user@email.com:password@example.com/",
            Url("http", auth="user%40email.com:password", host="example.com", path="/"),
        ),
        (
            u'http://user":quoted@example.com/',
            Url("http", auth="user%22:quoted", host="example.com", path="/"),
        ),
        # Unicode Surrogates
        (u"http://google.com/\uD800", Url("http", host="google.com", path="%ED%A0%80")),
        (
            u"http://google.com?q=\uDC00",
            Url("http", host="google.com", query="q=%ED%B0%80"),
        ),
        (
            u"http://google.com#\uDC00",
            Url("http", host="google.com", fragment="%ED%B0%80"),
        ),
        # Hosts and Schemes
        (
            "HTTP://GOOGLE.COM/mail/",
            Url(scheme="http", host="google.com", path="/mail/"),
        ),
        ("GOogle.COM/mail", Url(scheme=None, host="google.com", path="/mail")),
        (
            "HTTP://GoOgLe.CoM:8000/mail/",
            Url(scheme="http", host="google.com", port=8000, path="/mail/"),
        ),
        (
            "HTTP://user:password@EXAMPLE.COM:1234",
            Url(scheme="http", auth="user:password", host="example.com", port=1234),
        ),
        ("HTTP://173.194.35.7", Url(scheme="http", host="173.194.35.7")),
        (
            "HTTP://[2a00:1450:4001:c01::67]:80/test",
            Url(scheme="http", host="[2a00:1450:4001:c01::67]", port=80, path="/test"),
        ),
        (
            "HTTP://[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]:8000/index.html",
            Url(
                scheme="http",
                host="[fedc:ba98:7654:3210:fedc:ba98:7654:3210]",
                port=8000,
                path="/index.html",
            ),
        ),
        (
            "HTTPS://[1080:0:0:0:8:800:200c:417A]/index.html",
            Url(
                scheme="https", host="[1080:0:0:0:8:800:200c:417a]", path="/index.html"
            ),
        ),
        (
            "aBoUt://eXamPlE.com?info=1",
            Url(scheme="about", host="eXamPlE.com", query="info=1"),
        ),
        (
            "http+UNIX://%2fvar%2frun%2fSOCKET/path",
            Url(scheme="http+unix", host="%2fvar%2frun%2fSOCKET", path="/path"),
        ),
    ]

    @pytest.mark.parametrize(
        "url, expected_url",
        chain(parse_url_host_map, non_round_tripping_parse_url_host_map),
    )
    def test_parse_url(self, url, expected_url):
        returned_url = parse_url(url)
        assert returned_url == expected_url

    @pytest.mark.parametrize("url, expected_url", parse_url_host_map)
    def test_unparse_url(self, url, expected_url):
        assert url == expected_url.url

    @pytest.mark.parametrize(
        ["url", "expected_url"],
        [
            # RFC 3986 5.2.4
            ("/abc/../def", Url(path="/def")),
            ("/..", Url(path="/")),
            ("/./abc/./def/", Url(path="/abc/def/")),
            ("/.", Url(path="/")),
            ("/./", Url(path="/")),
            ("/abc/./.././d/././e/.././f/./../../ghi", Url(path="/ghi")),
        ],
    )
    def test_parse_and_normalize_url_paths(self, url, expected_url):
        actual_url = parse_url(url)
        assert actual_url == expected_url
        assert actual_url.url == expected_url.url

    def test_parse_url_invalid_IPv6(self):
        with pytest.raises(LocationParseError):
            parse_url("[::1")

    def test_parse_url_negative_port(self):
        with pytest.raises(LocationParseError):
            parse_url("https://www.google.com:-80/")

    def test_Url_str(self):
        U = Url("http", host="google.com")
        assert str(U) == U.url

    request_uri_map = [
        ("http://google.com/mail", "/mail"),
        ("http://google.com/mail/", "/mail/"),
        ("http://google.com/", "/"),
        ("http://google.com", "/"),
        ("", "/"),
        ("/", "/"),
        ("?", "/?"),
        ("#", "/"),
        ("/foo?bar=baz", "/foo?bar=baz"),
    ]

    @pytest.mark.parametrize("url, expected_request_uri", request_uri_map)
    def test_request_uri(self, url, expected_request_uri):
        returned_url = parse_url(url)
        assert returned_url.request_uri == expected_request_uri

    url_netloc_map = [
        ("http://google.com/mail", "google.com"),
        ("http://google.com:80/mail", "google.com:80"),
        ("google.com/foobar", "google.com"),
        ("google.com:12345", "google.com:12345"),
    ]

    @pytest.mark.parametrize("url, expected_netloc", url_netloc_map)
    def test_netloc(self, url, expected_netloc):
        assert parse_url(url).netloc == expected_netloc

    url_vulnerabilities = [
        # urlparse doesn't follow RFC 3986 Section 3.2
        (
            "http://google.com#@evil.com/",
            Url("http", host="google.com", fragment="@evil.com/"),
        ),
        # CVE-2016-5699
        (
            "http://127.0.0.1%0d%0aConnection%3a%20keep-alive",
            Url("http", host="127.0.0.1%0d%0aconnection%3a%20keep-alive"),
        ),
        # NodeJS unicode -> double dot
        (
            u"http://google.com/\uff2e\uff2e/abc",
            Url("http", host="google.com", path="/%EF%BC%AE%EF%BC%AE/abc"),
        ),
        # Scheme without ://
        (
            "javascript:a='@google.com:12345/';alert(0)",
            Url(scheme="javascript", path="a='@google.com:12345/';alert(0)"),
        ),
        ("//google.com/a/b/c", Url(host="google.com", path="/a/b/c")),
        # International URLs
        (
            u"http://ヒ:キ@ヒ.abc.ニ/ヒ?キ#ワ",
            Url(
                u"http",
                host=u"xn--pdk.abc.xn--idk",
                auth=u"%E3%83%92:%E3%82%AD",
                path=u"/%E3%83%92",
                query=u"%E3%82%AD",
                fragment=u"%E3%83%AF",
            ),
        ),
        # Injected headers (CVE-2016-5699, CVE-2019-9740, CVE-2019-9947)
        (
            "10.251.0.83:7777?a=1 HTTP/1.1\r\nX-injected: header",
            Url(
                host="10.251.0.83",
                port=7777,
                query="a=1%20HTTP/1.1%0D%0AX-injected:%20header",
            ),
        ),
        (
            "http://127.0.0.1:6379?\r\nSET test failure12\r\n:8080/test/?test=a",
            Url(
                scheme="http",
                host="127.0.0.1",
                port=6379,
                query="%0D%0ASET%20test%20failure12%0D%0A:8080/test/?test=a",
            ),
        ),
    ]

    @pytest.mark.parametrize("url, expected_url", url_vulnerabilities)
    def test_url_vulnerabilities(self, url, expected_url):
        if expected_url is False:
            with pytest.raises(LocationParseError):
                parse_url(url)
        else:
            assert parse_url(url) == expected_url

    @onlyPy2
    def test_parse_url_bytes_to_str_python_2(self):
        url = parse_url(b"https://www.google.com/")
        assert url == Url("https", host="www.google.com", path="/")

        assert isinstance(url.scheme, str)
        assert isinstance(url.host, str)
        assert isinstance(url.path, str)

    @onlyPy2
    def test_parse_url_unicode_python_2(self):
        url = parse_url(u"https://www.google.com/")
        assert url == Url(u"https", host=u"www.google.com", path=u"/")

        assert isinstance(url.scheme, six.text_type)
        assert isinstance(url.host, six.text_type)
        assert isinstance(url.path, six.text_type)

    @onlyPy3
    def test_parse_url_bytes_type_error_python_3(self):
        with pytest.raises(TypeError):
            parse_url(b"https://www.google.com/")

    @pytest.mark.parametrize(
        "kwargs, expected",
        [
            pytest.param(
                {"accept_encoding": True},
                {"accept-encoding": "gzip,deflate,br"},
                marks=onlyBrotlipy(),
            ),
            pytest.param(
                {"accept_encoding": True},
                {"accept-encoding": "gzip,deflate"},
                marks=notBrotlipy(),
            ),
            ({"accept_encoding": "foo,bar"}, {"accept-encoding": "foo,bar"}),
            ({"accept_encoding": ["foo", "bar"]}, {"accept-encoding": "foo,bar"}),
            pytest.param(
                {"accept_encoding": True, "user_agent": "banana"},
                {"accept-encoding": "gzip,deflate,br", "user-agent": "banana"},
                marks=onlyBrotlipy(),
            ),
            pytest.param(
                {"accept_encoding": True, "user_agent": "banana"},
                {"accept-encoding": "gzip,deflate", "user-agent": "banana"},
                marks=notBrotlipy(),
            ),
            ({"user_agent": "banana"}, {"user-agent": "banana"}),
            ({"keep_alive": True}, {"connection": "keep-alive"}),
            ({"basic_auth": "foo:bar"}, {"authorization": "Basic Zm9vOmJhcg=="}),
            (
                {"proxy_basic_auth": "foo:bar"},
                {"proxy-authorization": "Basic Zm9vOmJhcg=="},
            ),
            ({"disable_cache": True}, {"cache-control": "no-cache"}),
        ],
    )
    def test_make_headers(self, kwargs, expected):
        assert make_headers(**kwargs) == expected

    def test_rewind_body(self):
        body = io.BytesIO(b"test data")
        assert body.read() == b"test data"

        # Assert the file object has been consumed
        assert body.read() == b""

        # Rewind it back to just be b'data'
        rewind_body(body, 5)
        assert body.read() == b"data"

    def test_rewind_body_failed_tell(self):
        body = io.BytesIO(b"test data")
        body.read()  # Consume body

        # Simulate failed tell()
        body_pos = _FAILEDTELL
        with pytest.raises(UnrewindableBodyError):
            rewind_body(body, body_pos)

    def test_rewind_body_bad_position(self):
        body = io.BytesIO(b"test data")
        body.read()  # Consume body

        # Pass non-integer position
        with pytest.raises(ValueError):
            rewind_body(body, body_pos=None)
        with pytest.raises(ValueError):
            rewind_body(body, body_pos=object())

    def test_rewind_body_failed_seek(self):
        class BadSeek:
            def seek(self, pos, offset=0):
                raise IOError

        with pytest.raises(UnrewindableBodyError):
            rewind_body(BadSeek(), body_pos=2)

    def test_add_stderr_logger(self):
        handler = add_stderr_logger(level=logging.INFO)  # Don't actually print debug
        logger = logging.getLogger("hip")
        assert handler in logger.handlers

        logger.debug("Testing add_stderr_logger")
        logger.removeHandler(handler)

    def test_disable_warnings(self):
        with warnings.catch_warnings(record=True) as w:
            clear_warnings()
            warnings.warn("This is a test.", InsecureRequestWarning)
            assert len(w) == 1
            disable_warnings()
            warnings.warn("This is a test.", InsecureRequestWarning)
            assert len(w) == 1

    def _make_time_pass(self, seconds, timeout, time_mock):
        """ Make some time pass for the timeout object """
        time_mock.return_value = TIMEOUT_EPOCH
        timeout.start_connect()
        time_mock.return_value = TIMEOUT_EPOCH + seconds
        return timeout

    @pytest.mark.parametrize(
        "kwargs, message",
        [
            ({"total": -1}, "less than"),
            ({"connect": 2, "total": -1}, "less than"),
            ({"read": -1}, "less than"),
            ({"connect": False}, "cannot be a boolean"),
            ({"read": True}, "cannot be a boolean"),
            ({"connect": 0}, "less than or equal"),
            ({"read": "foo"}, "int, float or None"),
        ],
    )
    def test_invalid_timeouts(self, kwargs, message):
        with pytest.raises(ValueError) as e:
            Timeout(**kwargs)
        assert message in str(e.value)

    @patch("hip.util.timeout.current_time")
    def test_timeout(self, current_time):
        timeout = Timeout(total=3)

        # make 'no time' elapse
        timeout = self._make_time_pass(
            seconds=0, timeout=timeout, time_mock=current_time
        )
        assert timeout.read_timeout == 3
        assert timeout.connect_timeout == 3

        timeout = Timeout(total=3, connect=2)
        assert timeout.connect_timeout == 2

        timeout = Timeout()
        assert timeout.connect_timeout == Timeout.DEFAULT_TIMEOUT

        # Connect takes 5 seconds, leaving 5 seconds for read
        timeout = Timeout(total=10, read=7)
        timeout = self._make_time_pass(
            seconds=5, timeout=timeout, time_mock=current_time
        )
        assert timeout.read_timeout == 5

        # Connect takes 2 seconds, read timeout still 7 seconds
        timeout = Timeout(total=10, read=7)
        timeout = self._make_time_pass(
            seconds=2, timeout=timeout, time_mock=current_time
        )
        assert timeout.read_timeout == 7

        timeout = Timeout(total=10, read=7)
        assert timeout.read_timeout == 7

        timeout = Timeout(total=None, read=None, connect=None)
        assert timeout.connect_timeout is None
        assert timeout.read_timeout is None
        assert timeout.total is None

        timeout = Timeout(5)
        assert timeout.total == 5

    def test_timeout_str(self):
        timeout = Timeout(connect=1, read=2, total=3)
        assert str(timeout) == "Timeout(connect=1, read=2, total=3)"
        timeout = Timeout(connect=1, read=None, total=3)
        assert str(timeout) == "Timeout(connect=1, read=None, total=3)"

    @patch("hip.util.timeout.current_time")
    def test_timeout_elapsed(self, current_time):
        current_time.return_value = TIMEOUT_EPOCH
        timeout = Timeout(total=3)
        with pytest.raises(TimeoutStateError):
            timeout.get_connect_duration()

        timeout.start_connect()
        with pytest.raises(TimeoutStateError):
            timeout.start_connect()

        current_time.return_value = TIMEOUT_EPOCH + 2
        assert timeout.get_connect_duration() == 2
        current_time.return_value = TIMEOUT_EPOCH + 37
        assert timeout.get_connect_duration() == 37

    @pytest.mark.parametrize(
        "candidate, requirements",
        [
            (None, ssl.CERT_REQUIRED),
            (ssl.CERT_NONE, ssl.CERT_NONE),
            (ssl.CERT_REQUIRED, ssl.CERT_REQUIRED),
            ("REQUIRED", ssl.CERT_REQUIRED),
            ("CERT_REQUIRED", ssl.CERT_REQUIRED),
        ],
    )
    def test_resolve_cert_reqs(self, candidate, requirements):
        assert resolve_cert_reqs(candidate) == requirements

    @pytest.mark.parametrize(
        "candidate, version",
        [
            (ssl.PROTOCOL_TLSv1, ssl.PROTOCOL_TLSv1),
            ("PROTOCOL_TLSv1", ssl.PROTOCOL_TLSv1),
            ("TLSv1", ssl.PROTOCOL_TLSv1),
            (ssl.PROTOCOL_SSLv23, ssl.PROTOCOL_SSLv23),
        ],
    )
    def test_resolve_ssl_version(self, candidate, version):
        assert resolve_ssl_version(candidate) == version

    def test_ssl_wrap_socket_loads_the_cert_chain(self):
        socket = object()
        mock_context = Mock()
        ssl_wrap_socket(
            ssl_context=mock_context, sock=socket, certfile="/path/to/certfile"
        )

        mock_context.load_cert_chain.assert_called_once_with("/path/to/certfile", None)

    @patch("hip.util.ssl_.create_ssl_context")
    def test_ssl_wrap_socket_creates_new_context(self, create_ssl_context):
        socket = object()
        ssl_wrap_socket(sock=socket, cert_reqs="CERT_REQUIRED")

        create_ssl_context.assert_called_once_with(None, "CERT_REQUIRED", ciphers=None)

    def test_ssl_wrap_socket_loads_verify_locations(self):
        socket = object()
        mock_context = Mock()
        ssl_wrap_socket(ssl_context=mock_context, ca_certs="/path/to/pem", sock=socket)
        mock_context.load_verify_locations.assert_called_once_with("/path/to/pem", None)

    def test_ssl_wrap_socket_loads_certificate_directories(self):
        socket = object()
        mock_context = Mock()
        ssl_wrap_socket(
            ssl_context=mock_context, ca_cert_dir="/path/to/pems", sock=socket
        )
        mock_context.load_verify_locations.assert_called_once_with(
            None, "/path/to/pems"
        )

    def test_ssl_wrap_socket_with_no_sni_warns(self):
        socket = object()
        mock_context = Mock()
        # Ugly preservation of original value
        HAS_SNI = ssl_.HAS_SNI
        ssl_.HAS_SNI = False
        try:
            with patch("warnings.warn") as warn:
                ssl_wrap_socket(
                    ssl_context=mock_context,
                    sock=socket,
                    server_hostname="www.google.com",
                )
            mock_context.wrap_socket.assert_called_once_with(socket)
            assert warn.call_count >= 1
            warnings = [call[0][1] for call in warn.call_args_list]
            assert SNIMissingWarning in warnings
        finally:
            ssl_.HAS_SNI = HAS_SNI

    def test_const_compare_digest_fallback(self):
        target = hashlib.sha256(b"abcdef").digest()
        assert _const_compare_digest_backport(target, target)

        prefix = target[:-1]
        assert not _const_compare_digest_backport(target, prefix)

        suffix = target + b"0"
        assert not _const_compare_digest_backport(target, suffix)

        incorrect = hashlib.sha256(b"xyz").digest()
        assert not _const_compare_digest_backport(target, incorrect)

    def test_has_ipv6_disabled_on_compile(self):
        with patch("socket.has_ipv6", False):
            assert not _has_ipv6("::1")

    def test_has_ipv6_enabled_but_fails(self):
        with patch("socket.has_ipv6", True):
            with patch("socket.socket") as mock:
                instance = mock.return_value
                instance.bind = Mock(side_effect=Exception("No IPv6 here!"))
                assert not _has_ipv6("::1")

    def test_has_ipv6_enabled_and_working(self):
        with patch("socket.has_ipv6", True):
            with patch("socket.socket") as mock:
                instance = mock.return_value
                instance.bind.return_value = True
                assert _has_ipv6("::1")

    def test_ip_family_ipv6_enabled(self):
        with patch("hip.util.connection.HAS_IPV6", True):
            assert allowed_gai_family() == socket.AF_UNSPEC

    def test_ip_family_ipv6_disabled(self):
        with patch("hip.util.connection.HAS_IPV6", False):
            assert allowed_gai_family() == socket.AF_INET

    @pytest.mark.parametrize("value", ["-1", "+1", "1.0", six.u("\xb2")])  # \xb2 = ^2
    def test_parse_retry_after_invalid(self, value):
        retry = Retry()
        with pytest.raises(InvalidHeader):
            retry.parse_retry_after(value)

    @pytest.mark.parametrize(
        "value, expected", [("0", 0), ("1000", 1000), ("\t42 ", 42)]
    )
    def test_parse_retry_after(self, value, expected):
        retry = Retry()
        assert retry.parse_retry_after(value) == expected
