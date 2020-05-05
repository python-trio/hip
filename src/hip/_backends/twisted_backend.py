import sys
import socket
import OpenSSL.crypto
from cryptography import x509
from cryptography.hazmat.backends.openssl import backend as openssl_backend
from cryptography.hazmat.backends.openssl.x509 import _Certificate
from twisted.internet import protocol, reactor as default_reactor, ssl
from twisted.internet.interfaces import IHandshakeListener
from twisted.internet.endpoints import HostnameEndpoint, connectProtocol
from twisted.internet.defer import (
    Deferred,
    DeferredList,
    CancelledError,
    ensureDeferred,
)
from zope.interface import implementer

from ._common import LoopAbort

try:
    from cryptography.x509 import UnsupportedExtension
except ImportError:
    # UnsupportedExtension is gone in cryptography >= 2.1.0
    class UnsupportedExtension(Exception):
        pass


# XX support connect_timeout and read_timeout


class TwistedBackend:
    def __init__(self, reactor=None):
        self._reactor = reactor or default_reactor

    async def connect(
        self, host, port, connect_timeout, source_address=None, socket_options=None
    ):
        # HostnameEndpoint only supports setting source host, not source port
        if source_address is not None:
            raise NotImplementedError(
                "twisted backend doesn't support setting source_address"
            )

        # factory = protocol.Factory.forProtocol(TwistedSocketProtocol)
        endpoint = HostnameEndpoint(self._reactor, host, port)
        d = connectProtocol(endpoint, TwistedSocketProtocol())
        # XX d.addTimeout(...)
        protocol = await d
        if socket_options is not None:
            for opt in socket_options:
                if opt[:2] == (socket.IPPROTO_TCP, socket.TCP_NODELAY):
                    protocol.transport.setTcpNoDelay(opt[2])
                else:
                    raise NotImplementedError(
                        "unrecognized socket option for twisted backend"
                    )
        return TwistedSocket(protocol)


# enums
class _DATA_RECEIVED:
    pass


class _RESUME_PRODUCING:
    pass


class _HANDSHAKE_COMPLETED:
    pass


@implementer(IHandshakeListener)
class TwistedSocketProtocol(protocol.Protocol):
    def connectionMade(self):
        self._receive_buffer = bytearray()
        self.transport.pauseProducing()

        self.transport.registerProducer(self, True)
        self._producing = True

        self._readable_watch_state_enabled = False
        self._is_readable = False

        self._events = {}

        self._connection_lost = False

    def _signal(self, event):
        if event in self._events:
            # The first thing callback() will do is remove the deferred from
            # self._events (see cleanup() in _wait_for() below).
            self._events[event].callback(None)

    async def _wait_for(self, event):
        assert event not in self._events
        d = Deferred()

        # We might get callbacked, we might get cancelled; either way we want
        # to clean up then pass through the result:
        def cleanup(obj):
            assert self._events[event] is d
            del self._events[event]
            return obj

        d.addBoth(cleanup)

        self._events[event] = d
        await d

    def dataReceived(self, data):
        if self._readable_watch_state_enabled:
            self._is_readable = True
            self.transport.pauseProducing()
            return
        self._receive_buffer += data
        self._signal(_DATA_RECEIVED)

    def connectionLost(self, reason):
        if self._readable_watch_state_enabled:
            self._is_readable = True
            self.transport.pauseProducing()
            return
        self._connection_lost = True
        self._signal(_DATA_RECEIVED)

    def pauseProducing(self):
        self._producing = False

    def resumeProducing(self):
        self._producing = True
        self._signal(_RESUME_PRODUCING)

    def stopProducing(self):
        pass

    def handshakeCompleted(self):
        self._signal(_HANDSHAKE_COMPLETED)

    async def start_tls(self, server_hostname, ssl_context):
        # XX ssl_context?
        self.transport.startTLS(ssl.optionsForClientTLS(server_hostname))
        await self._wait_for(_HANDSHAKE_COMPLETED)

    async def receive_some(self):
        assert not self._readable_watch_state_enabled
        while not self._receive_buffer and not self._connection_lost:
            self.transport.resumeProducing()
            try:
                await self._wait_for(_DATA_RECEIVED)
            finally:
                self.transport.pauseProducing()
        got = self._receive_buffer
        self._receive_buffer = bytearray()
        return got

    async def send_all(self, data):
        assert not self._readable_watch_state_enabled
        while not self._producing:
            await self._wait_for(_RESUME_PRODUCING)
        self.transport.write(data)

    def is_readable(self):
        assert self._readable_watch_state_enabled
        return self._is_readable

    def set_readable_watch_state(self, enabled):
        self._readable_watch_state_enabled = enabled
        if self._readable_watch_state_enabled:
            self.transport.resumeProducing()
        else:
            self.transport.pauseProducing()


class DoubleError(Exception):
    def __init__(self, exc1, exc2):
        self.exc1 = exc1
        self.exc2 = exc2

    def __str__(self):
        return "{}, {}".format(self.exc1, self.exc2)


