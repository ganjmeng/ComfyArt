"""One guard object for the HTTP wrapper, the connector, and the socket audit hook.

Installing the audit hook is permanent in the calling process. Tests do that
only in a subprocess. Nothing here resolves DNS or connects to a remote host.
"""
from __future__ import annotations

import socket
import sys

import aiohappyeyeballs
import aiohttp

from tools.protection_v3.wrapper import controlled_price_request, network_audit, open_controlled_socket


class SharedGuard:
    def __init__(self, guard):
        self.guard = guard
        self.guard_id = id(guard)
        self.http_guard_ids = []
        self.connector_guard_ids = []
        self.audit_guard_ids = []
        self.sockets = []
        self.observe = None
        self.attempts = []
        self.price_reply = {"code": 200, "data": {"discounted_price": 0.1, "price": 0.2}}
        self._request = None
        self._start_connection = None
        self._getaddrinfo = None

    def block_dns(self):
        if self._getaddrinfo is not None:
            return

        def _denied(*_args, **_kwargs):
            raise PermissionError("dns_denied")

        self._getaddrinfo = socket.getaddrinfo
        socket.getaddrinfo = _denied

    def restore_dns(self):
        if self._getaddrinfo is not None:
            socket.getaddrinfo = self._getaddrinfo
            self._getaddrinfo = None

    def install_connector(self):
        """Replace happy-eyeballs connect with the shared factory. No sock_connect."""
        if self._start_connection is not None:
            return
        guard = self.guard
        owner = self
        original = aiohappyeyeballs.start_connection

        async def controlled_start_connection(addr_infos, **kwargs):
            owner.connector_guard_ids.append(id(guard))
            scope = guard._PRICE_SCOPE.get()
            if scope is None or not scope.active:
                raise PermissionError("connector outside validated price request")
            kwargs["socket_factory"] = guard.scoped_socket_factory(pair_factory)
            if not addr_infos:
                raise PermissionError("connector target outside price request")
            sock = kwargs["socket_factory"](addr_infos[0])
            owner.sockets.append(sock)
            return sock

        self._start_connection = original
        aiohappyeyeballs.start_connection = controlled_start_connection

    def restore_connector(self):
        if self._start_connection is not None:
            aiohappyeyeballs.start_connection = self._start_connection
            self._start_connection = None

    def install_http(self, price_ips):
        if self._request is not None:
            return
        guard = self.guard
        owner = self
        original = aiohttp.ClientSession._request

        async def intercepted(session, method, url, **kwargs):
            owner.http_guard_ids.append(id(guard))
            owner.attempts.append((str(method).upper(), str(url), kwargs.get("json")))

            async def transport(_session, bound_method, bound_url, request_kwargs, bound_guard):
                if bound_guard is not guard:
                    raise RuntimeError("http guard is not the shared guard")
                addr = (sorted(price_ips)[0], 443)
                addr_info = (socket.AF_INET, socket.SOCK_STREAM, 0, "", addr)
                await aiohappyeyeballs.start_connection([addr_info])
                sock = owner.sockets[-1]
                if owner.observe is not None:
                    await owner.observe(bound_method, bound_url, request_kwargs, bound_guard, sock)
                return await _response_for(bound_method, bound_url, request_kwargs, owner.price_reply)

            return await controlled_price_request(
                session, method, url, kwargs, guard=guard, transport=transport, price_ips=price_ips,
            )

        self._request = original
        aiohttp.ClientSession._request = intercepted

    def restore_http(self):
        if self._request is not None:
            aiohttp.ClientSession._request = self._request
            self._request = None

    def install_audit_hook(self):
        """Permanent for this process. The hook closes over this guard only."""
        guard = self.guard
        owner = self

        def audit(event, args):
            if event != "socket.connect":
                return
            owner.audit_guard_ids.append(id(guard))
            network_audit(guard, event, args)

        sys.addaudithook(audit)


class OfflineResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def json(self, content_type=None):
        return self._payload

    async def read(self):
        import json
        return json.dumps(self._payload).encode()


def pair_factory(_addr_info):
    left, right = socket.socketpair()
    right.close()
    return left


async def _response_for(method, url, _kwargs, price_reply):
    path = str(url).split("?", 1)[0]
    if path.endswith("/api/v3/models") and str(method).upper() == "GET":
        return OfflineResponse(200, {"data": [_CATALOG_MODEL]})
    if path.endswith("/api/v3/model/price") and str(method).upper() == "POST":
        return OfflineResponse(200, price_reply)
    from tools.protection_v3.wrapper import PriceRequestDenied
    raise PriceRequestDenied("offline_path_not_price")


_CATALOG_MODEL = {
    "model_id": "acme/offline-price",
    "base_price": 0.2,
    "api_schema": {"api_schemas": [{"request_schema": {"properties": {
        "prompt": {"type": "string"},
        "resolution": {"type": "string", "enum": ["1k", "2k"], "default": "1k"},
        "quality": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
    }}}]},
}
