Advanced Usage
==============

.. currentmodule:: hip


Customizing Pool Behavior
-------------------------

The :class:`~poolmanager.PoolManager` class automatically handles creating
:class:`~connectionpool.ConnectionPool` instances for each host as needed. By
default, it will keep a maximum of 10 :class:`~connectionpool.ConnectionPool`
instances. If you're making requests to many different hosts it might improve
performance to increase this number::

    >>> import hip
    >>> http = hip.PoolManager(num_pools=50)

However, keep in mind that this does increase memory and socket consumption.

Similarly, the :class:`~connectionpool.ConnectionPool` class keeps a pool
of individual :class:`~connection.HTTPConnection` instances. These connections
are used during an individual request and returned to the pool when the request
is complete. By default only one connection will be saved for re-use. If you
are making many requests to the same host simultaneously it might improve
performance to increase this number::

    >>> import hip
    >>> http = hip.PoolManager(maxsize=10)
    # Alternatively
    >>> http = hip.HTTPConnectionPool('google.com', maxsize=10)

The behavior of the pooling for :class:`~connectionpool.ConnectionPool` is
different from :class:`~poolmanager.PoolManager`. By default, if a new
request is made and there is no free connection in the pool then a new
connection will be created. However, this connection will not be saved if more
than ``maxsize`` connections exist. This means that ``maxsize`` does not
determine the maximum number of connections that can be open to a particular
host, just the maximum number of connections to keep in the pool. However, if you specify ``block=True`` then there can be at most ``maxsize`` connections
open to a particular host::

    >>> http = hip.PoolManager(maxsize=10, block=True)
    # Alternatively
    >>> http = hip.HTTPConnectionPool('google.com', maxsize=10, block=True)

Any new requests will block until a connection is available from the pool.
This is a great way to prevent flooding a host with too many connections in
multi-threaded applications.

.. _stream:

Streaming and IO
----------------

When dealing with large responses it's often better to stream the response
content::

    >>> import hip
    >>> http = hip.PoolManager()
    >>> r = http.request(
    ...     'GET',
    ...     'http://httpbin.org/bytes/1024',
    ...     preload_content=False)
    >>> for chunk in r.stream(32):
    ...     print(chunk)
    b'...'
    b'...'
    ...
    >>> r.release_conn()

Setting ``preload_content`` to ``False`` means that Hip will stream the
response content. :meth:`~response.HTTPResponse.stream` lets you iterate over
chunks of the response content.

.. note:: When using ``preload_content=False``, you should call 
    :meth:`~response.HTTPResponse.release_conn` to release the http connection
    back to the connection pool so that it can be re-used.

However, you can also treat the :class:`~response.HTTPResponse` instance as
a file-like object. This allows you to do buffering::

    >>> r = http.request(
    ...     'GET',
    ...     'http://httpbin.org/bytes/1024',
    ...     preload_content=False)
    >>> r.read(4)
    b'\x88\x1f\x8b\xe5'

Calls to :meth:`~response.HTTPResponse.read()` will block until more response
data is available. 

    >>> import io
    >>> reader = io.BufferedReader(r, 8)
    >>> reader.read(4)
    >>> r.release_conn()

You can use this file-like object to do things like decode the content using
:mod:`codecs`::

    >>> import codecs
    >>> reader = codecs.getreader('utf-8')
    >>> r = http.request(
    ...     'GET',
    ...     'http://httpbin.org/ip',
    ...     preload_content=False)
    >>> json.load(reader(r))
    {'origin': '127.0.0.1'}
    >>> r.release_conn()

.. _proxies:

Proxies
-------

You can use :class:`~poolmanager.ProxyManager` to tunnel requests through an
HTTP proxy::

    >>> import hip
    >>> proxy = hip.ProxyManager('http://localhost:3128/')
    >>> proxy.request('GET', 'http://google.com/')

The usage of :class:`~poolmanager.ProxyManager` is the same as
:class:`~poolmanager.PoolManager`.

You can use :class:`~contrib.socks.SOCKSProxyManager` to connect to SOCKS4 or
SOCKS5 proxies. In order to use SOCKS proxies you will need to install
`PySocks <https://pypi.org/project/PySocks/>`_ or install hip with the
``socks`` extra::

    python -m pip install hip[socks]

Once PySocks is installed, you can use
:class:`~contrib.socks.SOCKSProxyManager`::

    >>> from hip.contrib.socks import SOCKSProxyManager
    >>> proxy = SOCKSProxyManager('socks5://localhost:8889/')
    >>> proxy.request('GET', 'http://google.com/')


