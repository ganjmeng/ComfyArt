"""Request-local auxiliary designation.

Ordinary HTTP reads this context. Importing this module does not hash source,
take a POSIX lock, open a ledger, or import the validation gate.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from contextvars import ContextVar

_AUXILIARY: ContextVar = ContextVar("llm_designated_auxiliary", default=None)
_AUX_NO_REDIRECT: ContextVar = ContextVar("llm_aux_no_redirect", default=False)


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def canonical_digest(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@contextlib.contextmanager
def auxiliary_request(purpose, method, url, body):
    # Only explicit catalog/MCP helper call sites create this context. A model
    # payload cannot select its own purpose by URL substring or JSON fields.
    token = _AUXILIARY.set((purpose, method, str(url), canonical_digest(body)))
    try:
        yield
    finally:
        _AUXILIARY.reset(token)


@contextlib.contextmanager
def auxiliary_no_redirects():
    token = _AUX_NO_REDIRECT.set(True)
    try:
        yield
    finally:
        _AUX_NO_REDIRECT.reset(token)


def no_auxiliary_redirects() -> bool:
    return _AUX_NO_REDIRECT.get()


def auxiliary_designation() -> bool:
    return _AUXILIARY.get() is not None


def current_auxiliary():
    return _AUXILIARY.get()
