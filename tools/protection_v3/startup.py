"""Offline product entry for the main tree.

A synthetic test authorization may call the injected startup, which is how
tests reach quote_detail. The real ComfyUI runner is not approved and is not
called. This module does not write an authorization, a ledger, or a directory.
"""
from __future__ import annotations

import hashlib
import runpy
from dataclasses import dataclass
from pathlib import Path

from tools.protection_v3.constants import LOGICAL_GIT, LOGICAL_SOURCE
from tools.protection_v3.declaration import AuthorizationMissing, Declaration, DeclarationError, declare
from tools.protection_v3.guard_loader import load_frozen_guard
from tools.protection_v3.wiring import SharedGuard


class StartupRefused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Prepared:
    declaration: Declaration
    source_path: str
    ready_record: None = None


def source_digest(source_path: str) -> str:
    root = Path(source_path)
    if not root.is_dir():
        raise DeclarationError("source_path_missing")
    digest = hashlib.sha256()
    files = [root / "__init__.py"]
    for folder in ("api", "bot"):
        files.extend((root / folder).rglob("*.py"))
    for path in sorted(files):
        if path.is_file():
            relative = str(path.relative_to(root))
            digest.update(relative.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def preflight(*, source_git, source_sha256, source_path, home, port, runtime_id) -> Prepared:
    if type(source_path) is not str or not source_path.strip():
        raise DeclarationError("missing_source_path")
    declared = declare(
        source_git=source_git, source_sha256=source_sha256, home=home,
        port=port, runtime_id=runtime_id,
    )
    actual = source_digest(source_path)
    if actual != LOGICAL_SOURCE or actual != declared.source_sha256 or declared.source_git != LOGICAL_GIT:
        raise DeclarationError("source_digest_mismatch")
    return Prepared(declared, source_path, None)


def synthetic_test_authorization(prepared: Prepared) -> dict:
    declared = prepared.declaration
    return {
        "version": 1,
        "kind": "synthetic_test_only",
        "authorization_id": "synthetic-quote-only-not-installed",
        "logical_git": declared.source_git,
        "source_sha256": declared.source_sha256,
        "runtime_id": declared.runtime_id,
        "home": declared.home,
        "port": declared.port,
        "paid_activation": False,
        "llm_denied": True,
        "probe": False,
        "ledger_mutation": False,
        "tech_pm_approved": False,
    }


def validate_authorization(authorization, prepared: Prepared) -> str:
    if authorization is None:
        raise AuthorizationMissing()
    if type(authorization) is not dict or authorization.get("tech_pm_approved") is True:
        raise DeclarationError("approval_not_recorded")
    if authorization.get("kind") != "synthetic_test_only":
        raise DeclarationError("authorization_not_recorded")
    declared = prepared.declaration
    expected = {
        "version": 1,
        "authorization_id": "synthetic-quote-only-not-installed",
        "logical_git": LOGICAL_GIT,
        "source_sha256": LOGICAL_SOURCE,
        "runtime_id": declared.runtime_id,
        "home": declared.home,
        "port": declared.port,
        "paid_activation": False,
        "llm_denied": True,
        "probe": False,
        "ledger_mutation": False,
    }
    for key, value in expected.items():
        if authorization.get(key) != value:
            raise DeclarationError("authorization_not_recorded")
    return "synthetic_test_only"


def build_server_argv(prepared: Prepared) -> list[str]:
    home = Path(prepared.declaration.home)
    return [
        "ComfyUI/main.py",
        "--listen", "127.0.0.1",
        "--port", str(prepared.declaration.port),
        "--disable-auto-launch",
        "--offline",
        "--user-directory", str(home / "comfyui-user"),
    ]


def approval_recorded(_prepared: Prepared) -> bool:
    return False


def production_startup(prepared: Prepared, *, runner=None):
    """Server argv exists. The runner is not called: no Tech/PM approval is stored."""
    argv = build_server_argv(prepared)
    if not approval_recorded(prepared) or prepared.ready_record is not None:
        raise StartupRefused("tech_pm_approval_required")
    return (runner if runner is not None else runpy.run_path)(argv[0], run_name="__main__")


async def connect_product(prepared, authorization, *, startup, price_ips, guard=None, install_audit=False):
    """Validate first. A bad authorization never calls startup.

    A synthetic authorization calls startup. Tests pass an offline startup that
    exercises quote_detail through the shared guard. This does not start ComfyUI.
    """
    if startup is None:
        raise StartupRefused("startup_missing")
    validate_authorization(authorization, prepared)
    if startup is production_startup:
        return production_startup(prepared)
    if guard is None:
        guard = load_frozen_guard()
    shared = SharedGuard(guard)
    shared.block_dns()
    shared.install_connector()
    shared.install_http(price_ips)
    if install_audit:
        shared.install_audit_hook()
    try:
        result = await startup(prepared, shared)
        return result, shared
    finally:
        shared.restore_http()
        shared.restore_connector()
        shared.restore_dns()