.. _ssl_custom:

Custom SSL Certificates
-----------------------

Instead of using `certifi <https://certifi.io/>`_ you can provide your
own certificate authority bundle. This is useful for cases where you've
generated your own certificates or when you're using a private certificate
authority. Just provide the full path to the certificate bundle when creating a
:class:`~poolmanager.PoolManager`::

    >>> import hip
    >>> http = hip.PoolManager(
    ...     cert_reqs='CERT_REQUIRED',
    ...     ca_certs='/path/to/your/certificate_bundle')

When you specify your own certificate bundle only requests that can be
verified with that bundle will succeed. It's recommended to use a separate
:class:`~poolmanager.PoolManager` to make requests to URLs that do not need
the custom certificate.

.. _ssl_client:

Client Certificates
-------------------

You can also specify a client certificate. This is useful when both the server
and the client need to verify each other's identity. Typically these
certificates are issued from the same authority. To use a client certificate,
provide the full path when creating a :class:`~poolmanager.PoolManager`::

    >>> http = hip.PoolManager(
    ...     cert_file='/path/to/your/client_cert.pem',
    ...     cert_reqs='CERT_REQUIRED',
    ...     ca_certs='/path/to/your/certificate_bundle')

If you have an encrypted client certificate private key you can use
the ``key_password`` parameter to specify a password to decrypt the key. ::

    >>> http = hip.PoolManager(
    ...     cert_file='/path/to/your/client_cert.pem',
    ...     cert_reqs='CERT_REQUIRED',
    ...     key_file='/path/to/your/client.key',
    ...     key_password='keyfile_password')

If your key isn't encrypted the ``key_password`` parameter isn't required.

.. _ssl_mac:

Certificate Validation and macOS
--------------------------------

Apple-provided Python and OpenSSL libraries contain a patches that make them
automatically check the system keychain's certificates. This can be
surprising if you specify custom certificates and see requests unexpectedly
succeed. For example, if you are specifying your own certificate for validation
and the server presents a different certificate you would expect the connection
to fail. However, if that server presents a certificate that is in the system
keychain then the connection will succeed.

`This article <https://hynek.me/articles/apple-openssl-verification-surprises/>`_
has more in-depth analysis and explanation.

.. _ssl_warnings:

SSL Warnings
------------

Hip will issue several different warnings based on the level of certificate
verification support. These warnings indicate particular situations and can
be resolved in different ways.

* :class:`~exceptions.InsecureRequestWarning`
    This happens when a request is made to an HTTPS URL without certificate
    verification enabled. Follow the :ref:`certificate verification <ssl>`
    guide to resolve this warning.
* :class:`~exceptions.InsecurePlatformWarning`
    This happens on Python 2 platforms that have an outdated :mod:`ssl` module.
    These older :mod:`ssl` modules can cause some insecure requests to succeed
    where they should fail and secure requests to fail where they should
    succeed.

.. _sni_warning:

* :class:`~exceptions.SNIMissingWarning`
    This happens on Python 2 versions older than 2.7.9. These older versions
    lack `SNI <https://en.wikipedia.org/wiki/Server_Name_Indication>`_ support.
    This can cause servers to present a certificate that the client thinks is
    invalid.

.. _disable_ssl_warnings:

Making unverified HTTPS requests is **strongly** discouraged, however, if you
understand the risks and wish to disable these warnings, you can use :func:`~hip.disable_warnings`::

    >>> import hip
    >>> hip.disable_warnings()

Alternatively you can capture the warnings with the standard :mod:`logging` module::

    >>> logging.captureWarnings(True)

Finally, you can suppress the warnings at the interpreter level by setting the
``PYTHONWARNINGS`` environment variable or by using the
`-W flag <https://docs.python.org/3/using/cmdline.html#cmdoption-w>`_.

Brotli Encoding
---------------

Brotli is a compression algorithm created by Google with better compression
than gzip and deflate and is supported by Hip if the
`brotlipy <https://github.com/python-hyper/brotlipy>`_ package is installed.
You may also request the package be installed via the ``hip[brotli]`` extra::

    python -m pip install hip[brotli]

Here's an example using brotli encoding via the ``Accept-Encoding`` header::

    >>> from hip import PoolManager
    >>> http = PoolManager()
    >>> http.request('GET', 'https://www.google.com/', headers={'Accept-Encoding': 'br'})
