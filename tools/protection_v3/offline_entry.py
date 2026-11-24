"""Subprocess-only entry. The audit hook cannot be removed, so pytest stays clean.

No DNS and no remote connect. A denied connect raises inside the hook, before
the socket operation. An allowed check uses a closed local socket so the
following operation cannot leave the machine.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import socket
import sys
import types
from pathlib import Path

from tools.protection_v3.constants import LOGICAL_GIT, LOGICAL_SOURCE
from tools.protection_v3.guard_loader import load_frozen_guard
from tools.protection_v3.startup import connect_product, preflight, synthetic_test_authorization

HOME = "/var/lib/comfyart-unactivated/main-72f387a8/home"
RUNTIME = "main-72f387a8-unactivated"
IPS = frozenset({"203.0.113.5"})
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _wavespeed():
    """Load the product package the way the test harness does, without a server."""
    if "ComfyArt.api.wavespeed" in sys.modules:
        return sys.modules["ComfyArt.api.wavespeed"]
    root = Path(ROOT)
    base = Path(os.environ.get("TMPDIR", "/tmp")) / "comfyart-offline-entry"
    for name in ("user", "input", "output", "temp"):
        (base / name).mkdir(parents=True, exist_ok=True)

    def module(name, **attrs):
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[name] = mod
        return mod

    module(
        "folder_paths",
        STATE={"base": base},
        get_user_directory=lambda: str(base / "user"),
        get_input_directory=lambda: str(base / "input"),
        get_output_directory=lambda: str(base / "output"),
        get_temp_directory=lambda: str(base / "temp"),
        get_system_user_directory=lambda name="system": str(base / "user" / f"__{name}"),
        get_directory_by_type=lambda kind: str(base / kind),
    )
    comfy = module("comfy")
    comfy.ops = module("comfy.ops", manual_cast=object)
    comfy.sd = module("comfy.sd", load_diffusion_model=lambda *_a, **_k: None)
    comfy.utils = module("comfy.utils", ProgressBar=lambda _total: types.SimpleNamespace(update=lambda _n: None))
    comfy.model_management = module("comfy.model_management", throw_exception_if_processing_interrupted=lambda: None)
    comfy.cli_args = module("comfy.cli_args", args=types.SimpleNamespace(tls_keyfile=None, tls_certfile=None))
    import aiohttp.web as web
    server = module("server")
    prompt = types.SimpleNamespace(
        instance=None, routes=web.RouteTableDef(), address="127.0.0.1", port=0, sockets={},
    )
    prompt.instance = prompt
    server.PromptServer = type("PromptServer", (), {"instance": prompt})
    os.environ.setdefault("COMFYART_SKIP_KEY_CHECK", "1")
    spec = importlib.util.spec_from_file_location(
        "ComfyArt", root / "__init__.py", submodule_search_locations=[str(root)],
    )
    product = importlib.util.module_from_spec(spec)
    sys.modules["ComfyArt"] = product
    spec.loader.exec_module(product)
    return sys.modules["ComfyArt.api.wavespeed"]


def _prepared():
    return preflight(
        source_git=LOGICAL_GIT, source_sha256=LOGICAL_SOURCE, source_path=ROOT,
        home=HOME, port=8946, runtime_id=RUNTIME,
    )


async def _main():
    guard = load_frozen_guard()
    report = {"guard_id": id(guard), "dns": False}
    os.environ["WAVESPEED_API_KEY"] = "synthetic-offline-not-a-credential"

    async def startup(_prepared_value, shared):
        if shared.guard is not guard:
            raise RuntimeError("startup guard mismatch")
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            raw.connect(("203.0.113.5", 9))
            report["unscoped"] = "connected"
        except PermissionError:
            report["unscoped"] = "denied"
        finally:
            raw.close()

        wavespeed = _wavespeed()
        wavespeed._quotes.clear()
        wavespeed._catalog.update(models={}, at=0.0)
        try:
            price, source, reason = await wavespeed.quote_detail("acme/offline-price", {"prompt": "cup"})
            report["quote_detail"] = [price, source, reason]
        except PermissionError as exc:
            report["quote_detail"] = getattr(exc, "reason", str(exc))
        posts = [item for item in shared.attempts if item[0] == "POST"]
        report["post_body_keys"] = sorted(posts[-1][2]) if posts and isinstance(posts[-1][2], dict) else None
        report["http_guard"] = shared.http_guard_ids
        report["connector_guard"] = shared.connector_guard_ids
        report["audit_guard"] = shared.audit_guard_ids
        report["sockets_revoked"] = all(
            guard.price_socket_allowed(sock, ("203.0.113.5", 443)) is False for sock in shared.sockets
        )
        return "entered"

    result, shared = await connect_product(
        _prepared(), synthetic_test_authorization(_prepared()),
        startup=startup, price_ips=IPS, guard=guard, install_audit=True,
    )
    report["startup"] = result
    report["shared"] = shared.guard is guard and all(
        item == id(guard) for item in shared.http_guard_ids + shared.connector_guard_ids + shared.audit_guard_ids
    )
    print(json.dumps(report))
    ok = (
        report["unscoped"] == "denied"
        and report["quote_detail"] == [0.1, "quote", "live"]
        and report["post_body_keys"] == ["input", "model_id"]
        and report["startup"] == "entered"
        and report["shared"] is True
        and report["sockets_revoked"] is True
        and bool(report["connector_guard"])
        and bool(report["audit_guard"])
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
