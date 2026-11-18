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
from ComfyArt.bot import agent_loop, llm_usd_gate, local_llm
from ComfyArt.bot.llm_usd_gate import (
    CEILING_NANO,
    CHAT_URL,
    PRICES,
    TOKEN_URL,
    VISION_URL,
    Bound,
    LlmBudgetBlocked,
    apply_output_cap,
    dispatch,
    ledger_state,
    official_input_bound,
    price_snapshot,
    reserve_nano,
    settle,
    structural_block,
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
    assert official_input_bound(tools, snap).code == "unbounded_tools"
    assert CHAT_URL in official_input_bound(tools, snap).detail
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

    def forbid(body, snapshot):
        raise AssertionError("a tool body must not be authorized by a replacement bound")

    with pytest.raises(LlmBudgetBlocked) as tool_block:
        await once(_route(), tools, forbid)
    assert tool_block.value.code == "unbounded_tools"

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
                transport=transport, ledger_path=str(path), bound_fn=_zero_bound)
        assert legacy_block.value.code == "unbounded_tools"
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
