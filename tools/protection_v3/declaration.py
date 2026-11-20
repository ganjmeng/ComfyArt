"""Explicit source, home, port, and runtime-id declaration.

A declaration is not activation. This module does not create a home, bind a
port, write a ledger, or record an authorization.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from bot.llm_aux_context import canonical_digest
from tools.protection_v3.constants import (
    CREDENTIAL_ENV,
    DELIVERY_GIT,
    LOGICAL_GIT,
    LOGICAL_SOURCE,
    OLD_HOMES,
    OLD_STRICT_GIT,
    OLD_STRICT_SOURCE,
    OLD_V3_GIT,
    PROBE_ENV_FLAGS,
    RETIRED_PORTS,
)

_RUNTIME_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


class DeclarationError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AuthorizationMissing(DeclarationError):
    def __init__(self):
        super().__init__("authorization_missing")


@dataclass(frozen=True)
class Declaration:
    source_git: str
    source_sha256: str
    home: str
    port: int
    runtime_id: str
    fingerprint: str
    activated: bool = False


def _require_text(value, code: str) -> str:
    if type(value) is not str or not value.strip():
        raise DeclarationError(code)
    return value.strip()


def declare(*, source_git, source_sha256, home, port, runtime_id) -> Declaration:
    """Check the caller-supplied identity. Does not look at the live git HEAD."""
    git = _require_text(source_git, "missing_source_git")
    source = _require_text(source_sha256, "missing_source_sha256")
    home_text = _require_text(home, "missing_home")
    runtime = _require_text(runtime_id, "missing_runtime_id")
    if type(port) is not int:
        raise DeclarationError("missing_port")
    if git in DELIVERY_GIT:
        raise DeclarationError("delivery_commit_is_not_logical_source")
    if git == OLD_STRICT_GIT or source == OLD_STRICT_SOURCE:
        raise DeclarationError("old_strict_tree")
    if git == OLD_V3_GIT:
        raise DeclarationError("old_v3_tree")
    if git != LOGICAL_GIT or source != LOGICAL_SOURCE:
        raise DeclarationError("logical_source_mismatch")
    if not os.path.isabs(home_text):
        raise DeclarationError("home_not_absolute")
    if any(home_text == old or home_text.startswith(old + "/") for old in OLD_HOMES):
        raise DeclarationError("old_home")
    if port < 1 or port > 65535:
        raise DeclarationError("port_out_of_range")
    if port in RETIRED_PORTS:
        raise DeclarationError("retired_port")
    if _RUNTIME_ID.fullmatch(runtime) is None:
        raise DeclarationError("runtime_id_invalid")
    fingerprint = canonical_digest({
        "home": home_text,
        "runtime_id": runtime,
        "source_sha256": source,
    })
    return Declaration(git, source, home_text, port, runtime, fingerprint, False)


def reject_probe_and_credentials(env: dict) -> None:
    """Fail closed. Does not read the values into a child environment."""
    for name in PROBE_ENV_FLAGS:
        if env.get(name):
            raise DeclarationError("probe_disabled")
    for name in CREDENTIAL_ENV:
        if env.get(name):
            raise DeclarationError("credential_not_transferred")


def require_authorization(authorization_id) -> None:
    """No authorization is stored here. Any call fails closed, including a non-empty id."""
    if type(authorization_id) is not str or not authorization_id.strip():
        raise AuthorizationMissing()
    raise DeclarationError("authorization_not_recorded")
