"""Offline checks of the frozen WaveSpeed price guard. No sockets and no provider calls."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "docs/integrate/protection-v3/frozen/wavespeed_price_guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("wavespeed_price_guard_frozen", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_get_models_and_post_price_with_singular_input_are_allowed():
    guard = _load()
    ok, reason, info = guard.request_allowed(
        "POST", "https://api.wavespeed.ai/api/v3/model/price",
        {"json": {"model_id": "openai/gpt-image-2.6-flare/edit", "input": {"width": 1152, "height": 2048}}},
    )
    assert ok and reason == "allow_post_price" and info["path"] == "/api/v3/model/price"
    ok, reason, _info = guard.request_allowed("GET", "https://api.wavespeed.ai/api/v3/models", {})
    assert ok and reason == "allow_get_models"
    ok, reason, _info = guard.request_allowed(
        "POST", "https://api.wavespeed.ai/api/v3/model/price",
        {"json": {"model_id": "m", "inputs": {"width": 1}}},
    )
    assert not ok and reason == "inputs_plural_not_official"
    for path in guard.DENIED_PATHS:
        ok, reason, _info = guard.request_allowed("POST", "https://api.wavespeed.ai" + path, {"json": {"model_id": "m", "input": {}}})
        assert not ok and reason.startswith("url:"), (path, reason)


def test_price_scope_revocation_is_request_lifetime_only():
    guard = _load()

    async def _once():
        scope, token = guard.begin_price_request({"203.0.113.5"})
        assert scope.active is True
        guard.end_price_request(scope, token)
        assert scope.active is False
        class _Sock:
            pass
        assert guard.price_socket_allowed(_Sock(), ("203.0.113.5", 443)) is False
        assert guard._PRICE_SCOPE.get() is None

    asyncio.run(_once())
