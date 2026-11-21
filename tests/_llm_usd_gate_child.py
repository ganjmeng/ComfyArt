"""Subprocess helper for abrupt os._exit persist faults. Not a pytest module."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import uuid

EXIT_FAULT = 91

URL = "https://api.deepseek.com/chat/completions"
ROUTE = {
    "provider": "deepseek",
    "model": "deepseek-flash",
    "catalog_model": "deepseek-flash",
    "base_url": "https://api.deepseek.com",
    "secret_env": "DEEPSEEK_API_KEY",
    "adapter": "deepseek_official",
    "passthrough": False,
    "quote": "unknown",
}


def load(path: str):
    spec = importlib.util.spec_from_file_location("llm_usd_gate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def install_exit_hook(mod, stage: str) -> None:
    if not stage:
        return

    def hook(name: str) -> None:
        if name == stage:
            os._exit(EXIT_FAULT)

    mod._write_fault = hook


def record(mod, nano: int, rid: str) -> dict:
    return {
        "id": rid,
        "status": "reserved",
        "reserved_nano": nano,
        "actual_nano": None,
        "retain_reason": "",
        "input_bound": 0,
        "max_output_tokens": 1,
        "model": "deepseek-flash",
        "route": {},
        "snapshot": mod.price_snapshot("deepseek-flash") or {},
        "created_at": 0,
    }


def main(argv: list[str]) -> int:
    gate, action, path = argv[1], argv[2], argv[3]
    mod = load(gate)
    if action == "init":
        ceiling = int(argv[4])
        opened = mod.open_authorized_scope(path, ceiling)
        sys.stdout.write(json.dumps(opened))
        return 0
    if action == "init_fault":
        ceiling = int(argv[4])
        stage = argv[5] if len(argv) > 5 else ""
        install_exit_hook(mod, stage)
        opened = mod.open_authorized_scope(path, ceiling)
        sys.stdout.write(json.dumps(opened))
        return 0
    if action == "reserve":
        nano = int(argv[4])
        rid = argv[5]
        stage = argv[6] if len(argv) > 6 else ""
        install_exit_hook(mod, stage)
        result = mod.reserve_nano(path, nano=nano, record=record(mod, nano, rid))
        sys.stdout.write(json.dumps(result))
        return 0
    if action == "dispatch":
        sent = argv[4]
        stage = argv[5] if len(argv) > 5 else ""
        install_exit_hook(mod, stage)
        body = {
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.2,
            "thinking": {"type": "disabled"},
            "max_tokens": 1,
        }

        def bound(_body, _snap):
            return mod.Bound(True, 0, "", "test text bound")

        async def send():
            with open(sent, "w", encoding="utf-8") as handle:
                handle.write("sent")
            return {"id": "fake", "choices": [{"message": {"role": "assistant", "content": "ok"}}]}

        result = asyncio.run(
            mod.dispatch(body, route=dict(ROUTE), url=URL, send=send, ledger_path=path, bound_fn=bound)
        )
        sys.stdout.write(json.dumps({"ok": True, "sent": True, "keys": list(result)} if isinstance(result, dict) else {"ok": True}))
        return 0
    if action == "state":
        sys.stdout.write(json.dumps(mod.ledger_state(path)))
        return 0
    if action == "inos":
        lock = path + ".lock"
        payload = {
            "lock_ino": os.stat(lock).st_ino if os.path.exists(lock) else None,
            "ledger_ino": os.stat(path).st_ino if os.path.exists(path) else None,
            "lock_path": lock,
        }
        sys.stdout.write(json.dumps(payload))
        return 0
    raise SystemExit("unknown action: " + action)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as exc:
        typ = type(exc).__name__
        code = getattr(exc, "code", "")
        detail = getattr(exc, "detail", str(exc))
        sys.stderr.write(f"{typ}:{code}:{detail}\n")
        raise SystemExit(2)
