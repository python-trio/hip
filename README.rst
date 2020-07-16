Hip
===

.. image:: https://travis-ci.org/python-trio/hip.svg?branch=master
        :alt: Build status on Travis
        :target: https://travis-ci.org/python-trio/hip

.. image:: https://github.com/python-trio/hip/workflows/CI/badge.svg
        :alt: Build status on GitHub Actions
        :target: https://github.com/python-trio/hip/actions

.. image:: https://codecov.io/gh/python-trio/hip/branch/master/graph/badge.svg
        :alt: Coverage Status
        :target: https://codecov.io/gh/python-trio/hip

.. image:: https://img.shields.io/pypi/v/hip.svg?maxAge=86400
        :alt: PyPI version
        :target: https://pypi.org/project/hip

.. image:: https://badges.gitter.im/python-trio/hip.svg
        :alt: Gitter
        :target: https://gitter.im/python-trio/hip

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black

Hip is a new Python HTTP client for everybody. It supports synchronous Python (just like requests does), but also Trio, asyncio and Curio.

.. important:: Hip is still in its early days, use at your own risk! In particular, the async support is still experimental and untested.

Hip is robust as it is based on urllib3 and uses its extensive test suite that was refined over the years. It also shares most urllib3 features:

- Thread safety.
- Connection pooling.
- Client-side SSL/TLS verification.
- File uploads with multipart encoding.
- Helpers for retrying requests and dealing with HTTP redirects.
- Support for gzip, deflate, and brotli encoding.
- Proxy support for HTTP.
- 100% test coverage.

However, we currently do not support SOCKS proxies nor the pyOpenSSL and SecureTransport TLS backends.

Sample code
-----------

Hip is powerful and easy to use:

.. code-block:: python

    >>> import hip
    >>> http = hip.PoolManager()
    >>> r = http.request('GET', 'http://httpbin.org/robots.txt')
    >>> r.status
    200
    >>> r.data
    'User-agent: *\nDisallow: /deny\n'

It also supports async/await:

.. code-block:: python

    import ahip
    import trio

    async def main():
        with ahip.PoolManager() as http:
            r = await http.request("GET", "http://httpbin.org/uuid")
            print("Status:", r.status)  # 200
            print("Data:", r.data) # 'User-agent: *\nDisallow: /deny\n'

    trio.run(main)

Installing
----------

Hip can be installed with `pip <https://pip.pypa.io>`_::

    $ python -m pip install hip

Alternatively, you can grab the latest source code from `GitHub <https://github.com/python-trio/hip>`_::

    $ python -m pip install git+https://github.com/python-trio/hip

    - OR -

    $ git clone git://github.com/python-trio/hip.git
    $ cd hip && python setup.py install

Documentation
-------------

Hip will soon have usage and reference documentation at `hip.readthedocs.io <https://hip.readthedocs.io/en/latest/>`_.


Contributing
------------

Hip happily accepts contributions. Please see our
`contributing documentation <https://hip.readthedocs.io/en/latest/contributing.html>`_
for some tips on getting started.
