"""Default-deny network guard for the brand confirmation run.

Install this before any product import. A fake API key is not isolation: non-loopback
connects are refused, and the balance probe is replaced with a loopback stand-in.
"""
from __future__ import annotations

import socket
import urllib.request
from urllib.parse import urlparse

ALLOW = {"loopback": False}
REAL_CONNECTS: list[str] = []
PROBE_URLS: list[str] = []
INSTALLED = {"yes": False}


class NetBlocked(OSError):
    pass


def _host(address) -> str:
    if isinstance(address, tuple) and address:
        return str(address[0])
    return str(address)


def _loopback(host: str) -> bool:
    host = host.strip("[]").lower()
    return host in {"127.0.0.1", "::1", "localhost"} or host.startswith("127.")


def install() -> None:
    if INSTALLED["yes"]:
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create = socket.create_connection
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        host = _host(address)
        if not _loopback(host) or not ALLOW["loopback"]:
            raise NetBlocked("non-loopback connect refused: " + host)
        REAL_CONNECTS.append(host)
        return real_connect(self, address)

    def guarded_connect_ex(self, address):
        host = _host(address)
        if not _loopback(host) or not ALLOW["loopback"]:
            raise NetBlocked("non-loopback connect_ex refused: " + host)
        REAL_CONNECTS.append(host)
        return real_connect_ex(self, address)

    def guarded_create(address, timeout=None, source_address=None):
        host = _host(address)
        if not _loopback(host) or not ALLOW["loopback"]:
            raise NetBlocked("non-loopback create_connection refused: " + host)
        REAL_CONNECTS.append(host)
        return real_create(address, timeout, source_address)

    def guarded_getaddrinfo(host, port, *args, **kwargs):
        if not _loopback(str(host)) or not ALLOW["loopback"]:
            raise NetBlocked("non-loopback dns refused: " + str(host))
        return real_getaddrinfo(host, port, *args, **kwargs)

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"code":200,"data":{"balance":0}}'

    def fake_urlopen(req, timeout=None, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        PROBE_URLS.append(url)
        host = urlparse(url).hostname or ""
        if not _loopback(host):
            raise NetBlocked("balance probe refused non-loopback: " + host)
        return _FakeResponse()

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex
    socket.create_connection = guarded_create
    socket.getaddrinfo = guarded_getaddrinfo
    urllib.request.urlopen = fake_urlopen
    INSTALLED["yes"] = True


def self_check() -> dict:
    """Predicate checks only. Does not open a real socket."""
    refused = []
    for target in ("api.wavespeed.ai", "1.1.1.1", "8.8.8.8"):
        try:
            socket.socket.connect(object(), (target, 443))
            refused.append({"target": target, "refused": False})
        except NetBlocked:
            refused.append({"target": target, "refused": True})
    loopback_held = False
    try:
        socket.socket.connect(object(), ("127.0.0.1", 9))
    except NetBlocked:
        loopback_held = True
    return {
        "real_connects": list(REAL_CONNECTS),
        "probe_urls": list(PROBE_URLS),
        "non_loopback": refused,
        "loopback_held": loopback_held,
        "ok": (
            not REAL_CONNECTS
            and not PROBE_URLS
            and loopback_held
            and all(row["refused"] for row in refused)
        ),
    }
