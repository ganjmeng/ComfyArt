"""Allowlist for a controlled bootstrap WaveSpeed pricing window.

Only https://api.wavespeed.ai:443
  GET  /api/v3/models
  POST /api/v3/model/price
The price body is a JSON object. This guard does not accept or reject a tree
by the field name `input` or `inputs`. main 72f387a8 is rejected by source
digest and label, not here. Socket connects to resolved IPs of that host are
permitted only after a request has already passed this guard. This module
does no I/O of its own.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

WAVESPEED_HOST = 'api.wavespeed.ai'
WAVESPEED_PORT = 443
PATH_MODELS = '/api/v3/models'
PATH_PRICE = '/api/v3/model/price'
ALLOWED_PATHS = {PATH_MODELS, PATH_PRICE}

# Denied examples used in docs/tests (never called for real in offline proof).
DENIED_PATHS = (
    '/api/v3/balance',
    '/api/v3/media/upload/binary',
    '/api/v3/predictions/x/result',
    '/api/v3/wavespeed-ai/z-image/turbo',  # submit
    '/api/v3/model/price/extra',
    '/api/v3/models/',
    '/api/v3/models/foo',
    '/api/v3/./models',
    '/api/v3/model/price/',
)


def _port(p) -> int:
    if p.port:
        return p.port
    if p.scheme == 'https':
        return 443
    if p.scheme == 'http':
        return 80
    return -1


def classify_url(url) -> dict:
    """Parse and classify a URL. Never opens a socket."""
    p = urlsplit(str(url))
    info = {
        'scheme': p.scheme,
        'netloc': p.netloc,
        'hostname': p.hostname,
        'port': _port(p),
        'path': p.path,
        'query': p.query,
        'fragment': p.fragment,
        'username': p.username,
        'password': p.password,
    }
    reasons = []
    if p.scheme != 'https':
        reasons.append('scheme')
    if p.username is not None or p.password is not None:
        reasons.append('userinfo')
    if p.hostname != WAVESPEED_HOST:
        reasons.append('host')
    if _port(p) != WAVESPEED_PORT:
        reasons.append('port')
    if p.query:
        reasons.append('query')
    if p.fragment:
        reasons.append('fragment')
    if p.path not in ALLOWED_PATHS:
        reasons.append('path')
    info['official'] = not reasons
    info['deny_reasons'] = reasons
    return info


def method_allowed(method: str, path: str) -> bool:
    m = (method or '').upper()
    if path == PATH_MODELS and m == 'GET':
        return True
    if path == PATH_PRICE and m == 'POST':
        return True
    return False


def _extract_body(kwargs: dict):
    if kwargs.get('json') is not None and kwargs.get('data') not in (None, b'', ''):
        return None, 'json_and_data'
    if kwargs.get('json') is not None:
        raw = kwargs.get('json')
        if type(raw) is not dict:
            return None, 'json_not_object'
        return raw, None
    data = kwargs.get('data')
    if data is None:
        return None, 'missing_body'
    if type(data) is not bytes:
        return None, 'data_not_bytes'
    try:
        raw = json.loads(data)
    except (ValueError, TypeError, UnicodeDecodeError):
        return None, 'data_not_json'
    if type(raw) is not dict:
        return None, 'data_json_not_object'
    return raw, None


def price_body_allowed(kwargs: dict) -> tuple[bool, str]:
    """POST /api/v3/model/price accepts a JSON object.

    `input` and `inputs` are not inspected. A plural body is the same shape
    main 72f387a8 sends, and that tree is refused by digest and label instead.
    """
    _body, err = _extract_body(kwargs)
    if err:
        return False, err
    return True, 'ok'


def get_models_kwargs_allowed(kwargs: dict) -> tuple[bool, str]:
    if kwargs.get('json') is not None or kwargs.get('data') not in (None, b'', ''):
        return False, 'get_has_body'
    return True, 'ok'


def request_allowed(method: str, url, kwargs: dict | None = None) -> tuple[bool, str, dict]:
    """Single decision for an aiohttp-style request. Does not perform I/O."""
    kwargs = kwargs or {}
    info = classify_url(url)
    if not info['official']:
        return False, 'url:' + '+'.join(info['deny_reasons']), info
    if not method_allowed(method, info['path']):
        return False, 'method_path', info
    if info['path'] == PATH_MODELS:
        ok, reason = get_models_kwargs_allowed(kwargs)
        return ok, reason if not ok else 'allow_get_models', info
    ok, reason = price_body_allowed(kwargs)
    return ok, reason if not ok else 'allow_post_price', info


def socket_connect_allowed(address, *, wavespeed_ips: set, official_ips: set,
                           local_port: int = 8931) -> tuple[bool, str]:
    """Second line of defense. IPs must already have been filled by a passed HTTP guard."""
    if not isinstance(address, tuple):
        return False, 'socket_unix'
    host, port = address[:2]
    if host in ('127.0.0.1', '::1') and port == local_port:
        return True, 'local'
    if port == 443 and host in official_ips:
        return True, 'official_ip'
    if port == 443 and host in wavespeed_ips:
        return True, 'wavespeed_ip'
    return False, 'socket_not_allowlisted'


def transport_options_allowed(session, kwargs):
    """Reject request/session transport overrides before DNS or transmission."""
    if kwargs.get('params') or getattr(session, '_default_params', None):
        return False, 'transport_params'
    for name in ('server_hostname', 'proxy', 'proxy_auth', 'proxy_headers',
                 'ssl_context', 'verify_ssl', 'fingerprint'):
        if name in kwargs:
            return False, 'transport_' + name
    if 'ssl' in kwargs and kwargs['ssl'] is not True:
        return False, 'transport_ssl'
    for headers in (kwargs.get('headers'), getattr(session, '_default_headers', None)):
        if headers is None:
            continue
        try:
            pairs = headers.items() if hasattr(headers, 'items') else headers
            if any(str(k).lower() in {'host', ':authority', 'proxy-authorization'} for k, v in pairs):
                return False, 'transport_host_or_proxy_header'
        except (TypeError, ValueError):
            return False, 'transport_invalid_headers'
    if getattr(session, 'trust_env', False):
        return False, 'transport_trust_env'
    for name in ('_default_proxy', '_default_proxy_auth'):
        if getattr(session, name, None) is not None:
            return False, 'transport_session' + name
    connector = getattr(session, '_connector', None)
    if connector is not None and getattr(connector, '_ssl', True) is not True:
        return False, 'transport_connector_ssl'
    if connector is not None and getattr(connector, '_socket_factory', None) is not None:
        return False, 'transport_socket_factory'
    return True, 'transport_default'


# Request lifetime AND exact connector-created socket are required. A ContextVar
# alone would leak permission to arbitrary child tasks through context copying.
import asyncio
import contextvars
import socket as _socket
import weakref
_PRICE_SCOPE = contextvars.ContextVar('controlled_price_scope', default=None)
_PRICE_SOCKETS = weakref.WeakKeyDictionary()

class PriceScope:
    def __init__(self, ips):
        self.ips = frozenset(ips)
        self.owner = asyncio.current_task()
        self.active = True
        self.sockets = []

def begin_price_request(ips):
    scope = PriceScope(ips)
    return scope, _PRICE_SCOPE.set(scope)

def end_price_request(scope, token):
    scope.active = False
    for sock in scope.sockets:
        _PRICE_SOCKETS.pop(sock, None)
    scope.sockets.clear()
    _PRICE_SCOPE.reset(token)

def scoped_socket_factory(original_factory=None):
    scope = _PRICE_SCOPE.get()
    if scope is None or not scope.active or asyncio.current_task() is not scope.owner:
        raise PermissionError('connector outside validated price request')
    def factory(addr_info):
        if not scope.active or addr_info[4][0] not in scope.ips or addr_info[4][1] != 443:
            raise PermissionError('connector target outside price request')
        sock = original_factory(addr_info) if original_factory else _socket.socket(*addr_info[:3])
        _PRICE_SOCKETS[sock] = scope
        scope.sockets.append(sock)
        return sock
    return factory

def price_socket_allowed(sock, address):
    if not isinstance(address, tuple) or len(address) < 2:
        return False
    scope = _PRICE_SOCKETS.get(sock) if sock is not None else None
    return (scope is not None and scope.active and _PRICE_SCOPE.get() is scope
            and address[1] == 443 and address[0] in scope.ips)
