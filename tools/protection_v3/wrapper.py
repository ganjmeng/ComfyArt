"""One WaveSpeed price request, then revocation.

This is the strict bootstrap's request wrapper without DNS, without a quote
probe, and without a server. The scope ends in ``finally`` after success, a
transport exception, or cancellation of this task. Quote-card Cancel is a
different lifecycle and is not called from here.
"""
from __future__ import annotations

from tools.protection_v3.guard_loader import load_frozen_guard


class PriceRequestDenied(PermissionError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def open_controlled_socket(guard, addr_info, original_factory):
    """Register one socket on the current price scope. The factory must not dial out."""
    factory = guard.scoped_socket_factory(original_factory)
    return factory(addr_info)


def network_audit(guard, event, args):
    """Same decision as the strict audit hook. This function does not install the hook."""
    if event != "socket.connect":
        return
    address = args[1]
    if not isinstance(address, tuple):
        raise PermissionError("controlled network: no Unix socket outbound")
    if guard.price_socket_allowed(args[0], address):
        return
    raise PermissionError("controlled network: target not allowlisted")


async def controlled_price_request(session, method, url, kwargs, *, guard=None, transport, price_ips):
    """Run ``transport`` inside one price scope and always end that scope.

    ``price_ips`` is caller configuration. This function does not resolve DNS.
    ``transport`` is the stand-in for ``ClientSession._request``; tests pass a
    local socketpair transport.
    """
    if guard is None:
        guard = load_frozen_guard()
    if kwargs is None:
        kwargs = {}
    allowed, reason, _info = guard.request_allowed(method, url, kwargs)
    if not allowed:
        raise PriceRequestDenied(reason)
    transport_ok, transport_reason = guard.transport_options_allowed(session, kwargs)
    if not transport_ok:
        raise PriceRequestDenied(transport_reason)
    if not isinstance(price_ips, (set, frozenset)) or not price_ips or not all(type(ip) is str and ip for ip in price_ips):
        raise PriceRequestDenied("price_ips_missing")
    request_kwargs = dict(kwargs)
    request_kwargs["allow_redirects"] = False
    scope, token = guard.begin_price_request(set(price_ips))
    try:
        return await transport(session, method, url, request_kwargs, guard)
    finally:
        guard.end_price_request(scope, token)
