"""Ordinary product LLM entry is not the controlled validation profile.

Fake transport only. No provider network, no paid call, and no claim that a
live DeepSeek request succeeds. Committed activation, reservations, and source
binding stay covered by test_llm_scope_activation_1004.py.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ComfyArt.api import provider_admin
from ComfyArt.api._common import app_path
from ComfyArt.bot import get_provider
from ComfyArt.bot.llm_usd_gate import (
    CEILING_NANO,
    LlmBudgetBlocked,
    clear_authorized_scope,
    ledger_state,
    open_authorized_scope,
    use_authorized_scope,
)
from ComfyArt.bot.run_budget import SYSTEM_DEFAULTS

URL = "https://api.deepseek.com/chat/completions"
_ROOT = Path(__file__).resolve().parents[1]
_TESTS = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _ordinary_process(monkeypatch):
    clear_authorized_scope()
    monkeypatch.delenv("COMFYART_RUNTIME_ID", raising=False)
    monkeypatch.delenv("COMFYART_HOME", raising=False)
    yield
    clear_authorized_scope()


def _provider():
    provider = get_provider("local-llm")
    assert provider is not None
    assert getattr(provider_admin.install, "done", False)
    assert provider_admin._llm_http is not None
    assert "installed_llm_http(" in inspect.getsource(provider._request_json)
    return provider


async def _call(provider, url, body, *, route):
    seen = []

    async def fake(session, method, call_url, *, headers, json_body=None, timeout=120):
        seen.append((method, call_url, json_body))
        return {"choices": [{"message": {"content": "ok"}}]}

    saved = provider_admin._llm_http
    token = provider_admin._llm_lock.set(route)
    try:
        provider_admin._llm_http = fake
        result = await provider._request_json(
            None, "POST", url, headers={}, json_body=body)
    finally:
        provider_admin._llm_http = saved
        provider_admin._llm_lock.reset(token)
    return result, seen


def test_product_run_budget_defaults_stay_in_place():
    """Per-run product credits and tool-call caps are not the test ledger."""
    assert SYSTEM_DEFAULTS["credits_usd"] == 5.0
    assert SYSTEM_DEFAULTS["max_tool_calls"] == 30
    from ComfyArt.api.settings import SETTINGS_SPEC
    assert SETTINGS_SPEC["agent-credits-usd"] == 5.0


def test_ordinary_wrapper_does_not_import_activation_before_the_early_return():
    src = inspect.getsource(provider_admin.installed_llm_http)
    assert src.index("adapt_llm_body(") < src.index("llm_scope_activation")
    assert "gated_llm_http(" in src
    from ComfyArt.bot.local_llm import LocalLlmProvider
    raw = inspect.getsource(LocalLlmProvider._request_json)
    aux = inspect.getsource(LocalLlmProvider._request_auxiliary_json)
    assert "llm_scope_activation" not in raw
    assert "llm_scope_activation" not in aux
    assert "llm_aux_context" in raw and "llm_aux_context" in aux
    for rel in ("bot/llm_usd_gate.py", "bot/llm_scope_activation.py"):
        for line in (_ROOT / rel).read_text(encoding="utf-8").splitlines():
            assert not line.startswith("import fcntl") and not line.startswith("from fcntl ")


async def test_installed_official_text_reaches_fake_transport_without_a_ledger(tmp_path, monkeypatch):
    home = tmp_path / "home-only"
    monkeypatch.setenv("COMFYART_HOME", str(home))
    assert provider_admin.llm_source() == "default"
    route = provider_admin.llm_route()
    assert route["adapter"] == "deepseek_official"
    assert route["model"] == "deepseek-flash"
    assert route["base_url"] == "https://api.deepseek.com"
    body = {"model": "deepseek-flash", "messages": [{"role": "user", "content": "hello from ordinary"}]}
    result, seen = await _call(
        _provider(), route["base_url"] + "/chat/completions", body, route=route)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert len(seen) == 1
    assert seen[0][0] == "POST"
    assert seen[0][2]["messages"][0]["content"] == "hello from ordinary"
    assert seen[0][2]["thinking"] == {"type": "disabled"}
    assert "thinking" not in body
    assert not Path(app_path("llm_usd_ledger.json")).exists()
    assert not Path(app_path("llm_scope_authorities.json")).exists()
    assert not home.exists()


async def test_custom_settings_route_reaches_transport_unchanged():
    from conftest import write_settings
    write_settings(
        llm_mode="custom",
        **{"bot-local-llm-url": "https://example.invalid/v1", "bot-model-local-llm": "my-model"},
    )
    assert provider_admin.llm_source() == "settings"
    assert provider_admin.llm_route() is None
    body = {"model": "my-model", "messages": [{"role": "user", "content": "custom hello"}]}
    result, seen = await _call(
        _provider(), "https://example.invalid/v1/chat/completions", body, route=None)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert seen[0][2] is body
    assert "thinking" not in body
    assert not Path(app_path("llm_usd_ledger.json")).exists()


async def test_bound_scope_still_blocks_official_and_lets_custom_through(tmp_path):
    path = tmp_path / "bound.json"
    opened = open_authorized_scope(str(path), CEILING_NANO)
    use_authorized_scope(str(path))
    before = path.read_bytes()
    route = provider_admin.llm_route()
    official = {"model": route["model"], "messages": [{"role": "user", "content": "official"}]}
    provider = _provider()
    with pytest.raises(LlmBudgetBlocked) as blocked:
        await _call(provider, route["base_url"] + "/chat/completions", official, route=route)
    assert blocked.value.code == "unbounded_billed_input"
    assert path.read_bytes() == before
    assert ledger_state(str(path))["scope_id"] == opened["scope_id"]
    assert ledger_state(str(path))["accounted_nano"] == 0
    custom = {"model": "my-model", "messages": [{"role": "user", "content": "custom"}]}
    result, seen = await _call(
        provider, "https://example.invalid/v1/chat/completions", custom, route=None)
    assert result["choices"][0]["message"]["content"] == "ok"
    assert seen[0][2] is custom
    assert path.read_bytes() == before


@pytest.mark.parametrize("runtime_id", ["partial-server", " ", "bad id"])
async def test_partial_runtime_never_becomes_ordinary(tmp_path, monkeypatch, runtime_id):
    home = tmp_path / "partial-home"
    home.mkdir()
    monkeypatch.setenv("COMFYART_HOME", str(home))
    monkeypatch.setenv("COMFYART_RUNTIME_ID", runtime_id)
    route = provider_admin.llm_route()
    provider = _provider()
    official = {"model": "deepseek-flash", "messages": [{"role": "user", "content": "nope"}]}
    with pytest.raises(LlmBudgetBlocked) as official_block:
        await _call(provider, URL, official, route=route)
    custom = {"model": "my-model", "messages": [{"role": "user", "content": "nope"}]}
    with pytest.raises(LlmBudgetBlocked) as custom_block:
        await _call(provider, "https://example.invalid/v1/chat/completions", custom, route=None)
    assert official_block.value.code == custom_block.value.code
    if runtime_id == "partial-server":
        assert official_block.value.code == "activation_required"
    else:
        assert official_block.value.code == "activation_runtime_invalid"
    assert not Path(app_path("llm_usd_ledger.json")).exists()
    assert not (home / "llm_scope_authorities.json").exists()


async def test_empty_or_marker_only_registry_stays_closed(tmp_path, monkeypatch):
    home = tmp_path / "torn-home"
    home.mkdir()
    monkeypatch.setenv("COMFYART_HOME", str(home))
    monkeypatch.setenv("COMFYART_RUNTIME_ID", "partial-server")
    (home / "llm_scope_authorities.json").write_text("", encoding="utf-8")
    route = provider_admin.llm_route()
    with pytest.raises(LlmBudgetBlocked) as empty:
        await _call(_provider(), URL, {"model": "deepseek-flash", "messages": [{"role": "user", "content": "x"}]}, route=route)
    assert empty.value.code == "activation_registry_unreadable"
    (home / "llm_scope_authorities.json").unlink()
    (home / "llm_scope_authorities.json.activated").write_text("{}", encoding="utf-8")
    with pytest.raises(LlmBudgetBlocked) as marked:
        await _call(_provider(), URL, {"model": "deepseek-flash", "messages": [{"role": "user", "content": "x"}]}, route=route)
    assert marked.value.code == "activation_registry_unreadable"


async def test_direct_gate_still_denies_unproven_official_text(tmp_path):
    route = provider_admin.llm_route()
    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(1)
        return {}

    token = provider_admin._llm_lock.set(route)
    try:
        with pytest.raises(LlmBudgetBlocked) as blocked:
            await provider_admin.gated_llm_http(
                None, "POST", route["base_url"] + "/chat/completions", headers={},
                json_body={"model": route["model"], "messages": [{"role": "user", "content": "hi"}]},
                transport=transport, ledger_path=str(tmp_path / "direct.json"))
    finally:
        provider_admin._llm_lock.reset(token)
    assert blocked.value.code == "unbounded_billed_input"
    assert calls == []
    assert not (tmp_path / "direct.json").exists()


_CLEAN = r"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
os.environ.pop("COMFYART_RUNTIME_ID", None)
os.environ.pop("COMFYART_HOME", None)
import conftest
import asyncio
from pathlib import Path
from ComfyArt.api import provider_admin
from ComfyArt.api._common import app_path
from ComfyArt.bot import get_provider

class Resp:
    status = 200
    headers = {}
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return None
    async def text(self):
        return '{"choices":[{"message":{"content":"ok"}}]}'

class Session:
    def __init__(self):
        self.seen = []
    def request(self, method, url, **kwargs):
        self.seen.append({"method": method, "url": url, "json": kwargs.get("json"),
                          "allow_redirects": kwargs.get("allow_redirects", "absent")})
        return Resp()

async def main():
    provider = get_provider("local-llm")
    route = provider_admin.llm_route()
    session = Session()
    body = {"model": route["model"], "messages": [{"role": "user", "content": "ordinary"}]}
    token = provider_admin._llm_lock.set(route)
    try:
        await provider._request_json(session, "POST", route["base_url"] + "/chat/completions",
                                     headers={}, json_body=body)
    finally:
        provider_admin._llm_lock.reset(token)
    custom = {"model": "my-model", "messages": [{"role": "user", "content": "custom"}], "sentinel": 1}
    await provider._request_json(session, "POST", "https://example.invalid/v1/chat/completions",
                                 headers={}, json_body=custom)
    home = Path(sys.argv[2])
    os.environ["COMFYART_HOME"] = str(home)
    os.environ.pop("COMFYART_RUNTIME_ID", None)
    token = provider_admin._llm_lock.set(route)
    try:
        await provider._request_json(session, "POST", route["base_url"] + "/chat/completions",
                                     headers={}, json_body={"model": route["model"], "messages": [{"role": "user", "content": "home"}]})
    finally:
        provider_admin._llm_lock.reset(token)
    banned = [name for name in sys.modules if name in {
        "ComfyArt.bot.llm_scope_activation",
        "ComfyArt.bot.llm_usd_gate",
        "ComfyArt.bot.llm_activation_manifest",
    }]
    print(json.dumps({
        "source": provider_admin.llm_source(),
        "adapter": route["adapter"],
        "model": route["model"],
        "official_thinking": session.seen[0]["json"]["thinking"],
        "official_redirects": session.seen[0]["allow_redirects"],
        "custom_sentinel": session.seen[1]["json"].get("sentinel"),
        "custom_thinking": "thinking" in session.seen[1]["json"],
        "calls": len(session.seen),
        "home_exists": home.exists(),
        "ledger": os.path.exists(app_path("llm_usd_ledger.json")),
        "registry": os.path.exists(app_path("llm_scope_authorities.json")),
        "banned": banned,
        "wrapper": "installed_llm_http(" in __import__("inspect").getsource(provider._request_json),
    }))

asyncio.run(main())
"""


