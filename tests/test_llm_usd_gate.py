"""Fail-closed $0.05 gate for the official direct DeepSeek route. Fake transport only.

The production input bound does not authorize a send. Tests that exercise the
reservation ledger pass an explicit text-only bound. That bound is not the
character-count heuristic and is not a WaveSpeed price.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ComfyArt.api import provider_admin
from ComfyArt.bot import agent_loop, get_provider, llm_usd_gate, local_llm, reasoning_boost
from ComfyArt.bot.llm_usd_gate import (
    CEILING_NANO,
    CHAT_URL,
    DEFAULT_AUTHORIZATION,
    MEMORY_BOOST_OUTPUT_DEFAULT,
    ORDINARY_OUTPUT_DEFAULT,
    PRICES,
    SUMMARY_OUTPUT_DEFAULT,
    TOKEN_URL,
    TWO_DOLLAR_AUTHORIZATION,
    TWO_DOLLAR_CEILING_NANO,
    VISION_URL,
    Bound,
    LlmBudgetBlocked,
    LlmScopeConflict,
    apply_output_cap,
    dispatch,
    ledger_state,
    official_input_bound,
    open_authorized_scope,
    prepare,
    price_snapshot,
    reserve_nano,
    resolved_ledger_path,
    settle,
    structural_block,
    use_authorized_scope,
    clear_authorized_scope,
    worst_case_nano,
)
from ComfyArt.bot.local_llm import LlmHttpError, LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle

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


@pytest.fixture(autouse=True)
def _restore_prices():
    saved = {key: dict(value) for key, value in PRICES.items()}
    yield
    PRICES.clear()
    PRICES.update(saved)


@pytest.fixture(autouse=True)
def _unbind_authorized_scope():
    clear_authorized_scope()
    yield
    clear_authorized_scope()


def _zero_bound(body, snapshot):
    return Bound(True, 0, "", "test text bound")


def _bound(tokens: int):
    def run(body, snapshot):
        return Bound(True, tokens, "", "test text bound")
    return run


def _text(max_tokens=None, model="deepseek-flash", content="hi"):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2,
        "thinking": {"type": "disabled"},
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    return body


def _usage(prompt, completion, hit=None, miss=None, **extra):
    if hit is None:
        hit, miss = 0, prompt
    return {
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "prompt_cache_hit_tokens": hit,
            "prompt_cache_miss_tokens": miss,
            "prompt_tokens_details": {"cached_tokens": hit},
            **extra,
        }
    }


def _route(model="deepseek-flash"):
    return {**ROUTE, "model": model, "catalog_model": model}


async def _emit(_event):
    return None


def _provider(transport, path, bound_fn=_zero_bound):
    provider = LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")

    async def _request_json(session, method, url, *, headers, json_body=None, timeout=120):
        return await provider_admin.gated_llm_http(
            session, method, url, headers=headers, json_body=json_body, timeout=timeout,
            transport=transport, ledger_path=str(path), bound_fn=bound_fn)

    provider._request_json = _request_json
    return provider


# ---------------------------------------------------------------- prices


def test_official_peak_rates_are_exact_integers_and_not_wavespeed_ids():
    flash = price_snapshot("deepseek-flash")
    pro = price_snapshot("deepseek-v4-pro")
    assert flash["input_miss_peak_nano"] == 300
    assert flash["input_hit_peak_nano"] == 6
    assert flash["output_peak_nano"] == 1200
    assert pro["input_miss_peak_nano"] == 1320
    assert pro["input_hit_peak_nano"] == 44
    assert pro["output_peak_nano"] == 3960
    assert pro["output_peak_nano"] > flash["output_peak_nano"]
    assert price_snapshot("deepseek/deepseek-v4.1-flash-1017") is None
    assert price_snapshot("deepseek-chat") is None
    assert flash["snapshot_id"] == "deepseek-pricing-2026-11-18"
    assert "api-docs.deepseek.com" in flash["sources"][0]
    assert "wavespeed" not in json.dumps(flash).lower()
    assert CEILING_NANO == 50_000_000
    assert worst_case_nano(flash, 166662, 1) == 166662 * 300 + 1200
    assert worst_case_nano(flash, 166662, 1) <= CEILING_NANO
    assert worst_case_nano(flash, 166663, 1) > CEILING_NANO
    assert "confirm" not in inspect.signature(dispatch).parameters
    gate = Path(llm_usd_gate.__file__).read_text()
    assert "count_tokens(" not in gate


def test_output_default_follows_the_documented_mode_and_never_shrinks():
    disabled = _text()
    disabled.pop("max_tokens", None)
    cap, code = apply_output_cap(disabled)
    assert (cap, code) == (8192, "")
    explicit = _text(max_tokens=393216)
    assert apply_output_cap(explicit) == (393216, "")
    assert explicit["max_tokens"] == 393216
    too_big = _text(max_tokens=393217)
    assert apply_output_cap(too_big)[0] is None
    assert too_big["max_tokens"] == 393217
    enabled = {"thinking": {"type": "enabled"}, "messages": [], "model": "deepseek-flash"}
    assert apply_output_cap(enabled)[0] == 65536
    enabled_max = {"thinking": {"type": "enabled"}, "reasoning_effort": "max", "model": "deepseek-flash"}
    assert apply_output_cap(enabled_max)[0] == 131072
    assert apply_output_cap({"thinking": {"type": "disabled"}, "max_tokens": True})[0] is None
    assert apply_output_cap({"thinking": {"type": "disabled"}, "max_tokens": 0})[0] is None


def test_production_bound_rejects_text_tools_and_images_without_the_heuristic(monkeypatch):
    def boom(_text):
        raise AssertionError("character heuristic must not run")

    monkeypatch.setattr(local_llm, "count_tokens", boom)
    snap = price_snapshot("deepseek-flash")
    text = official_input_bound(_text(), snap)
    assert text.ok is False and text.code == "unbounded_billed_input"
    assert "not a guarantee" in text.detail and TOKEN_URL in text.detail
    tools = _text()
    tools["tools"] = [{"type": "function", "function": {"name": "lookup", "parameters": {}}}]
    tools["tool_choice"] = "auto"
    # Ordinary MCP function tools are not a structural block; production still
    # fail-closes on unproven billed input and must not call the heuristic.
    assert official_input_bound(tools, snap).code == "unbounded_billed_input"
    assert "not a guarantee" in official_input_bound(tools, snap).detail
    assert TOKEN_URL in official_input_bound(tools, snap).detail
    assert structural_block(tools) == ""
    image = _text()
    image["messages"] = [{"role": "user", "content": [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,aaaa"}},
    ]}]
    assert structural_block(image) == "unbounded_multimodal"
    assert VISION_URL in official_input_bound(image, snap).detail
    web = _text()
    web["tools"] = [{"type": "function", "function": {"name": "deepseek_web_search", "parameters": {}}}]
    assert structural_block(web) == "unpriced_tool_fee"


# ---------------------------------------------------------------- blocks


async def test_unpriced_unbounded_and_over_budget_make_zero_http_calls(tmp_path):
    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(json_body)
        raise AssertionError("HTTP must not run")

    path = tmp_path / "ledger.json"

    async def once(route, body, bound_fn=_zero_bound):
        token = provider_admin._llm_lock.set(route)
        try:
            await provider_admin.gated_llm_http(
                None, "POST", URL, headers={}, json_body=body,
                transport=transport, ledger_path=str(path), bound_fn=bound_fn)
        finally:
            provider_admin._llm_lock.reset(token)

    with pytest.raises(LlmBudgetBlocked) as mismatch:
        await once(_route(), _text(model="deepseek-chat"))
    assert mismatch.value.code == "route_mismatch"

    with pytest.raises(LlmBudgetBlocked) as wave:
        await once(_route("deepseek/deepseek-v4.1-flash-1017"),
                   _text(model="deepseek/deepseek-v4.1-flash-1017"))
    assert wave.value.code == "unpriced"

    with pytest.raises(LlmBudgetBlocked) as unbounded:
        await once(_route(), _text(content="UNIQUE_PROMPT_DO_NOT_STORE"), bound_fn=None)
    assert unbounded.value.code == "unbounded_billed_input"
    assert "not a guarantee" in str(unbounded.value)

    tools = _text(max_tokens=1)
    tools["tools"] = [{"type": "function", "function": {"name": "lookup", "parameters": {}}}]

    with pytest.raises(LlmBudgetBlocked) as tool_block:
        await once(_route(), tools, bound_fn=None)
    assert tool_block.value.code == "unbounded_billed_input"

    huge = _text(max_tokens=393216)
    with pytest.raises(LlmBudgetBlocked) as over:
        await once(_route(), huge)
    assert over.value.code == "over_budget"
    assert huge["max_tokens"] == 393216
    assert calls == []


async def test_explicit_output_cap_is_on_the_http_body_and_prompt_is_not_in_the_ledger(tmp_path):
    seen = {}

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        seen["body"] = json_body
        seen["url"] = url
        return _usage(0, 1)

    path = tmp_path / "ledger.json"
    body = _text(content="UNIQUE_PROMPT_DO_NOT_STORE")
    body.pop("thinking")
    body["stream"] = True
    token = provider_admin._llm_lock.set(_route())
    try:
        await provider_admin.gated_llm_http(
            None, "POST", URL, headers={}, json_body=body,
            transport=transport, ledger_path=str(path), bound_fn=_zero_bound)
    finally:
        provider_admin._llm_lock.reset(token)
    assert seen["url"] == URL
    assert seen["body"]["max_tokens"] == 8192
    assert seen["body"]["thinking"] == {"type": "disabled"}
    assert seen["body"]["stream"] is False
    assert "UNIQUE_PROMPT_DO_NOT_STORE" not in path.read_text()
    state = ledger_state(str(path))
    assert state["accounted_nano"] == 1200  # one completion token at the flash peak output rate
    assert state["ceiling_nano"] == CEILING_NANO


async def test_quote_field_cannot_replace_the_official_snapshot(tmp_path):
    seen = {}

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        seen["model"] = json_body["model"]
        return _usage(0, 1)

    path = tmp_path / "ledger.json"
    route = {**_route("deepseek-v4-pro"), "quote": 0.05}
    token = provider_admin._llm_lock.set(route)
    try:
        await provider_admin.gated_llm_http(
            None, "POST", URL, headers={}, json_body=_text(model="deepseek-v4-pro", max_tokens=1),
            transport=transport, ledger_path=str(path), bound_fn=_zero_bound)
    finally:
        provider_admin._llm_lock.reset(token)
    assert seen["model"] == "deepseek-v4-pro"
    assert ledger_state(str(path))["accounted_nano"] == 3960


async def test_sequential_cumulative_cap_blocks_the_third_send(tmp_path):
    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(json_body["max_tokens"])
        return {"choices": [{"message": {"content": "ok"}}]}

    path = tmp_path / "ledger.json"
    token = provider_admin._llm_lock.set(_route())
    try:
        for _ in range(2):
            await provider_admin.gated_llm_http(
                None, "POST", URL, headers={}, json_body=_text(max_tokens=20000),
                transport=transport, ledger_path=str(path), bound_fn=_zero_bound)
        with pytest.raises(LlmBudgetBlocked) as third:
            await provider_admin.gated_llm_http(
                None, "POST", URL, headers={}, json_body=_text(max_tokens=20000),
                transport=transport, ledger_path=str(path), bound_fn=_zero_bound)
    finally:
        provider_admin._llm_lock.reset(token)
    assert calls == [20000, 20000]
    assert third.value.code == "over_budget"
    state = ledger_state(str(path))
    # Missing usage keeps each 24_000_000 nano worst case. The third send never starts.
    assert state["accounted_nano"] == 48_000_000
    assert len(state["reservations"]) == 2
    assert {row["status"] for row in state["reservations"].values()} == {"retained"}


async def test_continuation_and_restart_keep_scope_and_spend(tmp_path):
    path = tmp_path / "ledger.json"

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        return {"choices": [{"message": {"content": "ok"}}]}  # usage missing: retain the worst case

    token = provider_admin._llm_lock.set(_route())
    try:
        await provider_admin.gated_llm_http(
            None, "POST", URL, headers={}, json_body=_text(max_tokens=20000, content="turn-1"),
            transport=transport, ledger_path=str(path), bound_fn=_zero_bound)
        first = ledger_state(str(path))
        await provider_admin.gated_llm_http(
            None, "POST", URL, headers={}, json_body=_text(max_tokens=20000, content="question-card reply"),
            transport=transport, ledger_path=str(path), bound_fn=_zero_bound)
        second = ledger_state(str(path))
    finally:
        provider_admin._llm_lock.reset(token)
    assert first["scope_id"] == second["scope_id"]
    assert second["accounted_nano"] == 48_000_000
    assert second["ceiling_nano"] == CEILING_NANO
    script = (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location('llm_usd_gate', sys.argv[1])\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "state = mod.ledger_state(sys.argv[2])\n"
        f"assert state['scope_id'] == {second['scope_id']!r}\n"
        "assert state['accounted_nano'] == 48000000\n"
        "assert state['ceiling_nano'] == 50000000\n"
        "again = mod.reserve_nano(sys.argv[2], nano=20000000, record={'id':'restart','status':'reserved',"
        "'reserved_nano':20000000,'actual_nano':None,'retain_reason':'','input_bound':0,"
        "'max_output_tokens':1,'model':'deepseek-flash','route':{},'snapshot':{},'created_at':0})\n"
        "assert again['ok'] is False and again['code'] == 'over_budget', again\n"
        "assert again['scope_id'] == state['scope_id']\n"
    )
    subprocess.check_call([sys.executable, "-c", script, str(Path(llm_usd_gate.__file__).resolve()), str(path)])


def test_threads_and_processes_cannot_pass_the_ceiling(tmp_path):
    path = str(tmp_path / "threads.json")

    def once(_n):
        return reserve_nano(path, nano=30_000_000, record={
            "id": uuid.uuid4().hex, "status": "reserved", "reserved_nano": 30_000_000,
            "actual_nano": None, "retain_reason": "", "input_bound": 0,
            "max_output_tokens": 1, "model": "deepseek-flash", "route": {},
            "snapshot": price_snapshot("deepseek-flash"), "created_at": 0,
        })

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(once, range(8)))
    assert sum(1 for row in results if row["ok"]) == 1
    assert ledger_state(path)["accounted_nano"] == 30_000_000

    proc_path = tmp_path / "procs.json"
    script = (
        "import importlib.util, sys, uuid\n"
        "spec = importlib.util.spec_from_file_location('llm_usd_gate', sys.argv[1])\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "nano = int(sys.argv[3])\n"
        "mod.reserve_nano(sys.argv[2], nano=nano, record={\n"
        "    'id': uuid.uuid4().hex, 'status': 'reserved', 'reserved_nano': nano,\n"
        "    'actual_nano': None, 'retain_reason': '', 'input_bound': 0,\n"
        "    'max_output_tokens': 1, 'model': 'deepseek-flash', 'route': {},\n"
        "    'snapshot': {}, 'created_at': 0,\n"
        "})\n"
    )
    gate_file = str(Path(llm_usd_gate.__file__).resolve())
    procs = [
        subprocess.Popen([sys.executable, "-c", script, gate_file, str(proc_path), "20000000"])
        for _ in range(8)
    ]
    assert [proc.wait(10) for proc in procs] == [0] * 8
    state = ledger_state(str(proc_path))
    assert state["accounted_nano"] == 40_000_000
    assert sum(1 for row in state["reservations"].values() if row["status"] == "reserved") == 2
    assert state["accounted_nano"] <= state["ceiling_nano"]


def test_tampered_ledger_cannot_raise_or_reset_the_ceiling(tmp_path):
    path = tmp_path / "ledger.json"
    path.write_text("{not json")
    before = path.read_text()
    with pytest.raises(LlmBudgetBlocked) as bad:
        reserve_nano(str(path), nano=1, record={"id": "x"})
    assert bad.value.code == "ledger_unreadable"
    assert path.read_text() == before

    fresh = tmp_path / "high.json"
    fresh.write_text(json.dumps({
        "version": 1, "scope_id": "usd-fixed", "ceiling_nano": 10 ** 12,
        "accounted_nano": 0, "reservations": {},
    }))
    denied = reserve_nano(str(fresh), nano=60_000_000, record={
        "id": "big", "status": "reserved", "reserved_nano": 60_000_000,
        "actual_nano": None, "retain_reason": "", "input_bound": 0,
        "max_output_tokens": 1, "model": "deepseek-flash", "route": {},
        "snapshot": {}, "created_at": 0,
    })
    assert denied["ok"] is False and denied["ceiling_nano"] == CEILING_NANO
    assert ledger_state(str(fresh))["accounted_nano"] == 0

    held = tmp_path / "held.json"
    reserve_nano(str(held), nano=30_000_000, record={
        "id": "kept", "status": "reserved", "reserved_nano": 30_000_000,
        "actual_nano": None, "retain_reason": "", "input_bound": 0,
        "max_output_tokens": 1, "model": "deepseek-flash", "route": {},
        "snapshot": {}, "created_at": 0,
    })
    raw = json.loads(held.read_text())
    raw["accounted_nano"] = 0
    held.write_text(json.dumps(raw))
    again = reserve_nano(str(held), nano=30_000_000, record={
        "id": "second", "status": "reserved", "reserved_nano": 30_000_000,
        "actual_nano": None, "retain_reason": "", "input_bound": 0,
        "max_output_tokens": 1, "model": "deepseek-flash", "route": {},
        "snapshot": {}, "created_at": 0,
    })
    assert again["ok"] is False
    assert ledger_state(str(held))["accounted_nano"] == 30_000_000


# ---------------------------------------------------------------- reconcile


@pytest.mark.parametrize("usage", [
    None,
    {},
    {"usage": None},
    {"usage": {}},
    {"usage": {"prompt_tokens": 1}},
    {"usage": {"prompt_tokens": True, "completion_tokens": 1, "total_tokens": 2,
               "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1,
               "prompt_tokens_details": {"cached_tokens": 0}}},
    {"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 3,
               "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1,
               "prompt_tokens_details": {"cached_tokens": 0}}},
    {"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2,
               "prompt_cache_hit_tokens": 1, "prompt_cache_miss_tokens": 1,
               "prompt_tokens_details": {"cached_tokens": 1}}},
    {"usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6,
               "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 5,
               "prompt_tokens_details": {"cached_tokens": 0}}},
    {"usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
               "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0,
               "prompt_tokens_details": {},
               "server_tool_use": {"tool_search": 1}}},
])
async def test_missing_or_malformed_usage_retains_the_reservation(tmp_path, usage):
    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(1)
        return usage if usage is not None else {"choices": []}

    path = tmp_path / "ledger.json"
    await dispatch(
        _text(max_tokens=20000), route=_route(), url=URL, send=lambda: transport(None, "POST", URL, headers={}),
        ledger_path=str(path), bound_fn=_zero_bound)
    state = ledger_state(str(path))
    assert calls == [1]
    assert state["accounted_nano"] == 24_000_000
    assert next(iter(state["reservations"].values()))["status"] == "retained"


async def test_timeout_and_cancel_retain_the_reservation(tmp_path):
    path = tmp_path / "timeout.json"

    async def explode():
        raise asyncio.TimeoutError()

    with pytest.raises(asyncio.TimeoutError):
        await dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=explode,
                       ledger_path=str(path), bound_fn=_zero_bound)
    state = ledger_state(str(path))
    assert state["accounted_nano"] == 24_000_000
    assert next(iter(state["reservations"].values()))["retain_reason"] == "transport:TimeoutError"

    cancel_path = tmp_path / "cancel.json"

    async def cancel():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await dispatch(_text(max_tokens=20000), route=_route(), url=URL, send=cancel,
                       ledger_path=str(cancel_path), bound_fn=_zero_bound)
    assert ledger_state(str(cancel_path))["accounted_nano"] == 24_000_000


async def test_trustworthy_usage_reconciles_and_a_later_call_can_use_the_remainder(tmp_path):
    path = tmp_path / "ledger.json"
    await dispatch(
        _text(max_tokens=20000), route=_route(), url=URL,
        send=lambda: _async(_usage(1, 1)),
        ledger_path=str(path), bound_fn=_bound(10))
    state = ledger_state(str(path))
    assert state["accounted_nano"] == 1500
    assert next(iter(state["reservations"].values()))["status"] == "reconciled"
    follow = reserve_nano(str(path), nano=48_000_000, record={
        "id": "follow", "status": "reserved", "reserved_nano": 48_000_000,
        "actual_nano": None, "retain_reason": "", "input_bound": 0,
        "max_output_tokens": 1, "model": "deepseek-flash", "route": {},
        "snapshot": {}, "created_at": 0,
    })
    assert follow["ok"] is True
    assert follow["accounted_nano"] == 48_001_500


async def test_cache_hit_reconcile_uses_the_stored_snapshot_not_a_later_table(tmp_path):
    path = tmp_path / "ledger.json"
    snap = price_snapshot("deepseek-flash")
    rid = "snap"
    reserve_nano(str(path), nano=10 * 300 + 1200, record={
        "id": rid, "status": "reserved", "reserved_nano": 10 * 300 + 1200,
        "actual_nano": None, "retain_reason": "", "input_bound": 10,
        "max_output_tokens": 1, "model": "deepseek-flash", "route": {},
        "snapshot": snap, "created_at": 0,
    })
    PRICES["deepseek-flash"]["input_miss_peak_nano"] = 1
    PRICES["deepseek-flash"]["input_hit_peak_nano"] = 1
    PRICES["deepseek-flash"]["output_peak_nano"] = 1
    done = settle(str(path), rid, _usage(10, 0, hit=10, miss=0)["usage"])
    assert done["code"] == "reconciled"
    assert done["actual_nano"] == 60  # 10 peak cache-hit tokens at 6 nano, not the mutated table
    assert ledger_state(str(path))["accounted_nano"] == 60


async def _async(value):
    return value


# ---------------------------------------------------------------- physical paths


async def test_summary_retry_and_overflow_each_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(local_llm, "_RETRY_BACKOFF_S", (0.0, 0.0))
    path = tmp_path / "ledger.json"
    calls = []

    async def flaky(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(("summary" if json_body.get("temperature") == 0.1 else "chat", json_body.get("max_tokens")))
        if len([item for item in calls if item[0] == "chat"]) == 1 and json_body.get("temperature") != 0.1:
            raise asyncio.TimeoutError()
        return _usage(0, 1)

    provider = _provider(flaky, path, _zero_bound)
    token = provider_admin._llm_lock.set(_route())
    try:
        text = await provider._summarize_llm(None, "https://api.deepseek.com", "deepseek-flash", "prev", "old turn")
        assert text == "" or isinstance(text, str)
        await provider._llm_request(None, URL, _text(max_tokens=1000), _emit, TurnHandle())
    finally:
        provider_admin._llm_lock.reset(token)
    assert ("summary", 8192) in calls
    assert calls.count(("chat", 1000)) == 2
    state = ledger_state(str(path))
    assert len(state["reservations"]) == 3
    retained = [row for row in state["reservations"].values() if row["status"] == "retained"]
    reconciled = [row for row in state["reservations"].values() if row["status"] == "reconciled"]
    assert len(retained) == 1 and len(reconciled) == 2

    over_calls = []

    async def once(session, method, url, *, headers, json_body=None, timeout=120):
        over_calls.append(json_body["max_tokens"])
        raise asyncio.TimeoutError()

    over_path = tmp_path / "retry-block.json"
    over = _provider(once, over_path, _zero_bound)
    token = provider_admin._llm_lock.set(_route())
    try:
        with pytest.raises(LlmBudgetBlocked) as blocked:
            await over._llm_request(None, URL, _text(max_tokens=25000), _emit, TurnHandle())
    finally:
        provider_admin._llm_lock.reset(token)
    assert blocked.value.code == "over_budget"
    assert over_calls == [25000]
    assert ledger_state(str(over_path))["accounted_nano"] == 30_000_000

    overflow_calls = []

    async def overflow(session, method, url, *, headers, json_body=None, timeout=120):
        overflow_calls.append(dict(json_body))
        if len(overflow_calls) == 1:
            raise LlmHttpError(400, "maximum context length is 8192 tokens. prompt is too long")
        return _usage(0, 1)

    fit_path = tmp_path / "fit.json"
    fit = _provider(overflow, fit_path, _zero_bound)
    token = provider_admin._llm_lock.set(_route())
    try:
        data, window = await fit._llm_request_fit(
            None, URL, _text(max_tokens=1000), _emit, TurnHandle(),
            model="deepseek-flash", window=1_000_000, refit=lambda messages, new_window: messages)
    finally:
        provider_admin._llm_lock.reset(token)
    assert window == 8192
    assert [body["max_tokens"] for body in overflow_calls] == [1000, 1000]
    assert data["usage"]["completion_tokens"] == 1
    assert len(ledger_state(str(fit_path))["reservations"]) == 2

    blocked_calls = []

    async def overflow_once(session, method, url, *, headers, json_body=None, timeout=120):
        blocked_calls.append(1)
        raise LlmHttpError(400, "context_length_exceeded maximum context length is 100000")

    blocked_path = tmp_path / "fit-block.json"
    blocked_fit = _provider(overflow_once, blocked_path, _zero_bound)
    token = provider_admin._llm_lock.set(_route())
    try:
        with pytest.raises(LlmBudgetBlocked):
            await blocked_fit._llm_request_fit(
                None, URL, _text(max_tokens=25000), _emit, TurnHandle(),
                model="deepseek-flash", window=1_000_000, refit=lambda messages, new_window: messages)
    finally:
        provider_admin._llm_lock.reset(token)
    assert blocked_calls == [1]


async def test_ordinary_mcp_function_tools_are_not_unbounded_tools(tmp_path):
    """Ask/canvas MCP function tools and tool-result messages proceed to the input bound.

    Native web tools and unknown tool shapes stay structurally blocked. A test
    bound may authorize ordinary MCP; production official_input_bound does not.
    """
    snap = price_snapshot("deepseek-flash")
    mcp = _text(max_tokens=8192)
    mcp["tools"] = [
        {"type": "function", "function": {"name": "ask_user", "parameters": {"type": "object"}}},
        {"type": "function", "function": {"name": "get_canvas", "parameters": {"type": "object"}}},
        {"type": "function", "function": {"name": "quote_plan", "parameters": {"type": "object"}}},
    ]
    mcp["tool_choice"] = "auto"
    mcp["messages"] = [
        {"role": "user", "content": "draw a card"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_canvas",
                "type": "function",
                "function": {"name": "get_canvas", "arguments": "{}"},
            }],
        },
        {"role": "tool", "tool_call_id": "call_canvas", "content": "canvas is empty"},
    ]
    assert structural_block(mcp) == ""
    prod = official_input_bound(mcp, snap)
    assert prod.ok is False and prod.code == "unbounded_billed_input"
    assert "not a guarantee" in prod.detail

    web = dict(mcp)
    web["tools"] = list(mcp["tools"]) + [
        {"type": "function", "function": {"name": "deepseek_web_search", "parameters": {}}},
    ]
    assert structural_block(web) == "unpriced_tool_fee"

    unknown = dict(mcp)
    unknown["tools"] = [{"type": "custom", "name": "apply_patch"}]
    assert structural_block(unknown) == "unbounded_tools"

    required = dict(mcp)
    required["tool_choice"] = "required"
    assert structural_block(required) == ""
    assert official_input_bound(required, snap).code == "unbounded_billed_input"

    named = dict(mcp)
    named["tool_choice"] = {"type": "function", "function": {"name": "get_canvas"}}
    assert structural_block(named) == ""
    assert official_input_bound(named, snap).code == "unbounded_billed_input"

    unknown_choice = dict(mcp)
    unknown_choice["tool_choice"] = "maybe"
    assert structural_block(unknown_choice) == "unbounded_tools"

    named_web = dict(mcp)
    named_web["tool_choice"] = {"type": "function", "function": {"name": "deepseek_read_url"}}
    assert structural_block(named_web) == "unpriced_tool_fee"

    server = dict(mcp)
    server["messages"] = list(mcp["messages"]) + [
        {"role": "assistant", "content": "", "server_tool_calls": [{"name": "deepseek_web_search"}]},
    ]
    assert structural_block(server) == "unbounded_tools"

    image = dict(mcp)
    image["messages"] = [{"role": "user", "content": [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,aaaa"}},
    ]}]
    assert structural_block(image) == "unbounded_multimodal"

    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(json_body)
        return _usage(1, 1)

    path = tmp_path / "ledger.json"
    token = provider_admin._llm_lock.set(_route())
    try:
        await provider_admin.gated_llm_http(
            None, "POST", URL, headers={}, json_body=mcp,
            transport=transport, ledger_path=str(path), bound_fn=_zero_bound)
        with pytest.raises(LlmBudgetBlocked) as blocked:
            await provider_admin.gated_llm_http(
                None, "POST", URL, headers={}, json_body=mcp,
                transport=transport, ledger_path=str(path), bound_fn=None)
        assert blocked.value.code == "unbounded_billed_input"
    finally:
        provider_admin._llm_lock.reset(token)
    assert len(calls) == 1
    assert calls[0]["tools"][0]["function"]["name"] == "ask_user"
    assert calls[0]["max_tokens"] == 8192


async def test_legacy_tool_body_is_blocked_and_non_chat_is_not(tmp_path):
    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append((method, str(url)))
        return {"data": []}

    path = tmp_path / "ledger.json"
    legacy = {
        "model": "deepseek-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"type": "function", "function": {"name": "lookup", "parameters": {}}}],
        "tool_choice": "auto",
        "temperature": 0.2,
    }
    token = provider_admin._llm_lock.set(_route())
    try:
        with pytest.raises(LlmBudgetBlocked) as legacy_block:
            await provider_admin.gated_llm_http(
                None, "POST", URL, headers={}, json_body=legacy,
                transport=transport, ledger_path=str(path), bound_fn=None)
        assert legacy_block.value.code == "unbounded_billed_input"
        await provider_admin.gated_llm_http(
            None, "GET", "https://api.deepseek.com/models", headers={}, json_body=None,
            transport=transport, ledger_path=str(path))
        await provider_admin.gated_llm_http(
            None, "POST", "http://127.0.0.1:9/mcp", headers={},
            json_body={"jsonrpc": "2.0", "method": "tools/list"},
            transport=transport, ledger_path=str(path))
    finally:
        provider_admin._llm_lock.reset(token)
    await provider_admin.gated_llm_http(
        None, "POST", "https://llm.wavespeed.ai/v1/chat/completions", headers={},
        json_body={"model": "deepseek/deepseek-v4.1-flash-1017", "messages": [{"role": "user", "content": "hi"}]},
        transport=transport, ledger_path=str(path))
    assert calls == [
        ("GET", "https://api.deepseek.com/models"),
        ("POST", "http://127.0.0.1:9/mcp"),
        ("POST", "https://llm.wavespeed.ai/v1/chat/completions"),
    ]
    assert not path.exists()


def test_primary_summary_retry_overflow_and_legacy_go_through_the_wrapper():
    send = inspect.getsource(LocalLlmProvider.send)
    assert send.count("_llm_request_fit(") >= 1
    assert "COMFYART_AGENT_BUDGET_LOOP" in send
    request = inspect.getsource(LocalLlmProvider._llm_request)
    assert request.count("_request_json(") >= 1
    assert "while True" in request
    fit = inspect.getsource(LocalLlmProvider._llm_request_fit)
    assert fit.count("_llm_request(") >= 2
    summary = inspect.getsource(LocalLlmProvider._summarize_llm)
    assert "_request_json(" in summary
    assert "_llm_request(" not in summary
    loop = inspect.getsource(agent_loop.run)
    assert "_llm_request_fit(" in loop
    install = inspect.getsource(provider_admin.install)
    assert "gated_llm_http(" in install
    wrapper = inspect.getsource(provider_admin.gated_llm_http)
    assert "adapt_llm_body(" in wrapper
    assert wrapper.index("adapt_llm_body(") < wrapper.index("dispatch(")


def _reserve_record(nano: int, rid: str | None = None) -> dict:
    return {
        "id": rid or uuid.uuid4().hex,
        "status": "reserved",
        "reserved_nano": nano,
        "actual_nano": None,
        "retain_reason": "",
        "input_bound": 0,
        "max_output_tokens": 1,
        "model": "deepseek-flash",
        "route": {},
        "snapshot": price_snapshot("deepseek-flash"),
        "created_at": 0,
    }


def test_authorized_two_dollar_scope_is_independent_and_immutable(tmp_path):
    """$2 is an explicit new scope. Opening will not upgrade or reset a default ledger.

    A used default ledger with stamped reservations stays at $0.05 if the ceiling
    or authorization fields are edited. That is not a seal against rewriting an
    empty file's authorization field.
    """
    gate_src = Path(llm_usd_gate.__file__).read_text()
    assert "0.3439" not in gate_src
    assert "343_900_000" not in gate_src and "343900000" not in gate_src
    assert "open_authorized_scope(" not in inspect.getsource(llm_usd_gate.dispatch)
    assert "resolved_ledger_path(" in inspect.getsource(llm_usd_gate.dispatch)
    assert "open_authorized_scope(" not in inspect.getsource(llm_usd_gate.default_ledger_path)
    assert "data = _fresh()" in inspect.getsource(llm_usd_gate._mutate)
    assert "TWO_DOLLAR" not in inspect.getsource(llm_usd_gate._mutate)
    install = inspect.getsource(provider_admin.install)
    wrapper = inspect.getsource(provider_admin.gated_llm_http)
    assert "open_authorized_scope" not in install + wrapper
    assert "use_authorized_scope" not in install + wrapper
    assert "TWO_DOLLAR" not in install + wrapper
    assert "2_000_000_000" not in install + wrapper
    assert "ledger_path" not in install
    assert TWO_DOLLAR_CEILING_NANO == 2_000_000_000
    assert TWO_DOLLAR_CEILING_NANO != CEILING_NANO
    assert DEFAULT_AUTHORIZATION == "default-0.05"
    assert TWO_DOLLAR_AUTHORIZATION == "explicit-2.00"

    default_path = tmp_path / "default.json"
    first = reserve_nano(str(default_path), nano=1_000_000, record=_reserve_record(1_000_000, "d1"))
    assert first["ok"] is True
    default_state = ledger_state(str(default_path))
    assert default_state["ceiling_nano"] == CEILING_NANO
    assert default_state["authorization"] == DEFAULT_AUTHORIZATION
    assert default_state["authorized_ceiling_nano"] == CEILING_NANO
    assert default_state["accounted_nano"] == 1_000_000

    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(default_path), TWO_DOLLAR_CEILING_NANO)
    assert ledger_state(str(default_path))["ceiling_nano"] == CEILING_NANO
    assert ledger_state(str(default_path))["accounted_nano"] == 1_000_000

    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(tmp_path / "bad.json"), 343_900_000)
    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(tmp_path / "bad2.json"), CEILING_NANO + 1)
    assert not (tmp_path / "bad.json").exists()
    assert not (tmp_path / "bad2.json").exists()

    two_path = tmp_path / "two.json"
    opened = open_authorized_scope(str(two_path), TWO_DOLLAR_CEILING_NANO)
    assert opened["ok"] is True
    assert opened["ceiling_nano"] == TWO_DOLLAR_CEILING_NANO
    assert opened["accounted_nano"] == 0
    assert opened["scope_id"] != default_state["scope_id"]
    two_state = ledger_state(str(two_path))
    assert two_state["authorization"] == TWO_DOLLAR_AUTHORIZATION
    assert two_state["authorized_ceiling_nano"] == TWO_DOLLAR_CEILING_NANO
    assert two_state["accounted_nano"] == 0
    assert two_state["scope_id"] != default_state["scope_id"]

    before = two_path.read_text()
    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(two_path), TWO_DOLLAR_CEILING_NANO)
    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(two_path), CEILING_NANO)
    assert two_path.read_text() == before

    # A $2 reservation is allowed; the default ledger is unchanged and does not absorb it.
    big = reserve_nano(str(two_path), nano=1_500_000_000, record=_reserve_record(1_500_000_000, "t1"))
    assert big["ok"] is True and big["ceiling_nano"] == TWO_DOLLAR_CEILING_NANO
    assert ledger_state(str(default_path))["accounted_nano"] == 1_000_000
    assert ledger_state(str(two_path))["accounted_nano"] == 1_500_000_000

    # Tampering cannot raise the $2 cap or turn a default ledger into $2.
    raw = json.loads(two_path.read_text())
    raw["ceiling_nano"] = 10 ** 12
    raw["authorized_ceiling_nano"] = 10 ** 12
    two_path.write_text(json.dumps(raw))
    denied = reserve_nano(str(two_path), nano=600_000_000, record=_reserve_record(600_000_000, "t2"))
    assert denied["ok"] is False and denied["ceiling_nano"] == TWO_DOLLAR_CEILING_NANO
    assert ledger_state(str(two_path))["accounted_nano"] == 1_500_000_000
    assert ledger_state(str(two_path))["authorized_ceiling_nano"] == TWO_DOLLAR_CEILING_NANO

    forged = json.loads(default_path.read_text())
    forged["authorization"] = TWO_DOLLAR_AUTHORIZATION
    forged["authorized_ceiling_nano"] = TWO_DOLLAR_CEILING_NANO
    forged["ceiling_nano"] = TWO_DOLLAR_CEILING_NANO
    default_path.write_text(json.dumps(forged))
    still = reserve_nano(str(default_path), nano=60_000_000, record=_reserve_record(60_000_000, "d2"))
    assert still["ok"] is False and still["ceiling_nano"] == CEILING_NANO
    sealed = ledger_state(str(default_path))
    assert sealed["ceiling_nano"] == CEILING_NANO
    assert sealed["authorization"] == DEFAULT_AUTHORIZATION
    assert sealed["accounted_nano"] == 1_000_000


def test_two_dollar_concurrent_reservations_are_atomic(tmp_path):
    path = str(tmp_path / "two-conc.json")
    open_authorized_scope(path, TWO_DOLLAR_CEILING_NANO)
    piece = 1_200_000_000

    def once(_n):
        return reserve_nano(path, nano=piece, record=_reserve_record(piece))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(once, range(8)))
    assert sum(1 for row in results if row["ok"]) == 1
    state = ledger_state(path)
    assert state["accounted_nano"] == piece
    assert state["ceiling_nano"] == TWO_DOLLAR_CEILING_NANO
    assert state["accounted_nano"] <= state["ceiling_nano"]
    assert sum(1 for row in state["reservations"].values() if row["status"] == "reserved") == 1


async def test_two_dollar_timeout_malformed_usage_and_summary_shaped_body_reserve_separately(tmp_path):
    """Direct dispatch of timeout, missing usage, and a summary-shaped body each reserve separately.

    This does not go through LocalLlmProvider._llm_request retries, _summarize_llm,
    or _llm_request_fit overflow. Those provider paths are covered on the default
    $0.05 scope by test_summary_retry_and_overflow_each_preflight.
    """
    path = tmp_path / "two-calls.json"
    opened = open_authorized_scope(str(path), TWO_DOLLAR_CEILING_NANO)
    assert opened["accounted_nano"] == 0

    boost = _text()
    boost.pop("max_tokens", None)
    boost["thinking"] = {"type": "enabled"}
    boost["reasoning_effort"] = "low"
    per = worst_case_nano(price_snapshot("deepseek-flash"), 0, MEMORY_BOOST_OUTPUT_DEFAULT)
    assert per == MEMORY_BOOST_OUTPUT_DEFAULT * 1200
    assert per > CEILING_NANO
    assert per * 2 <= TWO_DOLLAR_CEILING_NANO

    async def timeout():
        raise asyncio.TimeoutError()

    with pytest.raises(asyncio.TimeoutError):
        await dispatch(dict(boost), route=_route(), url=URL, send=timeout,
                       ledger_path=str(path), bound_fn=_zero_bound)

    async def empty_usage():
        return {"choices": []}

    # A second attempt (retry-shaped) reserves again; unknown usage is retained.
    await dispatch(dict(boost), route=_route(), url=URL, send=empty_usage,
                   ledger_path=str(path), bound_fn=_zero_bound)

    summary = {
        "model": "deepseek-flash",
        "temperature": 0.1,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": "summarize"},
            {"role": "user", "content": "Previous summary:\n(none)\n\nTurns that just left the context:\nuser: hi"},
        ],
    }
    await dispatch(dict(summary), route=_route(), url=URL, send=empty_usage,
                   ledger_path=str(path), bound_fn=_zero_bound)

    state = ledger_state(str(path))
    assert state["scope_id"] == opened["scope_id"]
    assert len(state["reservations"]) == 3
    statuses = [row["status"] for row in state["reservations"].values()]
    assert statuses.count("retained") == 3
    summary_cap = SUMMARY_OUTPUT_DEFAULT * 1200
    assert state["accounted_nano"] == per * 2 + summary_cap
    reasons = {row["retain_reason"] for row in state["reservations"].values()}
    assert "transport:TimeoutError" in reasons
    assert "missing_or_malformed_usage" in reasons

    held = state["accounted_nano"]
    fill = TWO_DOLLAR_CEILING_NANO - held - (per - 1)
    assert fill > 0
    filled = reserve_nano(str(path), nano=fill, record=_reserve_record(fill, "fill"))
    assert filled["ok"] is True
    with pytest.raises(LlmBudgetBlocked) as blocked:
        await dispatch(dict(boost), route=_route(), url=URL, send=empty_usage,
                       ledger_path=str(path), bound_fn=_zero_bound)
    assert blocked.value.code == "over_budget"
    after = ledger_state(str(path))
    assert after["accounted_nano"] == held + fill
    assert len(after["reservations"]) == 4


async def test_explicit_output_caps_thinking_boost_and_summary_are_preserved(tmp_path):
    """Documented defaults are written when omitted; an explicit max_tokens is never lowered."""
    assert ORDINARY_OUTPUT_DEFAULT == 8192
    assert SUMMARY_OUTPUT_DEFAULT == 8192
    assert MEMORY_BOOST_OUTPUT_DEFAULT == 65536
    assert reasoning_boost.reasoning_params("https://api.deepseek.com", "deepseek-flash") == {
        "reasoning_effort": "low",
        "thinking": {"type": "enabled"},
    }
    summary_src = inspect.getsource(LocalLlmProvider._summarize_llm)
    assert "_request_json(" in summary_src
    assert "max_tokens" not in summary_src
    assert "never shrink" in (apply_output_cap.__doc__ or "").lower()

    ordinary = _text()
    ordinary.pop("max_tokens", None)
    assert apply_output_cap(ordinary) == (ORDINARY_OUTPUT_DEFAULT, "")
    assert ordinary["max_tokens"] == ORDINARY_OUTPUT_DEFAULT

    omitted = {"model": "deepseek-flash", "messages": [{"role": "user", "content": "hi"}]}
    assert apply_output_cap(omitted) == (MEMORY_BOOST_OUTPUT_DEFAULT, "")

    summary = {
        "model": "deepseek-flash",
        "temperature": 0.1,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": "summarize"},
            {"role": "user", "content": "Previous summary:\n(none)"},
        ],
    }
    summary_body = dict(summary)
    assert apply_output_cap(summary_body) == (SUMMARY_OUTPUT_DEFAULT, "")
    assert summary_body["max_tokens"] == SUMMARY_OUTPUT_DEFAULT

    boost = {
        "model": "deepseek-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.2,
        "reasoning_effort": "low",
        "thinking": {"type": "enabled"},
    }
    boost_default = dict(boost)
    assert apply_output_cap(boost_default) == (MEMORY_BOOST_OUTPUT_DEFAULT, "")
    assert boost_default["max_tokens"] == MEMORY_BOOST_OUTPUT_DEFAULT

    explicit = dict(boost)
    explicit["max_tokens"] = 100
    assert apply_output_cap(explicit) == (100, "")
    assert explicit["max_tokens"] == 100

    huge = dict(boost)
    huge["max_tokens"] = 393216
    assert apply_output_cap(huge) == (393216, "")
    assert huge["max_tokens"] == 393216

    default_path = tmp_path / "cap-default.json"
    thinking = dict(boost)
    pre = prepare(thinking, _route(), URL, _zero_bound)
    assert pre["ok"] is True
    assert thinking["max_tokens"] == MEMORY_BOOST_OUTPUT_DEFAULT
    assert pre["reserved_nano"] == MEMORY_BOOST_OUTPUT_DEFAULT * 1200
    assert pre["reserved_nano"] > CEILING_NANO

    async def empty_usage():
        return {"choices": []}

    with pytest.raises(LlmBudgetBlocked) as blocked:
        await dispatch(thinking, route=_route(), url=URL, send=empty_usage,
                       ledger_path=str(default_path), bound_fn=_zero_bound)
    assert blocked.value.code == "over_budget"
    assert thinking["max_tokens"] == MEMORY_BOOST_OUTPUT_DEFAULT
    assert not default_path.exists() or ledger_state(str(default_path))["accounted_nano"] == 0

    two_path = tmp_path / "cap-two.json"
    open_authorized_scope(str(two_path), TWO_DOLLAR_CEILING_NANO)
    allowed = dict(boost)
    await dispatch(allowed, route=_route(), url=URL, send=empty_usage,
                   ledger_path=str(two_path), bound_fn=_zero_bound)
    assert allowed["max_tokens"] == MEMORY_BOOST_OUTPUT_DEFAULT
    two_state = ledger_state(str(two_path))
    assert two_state["accounted_nano"] == MEMORY_BOOST_OUTPUT_DEFAULT * 1200
    assert next(iter(two_state["reservations"].values()))["max_output_tokens"] == MEMORY_BOOST_OUTPUT_DEFAULT

    # An explicit cap that cannot fit the default $0.05 scope is rejected, not reduced.
    shrink = _text(max_tokens=393216)
    with pytest.raises(LlmBudgetBlocked) as too_big:
        await dispatch(shrink, route=_route(), url=URL, send=empty_usage,
                       ledger_path=str(tmp_path / "cap-shrink.json"), bound_fn=_zero_bound)
    assert too_big.value.code == "over_budget"
    assert shrink["max_tokens"] == 393216


async def test_bound_authorized_scope_is_used_when_transport_omits_ledger_path(tmp_path, monkeypatch):
    """The official wrapper omits ledger_path; a bound opened $2 scope must be consumed."""
    default_path = tmp_path / "default.json"
    two_path = tmp_path / "two.json"
    monkeypatch.setattr(llm_usd_gate, "default_ledger_path", lambda: str(default_path))
    with pytest.raises(LlmScopeConflict):
        use_authorized_scope(str(two_path))
    opened = open_authorized_scope(str(two_path), TWO_DOLLAR_CEILING_NANO)
    bound = use_authorized_scope(str(two_path))
    assert bound["ok"] is True
    assert bound["path"] == str(two_path)
    assert bound["scope_id"] == opened["scope_id"]
    assert bound["ceiling_nano"] == TWO_DOLLAR_CEILING_NANO
    assert resolved_ledger_path() == str(two_path)
    assert resolved_ledger_path(str(default_path)) == str(default_path)

    boost = {
        "model": "deepseek-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.2,
        "reasoning_effort": "low",
        "thinking": {"type": "enabled"},
    }
    seen = {}

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        seen["body"] = json_body
        return {"choices": []}

    token = provider_admin._llm_lock.set(_route())
    try:
        # Same calling shape as install(): no ledger_path argument.
        await provider_admin.gated_llm_http(
            None, "POST", URL, headers={}, json_body=boost,
            transport=transport, bound_fn=_zero_bound)
    finally:
        provider_admin._llm_lock.reset(token)
    assert seen["body"]["max_tokens"] == MEMORY_BOOST_OUTPUT_DEFAULT
    assert seen["body"]["thinking"] == {"type": "enabled"}
    two_state = ledger_state(str(two_path))
    assert two_state["accounted_nano"] == MEMORY_BOOST_OUTPUT_DEFAULT * 1200
    assert two_state["ceiling_nano"] == TWO_DOLLAR_CEILING_NANO
    assert not default_path.exists()

    clear_authorized_scope()
    assert resolved_ledger_path() == str(default_path)
    denied_body = dict(boost)
    token = provider_admin._llm_lock.set(_route())
    try:
        with pytest.raises(LlmBudgetBlocked) as blocked:
            await provider_admin.gated_llm_http(
                None, "POST", URL, headers={}, json_body=denied_body,
                transport=transport, bound_fn=_zero_bound)
    finally:
        provider_admin._llm_lock.reset(token)
    assert blocked.value.code == "over_budget"
    # adapt_llm_body copies the body, so the caller's dict is not silently reduced.
    assert "max_tokens" not in denied_body
    assert ledger_state(str(two_path))["accounted_nano"] == MEMORY_BOOST_OUTPUT_DEFAULT * 1200
    if default_path.exists():
        assert ledger_state(str(default_path))["ceiling_nano"] == CEILING_NANO
        assert ledger_state(str(default_path))["accounted_nano"] == 0


async def test_post_adapter_summary_and_thinking_boost_caps_are_on_the_http_body(tmp_path):
    """Output ceilings are applied after adapt_llm_body, on the body the transport sends."""
    seen = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        seen.append(dict(json_body))
        return _usage(0, 1)

    summary = {
        "model": "deepseek-flash",
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "summarize"},
            {"role": "user", "content": "Previous summary:\n(none)"},
        ],
    }
    boost = {
        "model": "deepseek-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.2,
        **reasoning_boost.reasoning_params("https://api.deepseek.com", "deepseek-flash"),
    }
    ordinary = _text()
    ordinary.pop("max_tokens", None)
    ordinary.pop("thinking", None)

    # A thinking-default reservation is $0.0786 and cannot fit the default $0.05 scope.
    open_authorized_scope(str(tmp_path / "boost.json"), TWO_DOLLAR_CEILING_NANO)
    token = provider_admin._llm_lock.set(_route())
    try:
        for name, body in (("ordinary", ordinary), ("summary", summary), ("boost", boost)):
            await provider_admin.gated_llm_http(
                None, "POST", URL, headers={}, json_body=body,
                transport=transport, ledger_path=str(tmp_path / f"{name}.json"),
                bound_fn=_zero_bound)
    finally:
        provider_admin._llm_lock.reset(token)
    assert [row["max_tokens"] for row in seen] == [
        ORDINARY_OUTPUT_DEFAULT, SUMMARY_OUTPUT_DEFAULT, MEMORY_BOOST_OUTPUT_DEFAULT,
    ]
    assert seen[0]["thinking"] == {"type": "disabled"}
    assert seen[1]["thinking"] == {"type": "disabled"}
    assert seen[2]["thinking"] == {"type": "enabled"}
    assert seen[2]["reasoning_effort"] == "low"
    assert ordinary.get("max_tokens") is None
    assert "max_tokens" not in summary
    assert "max_tokens" not in boost


async def test_install_wrapper_uses_bound_two_dollar_scope_for_real_summary_retry_and_overflow(
        tmp_path, monkeypatch):
    """Production install() wrapper, real LocalLlmProvider methods, bound $2 scope.

    This is not the same as dispatching a similarly shaped body. The proved input
    bound is injected only here by replacing official_input_bound; install() is
    not given ledger_path or bound_fn.
    """
    provider = get_provider("local-llm")
    if provider is None:
        pytest.fail(
            "install() wrapper coverage needs get_provider('local-llm'); "
            "AgentLlmProvider was not registered"
        )
    if not getattr(provider_admin.install, "done", False):
        provider_admin.install()
    if not getattr(provider_admin.install, "done", False) or provider_admin._llm_http is None:
        pytest.fail(
            "install() did not wrap local-llm._request_json; cannot cover the official wrapper"
        )
    wrapper = inspect.getsource(provider._request_json)
    assert "gated_llm_http(" in wrapper
    assert "ledger_path" not in wrapper
    assert "bound_fn" not in wrapper

    default_path = tmp_path / "default.json"
    two_path = tmp_path / "two.json"
    monkeypatch.setattr(llm_usd_gate, "default_ledger_path", lambda: str(default_path))
    monkeypatch.setattr(llm_usd_gate, "official_input_bound", _zero_bound)
    monkeypatch.setattr(local_llm, "_RETRY_BACKOFF_S", (0.0, 0.0))
    open_authorized_scope(str(two_path), TWO_DOLLAR_CEILING_NANO)
    use_authorized_scope(str(two_path))

    calls = []

    async def fake_http(session, method, url, *, headers, json_body=None, timeout=120):
        body = dict(json_body or {})
        calls.append(body)
        n = len(calls)
        if n == 1:
            return {"choices": [{"message": {"content": "sum"}}]}
        if n == 2:
            raise asyncio.TimeoutError()
        if n == 4:
            raise LlmHttpError(400, "maximum context length is 8192 tokens. prompt is too long")
        return _usage(0, 1)

    saved_http = provider_admin._llm_http
    token = provider_admin._llm_lock.set(_route())
    try:
        provider_admin._llm_http = fake_http
        text = await provider._summarize_llm(
            None, "https://api.deepseek.com", "deepseek-flash", "prev", "old turn")
        assert text == "sum"
        await provider._llm_request(None, URL, _text(max_tokens=1000), _emit, TurnHandle())
        data, window = await provider._llm_request_fit(
            None, URL, _text(max_tokens=1000), _emit, TurnHandle(),
            model="deepseek-flash", window=1_000_000,
            refit=lambda messages, new_window: messages)
        assert window == 8192
        assert data["usage"]["completion_tokens"] == 1
        boost = {
            "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.2,
            **reasoning_boost.reasoning_params("https://api.deepseek.com", "deepseek-flash"),
        }
        await provider._llm_request(None, URL, boost, _emit, TurnHandle())
        assert "max_tokens" not in boost
    finally:
        provider_admin._llm_http = saved_http
        provider_admin._llm_lock.reset(token)

    assert [row.get("max_tokens") for row in calls] == [
        SUMMARY_OUTPUT_DEFAULT, 1000, 1000, 1000, 1000, MEMORY_BOOST_OUTPUT_DEFAULT,
    ]
    assert calls[0]["thinking"] == {"type": "disabled"}
    assert calls[1]["max_tokens"] == 1000 and calls[2]["max_tokens"] == 1000
    assert calls[3]["max_tokens"] == 1000 and calls[4]["max_tokens"] == 1000
    assert calls[5]["thinking"] == {"type": "enabled"}
    assert calls[5]["reasoning_effort"] == "low"

    state = ledger_state(str(two_path))
    assert state["ceiling_nano"] == TWO_DOLLAR_CEILING_NANO
    assert state["authorization"] == TWO_DOLLAR_AUTHORIZATION
    assert len(state["reservations"]) == 6
    retained = [row for row in state["reservations"].values() if row["status"] == "retained"]
    reconciled = [row for row in state["reservations"].values() if row["status"] == "reconciled"]
    assert len(retained) == 3 and len(reconciled) == 3
    reasons = {row["retain_reason"] for row in retained}
    assert "missing_or_malformed_usage" in reasons
    assert "transport:TimeoutError" in reasons
    assert "transport:LlmHttpError" in reasons
    held = (sum(row["reserved_nano"] for row in retained)
            + sum(row["actual_nano"] for row in reconciled))
    assert state["accounted_nano"] == held
    assert not default_path.exists()

    clear_authorized_scope()
    token = provider_admin._llm_lock.set(_route())
    try:
        provider_admin._llm_http = fake_http
        with pytest.raises(LlmBudgetBlocked) as blocked:
            await provider._llm_request(
                None, URL,
                {"model": "deepseek-flash", "messages": [{"role": "user", "content": "hi"}],
                 "temperature": 0.2, "reasoning_effort": "low",
                 "thinking": {"type": "enabled"}},
                _emit, TurnHandle())
    finally:
        provider_admin._llm_http = saved_http
        provider_admin._llm_lock.reset(token)
    assert blocked.value.code == "over_budget"
    assert ledger_state(str(two_path))["accounted_nano"] == held
    if default_path.exists():
        unused = ledger_state(str(default_path))
        assert unused["ceiling_nano"] == CEILING_NANO
        assert unused["accounted_nano"] == 0
