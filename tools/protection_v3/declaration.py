"""Caller-supplied identity. A declaration is not activation and writes nothing."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass

from tools.protection_v3.constants import (
    CREDENTIAL_ENV,
    LOGICAL_GIT,
    LOGICAL_SOURCE,
    OLD_HOMES,
    OLD_STRICT_GIT,
    OLD_STRICT_SOURCE,
    OLD_V3_GIT,
    PROBE_ENV_FLAGS,
    RECOVERY_GIT,
    RECOVERY_SOURCE,
    RETIRED_PORTS,
    STALE_MAIN_GIT,
    STALE_MAIN_SOURCE,
)

_RUNTIME_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


def canonical_digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


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
    git = _require_text(source_git, "missing_source_git")
    source = _require_text(source_sha256, "missing_source_sha256")
    home_text = _require_text(home, "missing_home")
    runtime = _require_text(runtime_id, "missing_runtime_id")
    if type(port) is not int:
        raise DeclarationError("missing_port")
    if git == STALE_MAIN_GIT or source == STALE_MAIN_SOURCE:
        raise DeclarationError("stale_main_source")
    if git in RECOVERY_GIT or source == RECOVERY_SOURCE:
        raise DeclarationError("recovery_tree_is_not_main_product")
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
    if port < 1 or port > 65535 or port in RETIRED_PORTS:
        raise DeclarationError("retired_port" if port in RETIRED_PORTS else "port_out_of_range")
    if _RUNTIME_ID.fullmatch(runtime) is None:
        raise DeclarationError("runtime_id_invalid")
    fingerprint = canonical_digest({
        "home": home_text, "runtime_id": runtime, "source_sha256": source,
    })
    return Declaration(git, source, home_text, port, runtime, fingerprint, False)


def reject_probe_and_credentials(env: dict) -> None:
    for name in PROBE_ENV_FLAGS:
        if env.get(name):
            raise DeclarationError("probe_disabled")
    for name in CREDENTIAL_ENV:
        if env.get(name):
            raise DeclarationError("credential_not_transferred")