def test_clean_interpreter_ordinary_path_does_not_import_activation(tmp_path):
    home = tmp_path / "unused-home"
    env = os.environ.copy()
    env.pop("COMFYART_RUNTIME_ID", None)
    env.pop("COMFYART_HOME", None)
    proc = subprocess.run(
        [sys.executable, "-c", _CLEAN, str(_TESTS), str(home)],
        capture_output=True, text=True, env=env, timeout=60, cwd=str(_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["source"] == "default"
    assert data["adapter"] == "deepseek_official"
    assert data["model"] == "deepseek-flash"
    assert data["wrapper"] is True
    assert data["calls"] == 3
    assert data["official_thinking"] == {"type": "disabled"}
    assert data["official_redirects"] == "absent"
    assert data["custom_sentinel"] == 1
    assert data["custom_thinking"] is False
    assert data["home_exists"] is False
    assert data["ledger"] is False and data["registry"] is False
    assert data["banned"] == []


_NO_FCNTL = r"""
import builtins, json, os, sys, tempfile
from pathlib import Path
real = builtins.__import__
def guarded(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "fcntl":
        raise ImportError("fcntl unavailable")
    return real(name, globals, locals, fromlist, level)
builtins.__import__ = guarded
sys.path.insert(0, sys.argv[1])
os.environ.pop("COMFYART_RUNTIME_ID", None)
import conftest
from ComfyArt.bot import llm_usd_gate as gate
from ComfyArt.bot import llm_scope_activation as activation
root = Path(tempfile.mkdtemp())
entered = []
try:
    with gate._with_ledger_lock(str(root / "missing" / "ledger.json")):
        entered.append("gate")
    gate_code = "OPEN"
except gate.LlmBudgetBlocked as exc:
    gate_code = exc.code
try:
    with activation._registry_lock(str(root / "registry-home")):
        entered.append("registry")
    registry_code = "OPEN"
except gate.LlmBudgetBlocked as exc:
    registry_code = exc.code
print(json.dumps({
    "gate": gate_code,
    "registry": registry_code,
    "entered": entered,
    "missing_dir": (root / "missing").exists(),
    "registry_home": (root / "registry-home").exists(),
}))
"""


def test_missing_fcntl_fails_closed_before_creating_lock_files():
    env = os.environ.copy()
    env.pop("COMFYART_RUNTIME_ID", None)
    proc = subprocess.run(
        [sys.executable, "-c", _NO_FCNTL, str(_TESTS)],
        capture_output=True, text=True, env=env, timeout=60, cwd=str(_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data == {
        "gate": "posix_lock_unavailable",
        "registry": "posix_lock_unavailable",
        "entered": [],
        "missing_dir": False,
        "registry_home": False,
    }
