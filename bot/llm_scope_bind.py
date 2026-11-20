"""In-process signal that an authorized validation ledger is bound.

``use_authorized_scope`` publishes the path here. Ordinary product reads this
flag and does not import the USD gate or runtime activation. This is not a
product setting, a ledger file, or a runtime id.
"""
from __future__ import annotations

_path: str | None = None


def bind_scope(path: str) -> None:
    global _path
    _path = path


def clear_scope() -> None:
    global _path
    _path = None


def bound_scope_path() -> str | None:
    return _path


def scope_is_bound() -> bool:
    return _path is not None
