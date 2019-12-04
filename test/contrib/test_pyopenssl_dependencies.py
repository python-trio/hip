# -*- coding: utf-8 -*-
import pytest

from mock import patch, Mock

try:
    from hip.contrib.pyopenssl import inject_into_hip, extract_from_hip
except ImportError:
    pass


def setup_module():
    try:
        from hip.contrib.pyopenssl import inject_into_hip

        inject_into_hip()
    except ImportError as e:
        pytest.skip("Could not import PyOpenSSL: %r" % e)


def teardown_module():
    try:
        from hip.contrib.pyopenssl import extract_from_hip

        extract_from_hip()
    except ImportError:
        pass


class TestPyOpenSSLInjection(object):
    """
    Tests for error handling in pyopenssl's 'inject_into_hip'
    """

    def test_inject_validate_fail_cryptography(self):
        """
        Injection should not be supported if cryptography is too old.
        """
        try:
            with patch("cryptography.x509.extensions.Extensions") as mock:
                del mock.get_extension_for_class
                with pytest.raises(ImportError):
                    inject_into_hip()
        finally:
            # `inject_into_hip` is not supposed to succeed.
            # If it does, this test should fail, but we need to
            # clean up so that subsequent tests are unaffected.
            extract_from_hip()

    def test_inject_validate_fail_pyopenssl(self):
        """
        Injection should not be supported if pyOpenSSL is too old.
        """
        try:
            return_val = Mock()
            del return_val._x509
            with patch("OpenSSL.crypto.X509", return_value=return_val):
                with pytest.raises(ImportError):
                    inject_into_hip()
        finally:
            # `inject_into_hip` is not supposed to succeed.
            # If it does, this test should fail, but we need to
            # clean up so that subsequent tests are unaffected.
            extract_from_hip()