class TwistedSocket:
    def __init__(self, protocol):
        self._protocol = protocol

    async def start_tls(self, server_hostname, ssl_context):
        await self._protocol.start_tls(server_hostname, ssl_context)

    def getpeercert(self, binary_form=False):
        # Cribbed from urllib3.contrib.pyopenssl.WrappedSocket.getpeercert
        peercert = self._protocol.transport.getPeerCertificate()
        if not peercert:
            return peercert
        if binary_form:
            return OpenSSL.crypto.dump_certificate(
                OpenSSL.crypto.FILETYPE_ASN1, peercert
            )
        return {
            "subject": ((("commonName", peercert.get_subject().CN),),),
            "subjectAltName": get_subj_alt_name(peercert),
        }

    async def receive_some(self):
        return await self._protocol.receive_some()

    async def send_and_receive_for_a_while(
        self, produce_bytes, consume_bytes, read_timeout
    ):
        async def sender():
            while True:
                outgoing = await produce_bytes()
                if outgoing is None:
                    break
                await self._protocol.send_all(outgoing)

        async def receiver():
            while True:
                incoming = await self._protocol.receive_some()
                try:
                    consume_bytes(incoming)
                except LoopAbort:
                    break

        # Run the two async functions concurrently
        send_loop = ensureDeferred(sender())
        receive_loop = ensureDeferred(receiver())

        # If the send_loop errors out, then cancel receive_loop and preserve
        # the failure
        @send_loop.addErrback
        def send_loop_errback(failure):
            receive_loop.cancel()
            return failure

        # If the receive_loop errors out *or* exits cleanly due to LoopAbort,
        # then cancel the send_loop and preserve the result
        @receive_loop.addBoth
        def receive_loop_allback(result):
            send_loop.cancel()
            return result

        # Wait for both to finish, and then figure out if we need to raise an
        # exception.
        results = await DeferredList([send_loop, receive_loop])
        # First, find the failure objects - but since we've almost always
        # cancelled one of the deferreds, which causes it to raise
        # CancelledError, we can't treat these at face value.
        failures = []
        for success, result in results:
            if not success:
                failures.append(result)
        # First, loop over and remove at most 1 CancelledError, since that's
        # the most that we ever generate. (If *we* were cancelled, then there
        # will be 2 CancelledErrors, and that's fine; in that case we want to
        # preserve 1 of them and then re-raise it.)
        for i in range(len(failures)):
            if isinstance(failures[i].value, CancelledError):
                del failures[i]
                break
        # Now whatever's left is what we need to re-raise
        if len(failures) == 0:
            return
        elif len(failures) == 1:
            failures[0].raiseException()
        else:
            raise DoubleError(*failures)

    def forceful_close(self):
        self._protocol.transport.abortConnection()

    def is_readable(self):
        return self._protocol.is_readable()

    def set_readable_watch_state(self, enabled):
        return self._protocol.set_readable_watch_state(enabled)


def get_subj_alt_name(peer_cert):
    """
    Given an PyOpenSSL certificate, provides all the subject alternative names.
    """
    # Pass the cert to cryptography, which has much better APIs for this.
    if hasattr(peer_cert, "to_cryptography"):
        cert = peer_cert.to_cryptography()
    else:
        # This is technically using private APIs, but should work across all
        # relevant versions before PyOpenSSL got a proper API for this.
        cert = _Certificate(openssl_backend, peer_cert._x509)

    # We want to find the SAN extension. Ask Cryptography to locate it (it's
    # faster than looping in Python)
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        # No such extension, return the empty list.
        return []
    except (
        x509.DuplicateExtension,
        UnsupportedExtension,
        x509.UnsupportedGeneralNameType,
        UnicodeError,
    ):
        # A problem has been found with the quality of the certificate. Assume
        # no SAN field is present. TODO: figure out how to signal to the user.
        # log.warning(
        #     "A problem was encountered with the certificate that prevented "
        #     "Hip from finding the SubjectAlternativeName field. This can "
        #     "affect certificate validation. The error was %s",
        #     e,
        # )
        return []

    # We want to return dNSName and iPAddress fields. We need to cast the IPs
    # back to strings because the match_hostname function wants them as
    # strings.
    # Sadly the DNS names need to be idna encoded and then, on Python 3, UTF-8
    # decoded. This is pretty frustrating, but that's what the standard library
    # does with certificates, and so we need to attempt to do the same.
    # We also want to skip over names which cannot be idna encoded.
    names = [
        ("DNS", name)
        for name in map(_dnsname_to_stdlib, ext.get_values_for_type(x509.DNSName))
        if name is not None
    ]
    names.extend(
        ("IP Address", str(name)) for name in ext.get_values_for_type(x509.IPAddress)
    )

    return names


def _dnsname_to_stdlib(name):
    """
    Converts a dNSName SubjectAlternativeName field to the form used by the
    standard library on the given Python version.
    Cryptography produces a dNSName as a unicode string that was idna-decoded
    from ASCII bytes. We need to idna-encode that string to get it back, and
    then on Python 3 we also need to convert to unicode via UTF-8 (the stdlib
    uses PyUnicode_FromStringAndSize on it, which decodes via UTF-8).
    If the name cannot be idna-encoded then we return None signalling that
    the name given should be skipped.
    """

    def idna_encode(name):
        """
        Borrowed wholesale from the Python Cryptography Project. It turns out
        that we can't just safely call `idna.encode`: it can explode for
        wildcard names. This avoids that problem.
        """
        import idna

        try:
            for prefix in [u"*.", u"."]:
                if name.startswith(prefix):
                    name = name[len(prefix) :]
                    return prefix.encode("ascii") + idna.encode(name)
            return idna.encode(name)
        except idna.core.IDNAError:
            return None

    # Don't send IPv6 addresses through the IDNA encoder.
    if ":" in name:
        return name

    name = idna_encode(name)
    if name is None:
        return None
    elif sys.version_info >= (3, 0):
        name = name.decode("utf-8")
    return name
