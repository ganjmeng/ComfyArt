"""Fail-closed $0.05 gate for the official direct DeepSeek route. Fake transport only.

The production input bound does not authorize a send. Tests that exercise the
reservation ledger pass an explicit text-only bound. That bound is not the
character-count heuristic and is not a WaveSpeed price.
"""
from __future__ import annotations

import asyncio
import base64
import errno
import inspect
import io
import os
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
    bind_llm_project,
    current_llm_project,
    reset_llm_project,
    CEILING_NANO,
    CHAT_URL,
    DEFAULT_AUTHORIZATION,
    MEMORY_BOOST_OUTPUT_DEFAULT,
    ORDINARY_OUTPUT_DEFAULT,
    PRICES,
    SUMMARY_OUTPUT_DEFAULT,
    SKILL_CALL_CAP_NANO,
    SKILL_CUMULATIVE_STOP_NANO,
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
    retain,
    settle,
    structural_block,
    use_authorized_scope,
    clear_authorized_scope,
    worst_case_nano,
)
from ComfyArt.bot.local_llm import LlmHttpError, LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest

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
    llm_usd_gate._write_fault = None
    yield
    llm_usd_gate._write_fault = None
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
    tiny = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOoWHACAAN0AeF2Y/iPAAAAAElFTkSuQmCC"
    image = _text()
    image["messages"] = [{"role": "user", "content": [
        {"type": "text", "text": "look"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + tiny}},
    ]}]
    assert structural_block(image) == "unbounded_multimodal"
    proven = official_input_bound(image, snap)
    assert proven.ok is True and proven.image_tokens == 1024
    assert proven.tokens == proven.text_bytes + 1024
    assert proven.tokens != len(tiny)
    unproven = _text()
    unproven["messages"] = [{"role": "user", "content": [
        {"type": "text", "text": "look"},
        {"type": "file", "file_id": "not-a-measured-url"},
    ]}]
    blocked = official_input_bound(unproven, snap)
    assert blocked.ok is False and blocked.code == "unbounded_multimodal"
    assert VISION_URL in blocked.detail
    web = _text()
    web["tools"] = [{"type": "function", "function": {"name": "deepseek_web_search", "parameters": {}}}]
    assert structural_block(web) == "unpriced_tool_fee"


_TINY_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOoWHACAAN0AeF2Y/iPAAAAAElFTkSuQmCC"


def _image_turn(url: str, *, system: str = "plan the product", tools: bool = True) -> dict:
    body = {
        "model": "deepseek-flash",
        "temperature": 0.2,
        "thinking": {"type": "disabled"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": "参考图已附上，请写九宫格方案"},
                {"type": "image_url", "image_url": {"url": url}},
            ]},
        ],
    }
    if tools:
        body["tools"] = [{
            "type": "function",
            "function": {
                "name": "ask_user",
                "description": "ask",
                "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}},
            },
        }]
        body["tool_choice"] = "auto"
    return body


async def test_image_first_turn_passes_over_bound_blocks_and_text_is_unchanged(tmp_path):
    """Default-route image turn: proven byte bound, image still sent, no real socket.

    A no-image body keeps the old unbounded_billed_input refusal. A payload whose
    worst case exceeds $0.50 never reaches transport. A second payload-byte hold
    that would pass $0.40 is refused, and the first reservation stays.
    """
    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(json_body)
        return _usage(1, 1)

    path = tmp_path / "skill.json"
    route = _route()
    url = "https://api.deepseek.com/chat/completions"
    small = _image_turn("data:image/png;base64," + _TINY_PNG)
    token = provider_admin._llm_lock.set(route)
    try:
        await provider_admin.gated_llm_http(
            None, "POST", url, headers={}, json_body=small,
            transport=transport, ledger_path=str(path))
    finally:
        provider_admin._llm_lock.reset(token)
    assert len(calls) == 1
    sent = calls[0]
    urls = [part["image_url"]["url"] for msg in sent["messages"] if isinstance(msg.get("content"), list)
            for part in msg["content"] if part.get("type") == "image_url"]
    assert urls == ["data:image/png;base64," + _TINY_PNG]
    pre = prepare(dict(small), route, url)
    assert pre["ok"] is True
    assert pre["input_evidence"]["mode"] == "planner_image_cap"
    assert pre["input_evidence"]["image_tokens"] == 1024
    assert pre["input_tokens"] == pre["text_bytes"] + 1024
    assert pre["input_tokens"] != len(_TINY_PNG)
    assert pre["reserved_nano"] <= SKILL_CALL_CAP_NANO
    assert pre["reserved_nano"] <= SKILL_CUMULATIVE_STOP_NANO
    plain = _text()
    plain["tools"] = small["tools"]
    plain["tool_choice"] = "auto"
    plain["messages"] = [
        {"role": "system", "content": "plan the product"},
        {"role": "user", "content": "参考图已附上，请写九宫格方案"},
    ]
    same = official_input_bound(plain, price_snapshot("deepseek-flash"))
    assert same.ok is False and same.code == "unbounded_billed_input"
    assert "not a guarantee" in same.detail
    before = len(calls)
    token = provider_admin._llm_lock.set(route)
    try:
        with pytest.raises(LlmBudgetBlocked) as text_blocked:
            await provider_admin.gated_llm_http(
                None, "POST", url, headers={}, json_body=plain,
                transport=transport, ledger_path=str(path))
    finally:
        provider_admin._llm_lock.reset(token)
    assert text_blocked.value.code == "unbounded_billed_input"
    assert len(calls) == before

    remote = _image_turn("https://example.com/photo.png")
    token = provider_admin._llm_lock.set(route)
    try:
        with pytest.raises(LlmBudgetBlocked) as remote_blocked:
            await provider_admin.gated_llm_http(
                None, "POST", url, headers={}, json_body=remote,
                transport=transport, ledger_path=str(tmp_path / "remote.json"))
    finally:
        provider_admin._llm_lock.reset(token)
    assert remote_blocked.value.code == "unbounded_multimodal"
    from PIL import Image as _Image
    solid = _Image.new("RGB", (4000, 4000), (200, 10, 10))
    blob = io.BytesIO()
    solid.save(blob, format="PNG")
    raw_png = blob.getvalue()
    assert len(raw_png) < 80_000
    huge_px = _image_turn("data:image/png;base64," + base64.b64encode(raw_png).decode())
    assert official_input_bound(huge_px, price_snapshot("deepseek-flash")).code == "image_too_large"
    from ComfyArt.bot.local_llm import _user_content
    planned = _user_content("看这张图", [{"data": base64.b64encode(raw_png).decode(), "media_type": "image/png"}])
    planned_url = planned[1]["image_url"]["url"]
    planned_im = _Image.open(io.BytesIO(base64.b64decode(planned_url.split(",", 1)[1])))
    assert max(planned_im.size) == 1568
    planned_body = _image_turn(planned_url)
    planned_bound = official_input_bound(planned_body, price_snapshot("deepseek-flash"))
    assert planned_bound.ok and planned_bound.image_tokens == 1024
    assert planned_bound.tokens != len(raw_png)
    stored = {"data": base64.b64encode(raw_png).decode(), "media_type": "image/png"}
    original_field = stored["data"]
    _user_content("看这张图", [stored])
    assert stored["data"] == original_field
    from ComfyArt.api import wavespeed
    import os
    root = wavespeed.folder_paths.get_directory_by_type("input")
    os.makedirs(root, exist_ok=True)
    dest = os.path.join(root, "solid4000.png")
    with open(dest, "wb") as f:
        f.write(raw_png)
    from ComfyArt.bot.ref_orientation import ref_image_bytes
    assert ref_image_bytes(["/api/view?filename=solid4000.png&type=input"]) == raw_png
    from ComfyArt.bot.llm_usd_gate import user_notice
    notices = {
        "image_too_large": (
            "参考图太大，暂时无法发送，本次未产生费用。请压缩或换一张图片再试。",
            "This reference image is too large to send. You haven't been charged. Compress it or try a different image.",
            "llm.imageTooLarge",
        ),
        "unbounded_multimodal": (
            "这张参考图无法直接读取，本次未产生费用。请下载后直接上传再试。",
            "This reference image can't be read directly. You haven't been charged. Download it and upload it directly, then try again.",
            "llm.imageUnreadable",
        ),
        "over_budget": (
            "本项目用量已达上限，已暂停发送，未产生费用。新建项目可继续使用。",
            "This project has reached its usage limit. Sending is paused and you haven't been charged. Start a new project to continue.",
            "llm.overBudget",
        ),
        "unbounded_billed_input": (
            "这条消息暂时无法发送，未产生费用，请稍后再试。",
            "This message can't be sent right now. You haven't been charged. Please try again later.",
            "llm.messageBlocked",
        ),
    }
    root = Path(__file__).resolve().parents[1]
    locales = json.loads((root / "src/locales/zh.json").read_text(encoding="utf-8"))
    locales_en = json.loads((root / "src/locales/en.json").read_text(encoding="utf-8"))
    for code, (zh, en, key) in notices.items():
        assert user_notice(code, "zh") == zh and user_notice(code, "en") == en
        assert locales[key] == zh and locales_en[key] == en
        assert "Blocked before HTTP" not in zh and "Blocked before HTTP" not in en
        assert "token" not in zh.lower() and "token" not in en.lower()
    assert len(calls) == before
    assert not (tmp_path / "remote.json").exists()

    huge = _image_turn("data:image/png;base64," + _TINY_PNG, system="x" * 1_700_000)
    token = provider_admin._llm_lock.set(route)
    try:
        with pytest.raises(LlmBudgetBlocked) as over:
            await provider_admin.gated_llm_http(
                None, "POST", url, headers={}, json_body=huge,
                transport=transport, ledger_path=str(tmp_path / "over.json"))
    finally:
        provider_admin._llm_lock.reset(token)
    assert over.value.code == "image_too_large"
    assert len(calls) == before
    assert not (tmp_path / "over.json").exists()

    # About $0.25 each, so the second call would pass the $0.40 cumulative stop.
    medium = _image_turn("data:image/png;base64," + _TINY_PNG, system="y" * 800_000)
    first = prepare(dict(medium), route, url)
    assert first["ok"] is True
    assert SKILL_CUMULATIVE_STOP_NANO // 2 < first["reserved_nano"] <= SKILL_CUMULATIVE_STOP_NANO
    held_calls = []

    async def retain_transport(session, method, url, *, headers, json_body=None, timeout=120):
        held_calls.append(json_body)
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    token = provider_admin._llm_lock.set(route)
    try:
        await provider_admin.gated_llm_http(
            None, "POST", url, headers={}, json_body=medium,
            transport=retain_transport, ledger_path=str(tmp_path / "cum.json"))
        held = ledger_state(str(tmp_path / "cum.json"))["accounted_nano"]
        with pytest.raises(LlmBudgetBlocked) as second:
            await provider_admin.gated_llm_http(
                None, "POST", url, headers={}, json_body=medium,
                transport=retain_transport, ledger_path=str(tmp_path / "cum.json"))
    finally:
        provider_admin._llm_lock.reset(token)
    assert second.value.code == "over_budget"
    assert ledger_state(str(tmp_path / "cum.json"))["accounted_nano"] == held
    assert len(held_calls) == 1
    assert len(calls) == before


@pytest.mark.asyncio
async def test_default_flow_reaches_unconfirmed_quote_inside_the_cap(tmp_path, monkeypatch):
    """Chinese multi-angle path, mocked transport, production pixel bound. Quote stays unconfirmed."""
    import os
    from ComfyArt.api import bot_asks, bot_turns, chat_store, mcp, multi_angle as ma
    from ComfyArt.api.mcp_tools import TOOLS, canvas
    from ComfyArt.api.mcp_tools import bot_tools
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from ComfyArt.bot.guide import CORE_MCP_TOOLS
    from ComfyArt.bot.providers import TurnHandle, TurnRequest
    from multi_angle_plan_fixture import HEADPHONES_PLAN
    from test_agent_budget_391 import calls, reply

    chat = chat_store.create_chat(user="default", project="flow-bound", provider="local-llm")
    cid = chat["id"]
    ref = "/api/view?filename=ma_subject_691.png&type=input"
    chat_store.create_message(chat_id=cid, role="user", blocks=[
        {"type": "skill", "name": ma.SKILL}, {"type": "text", "text": "商品详情页，纯白无缝背景"},
        {"type": "image", "url": ref}])
    assistant = chat_store.create_message(chat_id=cid, role="assistant", blocks=[], status="running")
    handle = TurnHandle()
    monkeypatch.setitem(bot_turns.ACTIVE_TURNS, cid, bot_turns._TurnState(handle, cid, assistant["id"]))
    quotes, seen, submitted = [], [], []
    solid = __import__("PIL").Image.new("RGB", (4000, 4000), (180, 20, 20))
    blob = io.BytesIO(); solid.save(blob, format="PNG"); raw = blob.getvalue()
    root = __import__("ComfyArt.api.wavespeed", fromlist=["folder_paths"]).folder_paths.get_directory_by_type("input")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "ma_subject_691.png"), "wb") as f:
        f.write(raw)
    script = [calls(("ask_user", {"prompt": "setup"})),
              calls(("generate_image", {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                        "refs": [ref], "multi_angle_stage": "preview"})),
              reply("方案已列出，等待确认。")]

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        if (json_body or {}).get("method") == "tools/list":
            return {"result": {"tools": [
                {"name": name, "description": spec.get("description") or "", "inputSchema": spec.get("inputSchema") or {"type": "object"}}
                for name, spec in TOOLS.items() if name in CORE_MCP_TOOLS]}}
        if not str(url).endswith("/chat/completions"):
            return {"data": [{"id": "deepseek-flash", "context_length": 1000000}]}
        seen.append(json_body)
        return script[len(seen) - 1]

    async def real_mcp(session, endpoint, name, arguments):
        out = await mcp._tools_call({"name": name, "arguments": arguments})
        return next(b["text"] for b in out["content"] if b["type"] == "text"), []

    def answer_broadcast(event, payload):
        if event != "turn_ask":
            return
        if payload.get("kind") == "plan_quote":
            quotes.append(payload)
            bot_asks.resolve_ask(payload["ask_id"], "cancelled", selected=["cancel"])
            return
        answers = {}
        ids = {q["id"] for q in payload.get("questions") or []}
        if ma.SOURCE in ids:
            answers[ma.SOURCE] = {"selected": ["single_front"]}
        if ma.ASPECT in ids:
            answers[ma.ASPECT] = {"selected": ["1:1"]}
        bot_asks.validate_answer(payload, [], "", answers)
        bot_asks.resolve_ask(payload["ask_id"], "answered", answers=answers)

    provider = LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")

    async def _request_json(session, method, url, *, headers, json_body=None, timeout=120):
        return await provider_admin.gated_llm_http(
            session, method, url, headers=headers, json_body=json_body, timeout=timeout,
            transport=transport, ledger_path=str(tmp_path / "flow.json"), bound_fn=None)

    provider._request_json = _request_json
    provider._mcp_call_tool = real_mcp
    provider._context_window = lambda *a: _async_return(1000000)
    provider._price_call = lambda *a, **k: _async_return(None)
    provider._price_one = lambda *a, **k: _async_return(None)
    provider._models_for = lambda *a: _async_return([])
    provider._run_store = lambda: None
    monkeypatch.setattr(bot_tools, "broadcast", answer_broadcast)
    monkeypatch.setattr(canvas, "submit_command", lambda *a, **k: submitted.append(a) or _async_return({"ids": []}))
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "bytedance/seedream-v4", "category": "auto", "auto": True})
    monkeypatch.setattr(canvas, "unregistered_model", lambda *a, **k: None)
    monkeypatch.setattr(canvas, "load_config", lambda: {"features": {}})
    token = provider_admin._llm_lock.set(_route())
    chat_token = BOT_CHAT_ID.set(cid)
    from ComfyArt.api import paid_guard
    paid_guard.begin_turn(cid, text="商品详情页", provider_text="商品详情页")
    try:
        result = await provider.send(TurnRequest(
            chat_id=cid, user_text="Use the ComfyArt skill for this task. 商品详情页，纯白无缝背景",
            goal_text="商品详情页，纯白无缝背景", lang="zh",
            mcp_endpoint="http://mock-no-network/mcp", model="deepseek-flash",
            attachments=[{"data": base64.b64encode(raw).decode(), "media_type": "image/png"}]), _emit, handle)
    finally:
        paid_guard.end_turn(cid)
        provider_admin._llm_lock.reset(token)
        BOT_CHAT_ID.reset(chat_token)
        bot_turns.ACTIVE_TURNS.pop(cid, None)
        bot_asks.cancel_chat_asks(cid)
    assert not result.error, (result.error, len(seen))
    assert quotes, "the unconfirmed quote card was not shown"
    blob = json.dumps(quotes[0], ensure_ascii=False)
    assert "线稿预览" in blob and "1152" in blob and "2048" in blob
    assert quotes[0].get("status") != "answered"
    assert not submitted
    snap = price_snapshot("deepseek-flash")
    rows = []
    held = 0
    for body in seen:
        pre = prepare(body, _route(), "https://api.deepseek.com/chat/completions")
        assert pre["ok"], pre
        held += pre["reserved_nano"]
        rows.append({"body_bytes": pre["body_bytes"], "image_bytes": pre["image_bytes"],
                     "image_tokens": pre["input_evidence"]["image_tokens"], "text_bytes": pre["text_bytes"],
                     "max_tokens": pre["max_output_tokens"], "usd": pre["reserved_nano"] / 1e9})
    assert held <= SKILL_CUMULATIVE_STOP_NANO
    report = {"rows": rows, "cumulative_nano": held, "rates": {
        "input_miss_peak_nano": snap["input_miss_peak_nano"], "output_peak_nano": snap["output_peak_nano"]}}
    (tmp_path / "flow-rows.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    Path("/tmp/flow-rows.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _planner_record(nano: int, project: str) -> dict:
    return {
        "id": uuid.uuid4().hex, "status": "reserved", "reserved_nano": nano,
        "actual_nano": None, "retain_reason": "", "input_bound": 1000,
        "max_output_tokens": 8192, "model": "deepseek-flash", "route": {},
        "snapshot": price_snapshot("deepseek-flash"), "created_at": 0,
        "project_id": project,
        "input_evidence": {"mode": "planner_image_cap", "input_tokens": 1000},
    }


def test_planner_stop_is_per_project_and_survives_a_new_process(tmp_path):
    """$0.40 is per project. $0.50 is still per call. A new process reads the same file."""
    path = str(tmp_path / "projects.json")
    quarter = 250_000_000
    first = reserve_nano(path, nano=quarter, record=_planner_record(quarter, "alpha"))
    assert first["ok"] is True
    again = reserve_nano(path, nano=quarter, record=_planner_record(quarter, "alpha"))
    assert again["ok"] is False and again["code"] == "over_budget"
    other = reserve_nano(path, nano=quarter, record=_planner_record(quarter, "beta"))
    assert other["ok"] is True
    fresh = reserve_nano(path, nano=quarter, record=_planner_record(quarter, "gamma"))
    assert fresh["ok"] is True
    too_big = reserve_nano(path, nano=SKILL_CALL_CAP_NANO + 1, record=_planner_record(SKILL_CALL_CAP_NANO + 1, "delta"))
    assert too_big["ok"] is False and too_big["code"] == "over_budget"
    token = bind_llm_project("canvas-9")
    try:
        assert current_llm_project() == "canvas-9"
    finally:
        reset_llm_project(token)
    assert "current_llm_project()" in inspect.getsource(llm_usd_gate.dispatch)
    assert "bind_llm_project(" in inspect.getsource(local_llm.LocalLlmProvider.send)
    script = (
        "import importlib.util, sys, uuid\n"
        "spec = importlib.util.spec_from_file_location('llm_usd_gate', sys.argv[1])\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "nano = 250_000_000\n"
        "snap = mod.price_snapshot('deepseek-flash')\n"
        "def record(project):\n"
        "    return {'id': uuid.uuid4().hex, 'status': 'reserved', 'reserved_nano': nano,\n"
        "            'actual_nano': None, 'retain_reason': '', 'input_bound': 1000,\n"
        "            'max_output_tokens': 8192, 'model': 'deepseek-flash', 'route': {},\n"
        "            'snapshot': snap, 'created_at': 0, 'project_id': project,\n"
        "            'input_evidence': {'mode': 'planner_image_cap', 'input_tokens': 1000}}\n"
        "blocked = mod.reserve_nano(sys.argv[2], nano=nano, record=record('alpha'))\n"
        "assert blocked['ok'] is False and blocked['code'] == 'over_budget', blocked\n"
        "opened = mod.reserve_nano(sys.argv[2], nano=nano, record=record('restart-new'))\n"
        "assert opened['ok'] is True, opened\n"
    )
    subprocess.check_call([sys.executable, "-c", script, str(Path(llm_usd_gate.__file__).resolve()), path])


@pytest.mark.asyncio
async def test_undecodable_attachment_shows_unreadable_copy_and_does_not_send(tmp_path):
    from ComfyArt.bot.llm_usd_gate import user_notice
    from ComfyArt.bot.providers import TurnHandle, TurnRequest
    sent = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        if str(url).endswith("/chat/completions"):
            sent.append(json_body)
            return {"choices": [{"message": {"role": "assistant", "content": "no"}}]}
        if (json_body or {}).get("method") == "tools/list":
            return {"result": {"tools": []}}
        return {"data": [{"id": "deepseek-flash", "context_length": 1000000}]}

    provider = LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")

    async def _request_json(session, method, url, *, headers, json_body=None, timeout=120):
        return await provider_admin.gated_llm_http(
            session, method, url, headers=headers, json_body=json_body, timeout=timeout,
            transport=transport, ledger_path=str(tmp_path / "unread.json"), bound_fn=None)

    provider._request_json = _request_json
    provider._run_store = lambda: None
    token = provider_admin._llm_lock.set(_route())
    try:
        result = await provider.send(TurnRequest(
            chat_id="unread-chat", user_text="看这张图", lang="zh", model="deepseek-flash",
            mcp_endpoint="http://mock-no-network/mcp", project_id="local",
            attachments=[{"data": "QUJD", "media_type": "image/jpeg"}]), _emit, TurnHandle())
    finally:
        provider_admin._llm_lock.reset(token)
    assert result.error == user_notice("unbounded_multimodal", "zh")
    assert "Blocked before HTTP" not in result.error
    assert sent == []
    assert not (tmp_path / "unread.json").exists()


def test_tool_images_use_the_planner_jpeg_and_unreadable_ones_stay_blocked():
    from PIL import Image as _Image
    from ComfyArt.bot.llm_usd_gate import user_notice
    from ComfyArt.bot.local_llm import planner_image_url
    solid = _Image.new("RGB", (2000, 1000), (8, 16, 32))
    blob = io.BytesIO()
    solid.save(blob, format="PNG")
    raw_url = "data:image/png;base64," + base64.b64encode(blob.getvalue()).decode()
    planned = planner_image_url(raw_url)
    assert planned.startswith("data:image/jpeg;base64,")
    with _Image.open(io.BytesIO(base64.b64decode(planned.split(",", 1)[1]))) as im:
        assert im.size == (1568, 784)
    kept = planner_image_url("data:image/png;base64,QUJD")
    assert kept == "data:image/png;base64,QUJD"
    blocked = official_input_bound(_image_turn(kept), price_snapshot("deepseek-flash"))
    assert blocked.code == "unbounded_multimodal"
    assert user_notice(blocked.code, "en").startswith("This reference image can't be read directly")
    assert "planner_image_url(" in inspect.getsource(local_llm.LocalLlmProvider._emit_mcp)
    assert "planner_image_url(" in inspect.getsource(local_llm.LocalLlmProvider._run_fallback_tool)


async def _async_return(value):
    return value


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
    assert "installed_llm_http(" in install
    assert "gated_llm_http(" in inspect.getsource(provider_admin.installed_llm_http)
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
    assert "_fresh()" in inspect.getsource(llm_usd_gate._load_ledger)
    assert "TWO_DOLLAR" not in inspect.getsource(llm_usd_gate._load_ledger)
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
    assert "installed_llm_http(" in wrapper
    assert "gated_llm_http(" in inspect.getsource(provider_admin.installed_llm_http)
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


class _CrashAfter(Exception):
    """In-process stand-in for a crash at a ledger persist stage."""


def _crash_at(*stages: str):
    def hook(stage: str) -> None:
        if stage in stages:
            raise _CrashAfter(stage)
    return hook


@pytest.mark.parametrize("stage", [
    "before_temp",
    "after_temp_write",
    "after_temp_fsync",
    "before_replace",
])
def test_crash_before_replace_keeps_prior_reservations(tmp_path, stage):
    """A crash before os.replace must not empty the ledger or call _fresh()."""
    path = str(tmp_path / "ledger.json")
    first = reserve_nano(path, nano=10_000_000, record=_reserve_record(10_000_000, "kept"))
    assert first["ok"] is True
    before = ledger_state(path)
    assert before["accounted_nano"] == 10_000_000
    assert Path(path + ".activated").is_file()
    lock_ino = Path(path + ".lock").stat().st_ino
    prior = Path(path).read_text()

    llm_usd_gate._write_fault = _crash_at(stage)
    with pytest.raises(_CrashAfter) as crashed:
        reserve_nano(path, nano=1_000_000, record=_reserve_record(1_000_000, "lost"))
    assert crashed.value.args == (stage,)
    llm_usd_gate._write_fault = None

    assert Path(path).read_text() == prior
    state = ledger_state(path)
    assert state["scope_id"] == before["scope_id"]
    assert state["accounted_nano"] == 10_000_000
    assert "kept" in state["reservations"] and "lost" not in state["reservations"]
    assert Path(path + ".lock").stat().st_ino == lock_ino


@pytest.mark.parametrize("stage", ["after_replace", "after_dir_fsync"])
def test_crash_after_replace_keeps_the_new_reservation(tmp_path, stage):
    """Once replace has returned, this filesystem shows the new ledger.

    Parent-directory fsync is still performed. That is not a proof of power-loss
    durability on every mount.
    """
    path = str(tmp_path / "ledger.json")
    first = reserve_nano(path, nano=10_000_000, record=_reserve_record(10_000_000, "kept"))
    scope = first["scope_id"]

    llm_usd_gate._write_fault = _crash_at(stage)
    with pytest.raises(_CrashAfter) as crashed:
        reserve_nano(path, nano=1_000_000, record=_reserve_record(1_000_000, "new"))
    assert crashed.value.args == (stage,)
    llm_usd_gate._write_fault = None

    state = ledger_state(path)
    assert state["scope_id"] == scope
    assert state["accounted_nano"] == 11_000_000
    assert set(state["reservations"]) == {"kept", "new"}


def test_activated_empty_or_missing_ledger_is_fail_closed(tmp_path):
    path = Path(tmp_path / "ledger.json")
    first = reserve_nano(str(path), nano=10_000_000, record=_reserve_record(10_000_000, "kept"))
    marker = Path(str(path) + ".activated")
    assert marker.is_file()
    marker_text = marker.read_text()

    path.write_text("")
    with pytest.raises(LlmBudgetBlocked) as empty:
        reserve_nano(str(path), nano=1, record=_reserve_record(1, "reset"))
    assert empty.value.code == "ledger_unreadable"
    assert empty.value.detail == "activated_missing_or_empty"
    assert path.read_text() == ""
    assert marker.read_text() == marker_text
    with pytest.raises(LlmBudgetBlocked) as empty_state:
        ledger_state(str(path))
    assert empty_state.value.detail == "activated_missing_or_empty"
    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(path), TWO_DOLLAR_CEILING_NANO)

    path.unlink()
    with pytest.raises(LlmBudgetBlocked) as missing:
        reserve_nano(str(path), nano=1, record=_reserve_record(1, "reset2"))
    assert missing.value.code == "ledger_unreadable"
    assert missing.value.detail == "activated_missing_or_empty"
    assert not path.exists()
    assert marker.is_file()


def test_explicit_first_init_and_legacy_ledger_without_marker(tmp_path):
    fresh_path = tmp_path / "fresh.json"
    first = reserve_nano(str(fresh_path), nano=1_000_000, record=_reserve_record(1_000_000, "a"))
    assert first["ok"] is True
    assert (tmp_path / "fresh.json.activated").is_file()
    assert (tmp_path / "fresh.json.lock").is_file()
    again = reserve_nano(str(fresh_path), nano=1_000_000, record=_reserve_record(1_000_000, "b"))
    assert again["scope_id"] == first["scope_id"]
    assert ledger_state(str(fresh_path))["accounted_nano"] == 2_000_000

    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({
        "version": 1,
        "scope_id": "usd-legacy",
        "authorization": DEFAULT_AUTHORIZATION,
        "authorized_ceiling_nano": CEILING_NANO,
        "ceiling_nano": CEILING_NANO,
        "accounted_nano": 20_000_000,
        "reservations": {
            "old": {
                "id": "old", "status": "reserved", "reserved_nano": 20_000_000,
                "actual_nano": None, "retain_reason": "", "input_bound": 0,
                "max_output_tokens": 1, "authorization": DEFAULT_AUTHORIZATION,
                "authorized_ceiling_nano": CEILING_NANO,
            }
        },
    }))
    assert not (tmp_path / "legacy.json.activated").exists()
    added = reserve_nano(str(legacy), nano=1_000_000, record=_reserve_record(1_000_000, "new"))
    assert added["ok"] is True
    assert added["scope_id"] == "usd-legacy"
    state = ledger_state(str(legacy))
    assert state["accounted_nano"] == 21_000_000
    assert "old" in state["reservations"] and "new" in state["reservations"]
    assert (tmp_path / "legacy.json.activated").is_file()


def test_lock_inode_survives_replace_and_restart_keeps_scope(tmp_path):
    path = str(tmp_path / "ledger.json")
    first = reserve_nano(path, nano=10_000_000, record=_reserve_record(10_000_000, "kept"))
    lock = Path(path + ".lock")
    lock_ino = lock.stat().st_ino
    reserve_nano(path, nano=5_000_000, record=_reserve_record(5_000_000, "second"))
    assert lock.stat().st_ino == lock_ino

    script = (
        "import importlib.util, json, sys\n"
        "spec = importlib.util.spec_from_file_location('llm_usd_gate', sys.argv[1])\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "state = mod.ledger_state(sys.argv[2])\n"
        "print(json.dumps(state))\n"
    )
    out = subprocess.check_output(
        [sys.executable, "-c", script, str(Path(llm_usd_gate.__file__).resolve()), path],
        text=True,
    )
    restarted = json.loads(out)
    assert restarted["scope_id"] == first["scope_id"]
    assert restarted["accounted_nano"] == 15_000_000
    assert set(restarted["reservations"]) == {"kept", "second"}
    assert Path(path + ".lock").stat().st_ino == lock_ino


_CHILD = Path(__file__).resolve().parent / "_llm_usd_gate_child.py"
_GATE_FILE = Path(llm_usd_gate.__file__).resolve()
_EXIT_FAULT = 91


def _run_child(*args: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_CHILD), str(_GATE_FILE), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _fresh_state(path: str) -> dict:
    """Reopen the ledger in a new interpreter after a child exit."""
    proc = _run_child("state", path)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_ledger_state_is_readonly_and_does_not_write_marker(tmp_path):
    path = tmp_path / "legacy.json"
    raw = json.dumps({
        "version": 1,
        "scope_id": "usd-readonly",
        "authorization": DEFAULT_AUTHORIZATION,
        "authorized_ceiling_nano": CEILING_NANO,
        "ceiling_nano": CEILING_NANO,
        "accounted_nano": 20_000_000,
        "reservations": {
            "old": {
                "id": "old", "status": "reserved", "reserved_nano": 20_000_000,
                "actual_nano": None, "retain_reason": "", "input_bound": 0,
                "max_output_tokens": 1, "authorization": DEFAULT_AUTHORIZATION,
                "authorized_ceiling_nano": CEILING_NANO,
            }
        },
    }, separators=(",", ":"))
    path.write_text(raw)
    marker = Path(str(path) + ".activated")
    assert not marker.exists()
    writes = []
    saved = (
        llm_usd_gate._persist_ledger,
        llm_usd_gate._write_activation_marker,
        llm_usd_gate._atomic_write,
    )

    def banned(*_args, **_kwargs):
        writes.append(1)
        raise AssertionError("ledger_state must not write")

    llm_usd_gate._persist_ledger = banned
    llm_usd_gate._write_activation_marker = banned
    llm_usd_gate._atomic_write = banned
    try:
        state = ledger_state(str(path))
    finally:
        (
            llm_usd_gate._persist_ledger,
            llm_usd_gate._write_activation_marker,
            llm_usd_gate._atomic_write,
        ) = saved
    assert writes == []
    assert state["scope_id"] == "usd-readonly"
    assert state["accounted_nano"] == 20_000_000
    assert path.read_text() == raw
    assert not marker.exists()


def test_marker_only_or_ledger_only_does_not_reset_funds(tmp_path):
    path = Path(tmp_path / "scope.json")
    opened = open_authorized_scope(str(path), CEILING_NANO)
    reserved = reserve_nano(str(path), nano=10_000_000, record=_reserve_record(10_000_000, "kept"))
    assert reserved["ok"] is True
    scope = reserved["scope_id"]
    marker = Path(str(path) + ".activated")
    assert marker.is_file()

    # Ledger-only: valid spend, no marker. Must not mint a new scope or zero spend.
    marker.unlink()
    before = path.read_bytes()
    state = ledger_state(str(path))
    assert state["scope_id"] == scope
    assert state["accounted_nano"] == 10_000_000
    assert path.read_bytes() == before
    assert not marker.exists()
    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(path), TWO_DOLLAR_CEILING_NANO)
    assert path.read_bytes() == before
    again = reserve_nano(str(path), nano=1_000_000, record=_reserve_record(1_000_000, "more"))
    assert again["ok"] is True
    assert again["scope_id"] == scope
    assert ledger_state(str(path))["accounted_nano"] == 11_000_000
    assert marker.is_file()

    # Marker-only: empty or missing ledger must not _fresh() new funds.
    marker_text = marker.read_text()
    path.write_text("")
    for call in (
        lambda: reserve_nano(str(path), nano=1, record=_reserve_record(1, "reset")),
        lambda: ledger_state(str(path)),
        lambda: settle(str(path), "kept", None),
        lambda: retain(str(path), "kept", "test"),
        lambda: use_authorized_scope(str(path)),
    ):
        with pytest.raises(LlmBudgetBlocked) as blocked:
            call()
        assert blocked.value.code == "ledger_unreadable"
        assert blocked.value.detail == "activated_missing_or_empty"
    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(path), TWO_DOLLAR_CEILING_NANO)
    assert path.read_text() == ""
    assert marker.read_text() == marker_text

    path.unlink()
    with pytest.raises(LlmBudgetBlocked) as missing:
        reserve_nano(str(path), nano=1, record=_reserve_record(1, "reset2"))
    assert missing.value.detail == "activated_missing_or_empty"
    with pytest.raises(LlmBudgetBlocked):
        use_authorized_scope(str(path))
    with pytest.raises(LlmScopeConflict):
        open_authorized_scope(str(path), CEILING_NANO)
    assert not path.exists()
    assert marker.is_file()


def test_dir_fsync_failure_holds_reservation_and_does_not_send(tmp_path):
    path = str(tmp_path / "ledger.json")
    open_authorized_scope(path, CEILING_NANO)
    reserve_nano(path, nano=10_000_000, record=_reserve_record(10_000_000, "kept"))
    sent = []

    async def send():
        sent.append("sent")
        return {"id": "fake", "choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    def fail_fsync(stage: str) -> None:
        if stage == "dir_fsync":
            raise OSError("injected directory fsync failure")

    llm_usd_gate._write_fault = fail_fsync
    with pytest.raises(OSError, match="injected directory fsync failure"):
        asyncio.run(dispatch(
            _text(max_tokens=1), route=_route(), url=URL, send=send,
            ledger_path=path, bound_fn=_zero_bound,
        ))
    llm_usd_gate._write_fault = None
    assert sent == []
    state = ledger_state(path)
    assert "kept" in state["reservations"]
    assert state["accounted_nano"] > 10_000_000
    assert len(state["reservations"]) == 2


@pytest.mark.parametrize("stage", [
    "after_temp_write",
    "after_temp_fsync",
    "before_replace",
])
def test_process_exit_before_replace_does_not_send_or_reset(tmp_path, stage):
    path = str(tmp_path / "ledger.json")
    init = _run_child("init", path, str(CEILING_NANO))
    assert init.returncode == 0, init.stderr
    first = _run_child("reserve", path, "10000000", "kept", "")
    assert first.returncode == 0, first.stderr
    before = _fresh_state(path)
    assert before["accounted_nano"] == 10_000_000
    lock_ino = json.loads(_run_child("inos", path).stdout)["lock_ino"]
    sent = str(tmp_path / "sent")

    crashed = _run_child("dispatch", path, sent, stage)
    assert crashed.returncode == _EXIT_FAULT, (crashed.returncode, crashed.stdout, crashed.stderr)
    assert not Path(sent).exists()

    state = _fresh_state(path)
    assert state["scope_id"] == before["scope_id"]
    assert state["accounted_nano"] == 10_000_000
    assert "kept" in state["reservations"]
    assert json.loads(_run_child("inos", path).stdout)["lock_ino"] == lock_ino


@pytest.mark.parametrize("stage", ["after_replace", "dir_fsync", "after_dir_fsync"])
def test_process_exit_after_replace_keeps_conservative_reservation(tmp_path, stage):
    path = str(tmp_path / "ledger.json")
    assert _run_child("init", path, str(CEILING_NANO)).returncode == 0
    first = _run_child("reserve", path, "10000000", "kept", "")
    assert first.returncode == 0, first.stderr
    scope = json.loads(first.stdout)["scope_id"]
    sent = str(tmp_path / "sent")

    crashed = _run_child("dispatch", path, sent, stage)
    assert crashed.returncode == _EXIT_FAULT, (crashed.returncode, crashed.stdout, crashed.stderr)
    assert not Path(sent).exists()

    state = _fresh_state(path)
    assert state["scope_id"] == scope
    assert state["accounted_nano"] > 10_000_000
    assert "kept" in state["reservations"]
    assert len(state["reservations"]) == 2


def test_process_exit_during_first_marker_leaves_ledger_funds(tmp_path):
    """Crash after ledger replace and before the activation marker.

    The next fresh interpreter must see the reserved funds and must not _fresh().
    """
    path = str(tmp_path / "ledger.json")
    # First persist of an explicit init writes the ledger, then the marker.
    crashed = _run_child("init_fault", path, str(CEILING_NANO), "marker_before_replace")
    # init_fault is added below in the child if present; fallback: reserve with
    # no prior marker, inject at marker_before_replace after ledger replace.
    if crashed.returncode == 2 and "unknown action" in crashed.stderr:
        raise AssertionError("child missing init_fault action")
    assert crashed.returncode == _EXIT_FAULT, (crashed.returncode, crashed.stdout, crashed.stderr)
    assert Path(path).is_file()
    assert Path(path).read_text().strip()
    assert not Path(path + ".activated").exists()
    state = _fresh_state(path)
    assert state["accounted_nano"] == 0
    assert state["ceiling_nano"] == CEILING_NANO
    # A later update must keep this scope, not mint a default replacement.
    added = _run_child("reserve", path, "10000000", "kept", "")
    assert added.returncode == 0, added.stderr
    after = _fresh_state(path)
    assert after["scope_id"] == state["scope_id"]
    assert after["accounted_nano"] == 10_000_000
    assert Path(path + ".activated").is_file()


def test_separate_processes_contend_on_lock_while_ledger_inode_replaced(tmp_path):
    path = str(tmp_path / "ledger.json")
    assert _run_child("init", path, str(CEILING_NANO)).returncode == 0
    first = _run_child("reserve", path, "5000000", "seed", "")
    assert first.returncode == 0, first.stderr
    before_inos = json.loads(_run_child("inos", path).stdout)
    lock_ino = before_inos["lock_ino"]
    assert lock_ino is not None
    assert Path(path + ".lock").is_file()

    procs = [
        subprocess.Popen(
            [sys.executable, str(_CHILD), str(_GATE_FILE), "reserve", path, "5000000", f"p{i}", ""],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for i in range(12)
    ]
    codes = [proc.wait(15) for proc in procs]
    assert codes == [0] * 12, [proc.stderr.read() if proc.stderr else "" for proc in procs]
    state = _fresh_state(path)
    # $0.05 / 5_000_000 = 10; seed already used one slot → 9 more succeed, 3 denied
    ok = sum(1 for row in state["reservations"].values() if row["status"] == "reserved")
    assert state["accounted_nano"] == ok * 5_000_000
    assert state["accounted_nano"] <= CEILING_NANO
    assert ok == 10
    after_inos = json.loads(_run_child("inos", path).stdout)
    assert after_inos["lock_ino"] == lock_ino
    # The ledger inode may change when os.replace installs a new file.
    assert after_inos["ledger_ino"] is not None


REASONING_TEXT = "I will inspect the canvas first."


def test_reasoning_content_is_whitelisted_on_assistant_history():
    snap = price_snapshot("deepseek-flash")
    body = _text(max_tokens=8192)
    body["thinking"] = {"type": "enabled"}
    body["tools"] = [
        {"type": "function", "function": {"name": "get_canvas", "parameters": {"type": "object"}}},
    ]
    body["tool_choice"] = "auto"
    body["messages"] = [
        {"role": "user", "content": "draw a card"},
        {
            "role": "assistant",
            "content": None,
            "reasoning_content": REASONING_TEXT,
            "tool_calls": [{
                "id": "call_canvas",
                "type": "function",
                "function": {"name": "get_canvas", "arguments": "{}"},
            }],
        },
        {"role": "tool", "tool_call_id": "call_canvas", "content": "canvas is empty"},
    ]
    assert structural_block(body) == ""
    prod = official_input_bound(body, snap)
    assert prod.ok is False and prod.code == "unbounded_billed_input"

    text_only = _text(max_tokens=8192)
    text_only["thinking"] = {"type": "enabled"}
    text_only["messages"] = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello", "reasoning_content": REASONING_TEXT},
    ]
    assert structural_block(text_only) == ""

    bad_type = dict(body)
    bad_type["messages"] = list(body["messages"])
    bad_type["messages"][1] = dict(body["messages"][1], reasoning_content=1)
    assert structural_block(bad_type) == "unbounded_tools"

    unknown = dict(body)
    unknown["messages"] = list(body["messages"])
    unknown["messages"][1] = dict(body["messages"][1], reasoning="not-canonical")
    assert structural_block(unknown) == "unbounded_tools"


async def test_two_round_fake_http_replays_reasoning_content_with_thinking_and_tools(tmp_path, monkeypatch):
    """Official thinking+tools: the second request must echo reasoning_content.

    The fake server returns 400 when that field is dropped. The test does not
    disable thinking to avoid the 400. Model and MCP tools stay unchanged.
    """
    think = REASONING_TEXT
    calls = []
    two_path = tmp_path / "two.json"
    # Thinking-on default 64K output cannot fit the $0.05 ceiling; use an explicit
    # local $2 scope. This does not disable thinking and is not a live activation.
    open_authorized_scope(str(two_path), TWO_DOLLAR_CEILING_NANO)

    async def no_plan(ctx, turn, handle, messages):
        return None

    monkeypatch.setattr("ComfyArt.bot.shot_plan.run_plan_card", no_plan)

    provider = LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")
    monkeypatch.setattr(local_llm, "_RETRY_BACKOFF_S", (0.0, 0.0))

    async def ctx_window(session, model):
        return 32_000

    monkeypatch.setattr(provider, "_context_window", ctx_window)
    monkeypatch.setattr(provider, "_run_store", lambda: None)

    async def fake_call(session, endpoint, name, arguments):
        assert name == "get_canvas"
        return '{"shapes": []}', []

    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)

    async def fake_http(session, method, url, *, headers, json_body=None, timeout=120):
        if not str(url).endswith("/chat/completions"):
            return {"result": {"tools": [{"name": "get_canvas"}]}}
        body = json_body or {}
        calls.append(body)
        # Do not disable thinking to make this pass.
        thinking = body.get("thinking")
        assert thinking != {"type": "disabled"}
        msgs = body.get("messages") or []
        if len(calls) == 1:
            return {
                "id": "r1",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": think,
                        "tool_calls": [{
                            "id": "call_canvas",
                            "type": "function",
                            "function": {"name": "get_canvas", "arguments": "{}"},
                        }],
                    }
                }],
                "usage": {
                    "prompt_tokens": 8, "completion_tokens": 16, "total_tokens": 24,
                    "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 8,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
            }
        prior = [m for m in msgs if m.get("role") == "assistant" and m.get("tool_calls")]
        if not prior or prior[-1].get("reasoning_content") != think:
            raise LlmHttpError(400, "official thinking+tools requires reasoning_content")
        return {
            "id": "r2",
            "choices": [{"message": {"role": "assistant", "content": "the canvas is empty", "tool_calls": []}}],
            "usage": {
                "prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18,
                "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 12,
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        }

    # Route the production HTTP wrapper so the gate sees the replay body, with a
    # test input bound only. Thinking stays enabled on this official-style body.
    token = provider_admin._llm_lock.set(_route())

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        body = json_body or {}
        if str(url).endswith("/chat/completions"):
            if body.get("thinking") == {"type": "disabled"}:
                raise AssertionError("test must not disable thinking to pass")
        return await fake_http(session, method, url, headers=headers, json_body=json_body, timeout=timeout)

    async def _request_json(session, method, url, *, headers, json_body=None, timeout=120):
        body = dict(json_body or {})
        if str(url).endswith("/chat/completions"):
            # Official thinking+tools scenario: enable thinking before adapt so
            # setdefault(disabled) cannot flip it off to avoid the protocol 400.
            body["thinking"] = {"type": "enabled"}
        return await provider_admin.gated_llm_http(
            session, method, url, headers=headers, json_body=body, timeout=timeout,
            transport=transport, ledger_path=str(two_path), bound_fn=_zero_bound)

    provider._request_json = _request_json
    events = []

    async def emit(ev):
        events.append(ev)

    try:
        result = await provider.send(
            TurnRequest(
                chat_id="c",
                user_text="look at the canvas",
                lang="en",
                mcp_endpoint="http://x/mcp",
                model="deepseek-flash",
            ),
            emit,
            TurnHandle(),
        )
    finally:
        provider_admin._llm_lock.reset(token)

    assert result.error == ""
    assert len(calls) >= 2
    assert calls[0]["model"] == "deepseek-flash"
    assert calls[1]["model"] == "deepseek-flash"
    assert calls[0].get("thinking") == {"type": "enabled"}
    assert calls[1].get("thinking") == {"type": "enabled"}
    assert any(
        (t.get("function") or {}).get("name") == "get_canvas" or t.get("name") == "get_canvas"
        for t in (calls[1].get("tools") or [])
    )
    prior = [m for m in calls[1]["messages"] if m.get("role") == "assistant" and m.get("tool_calls")]
    assert prior and prior[-1]["reasoning_content"] == think
    assert any(m.get("role") == "tool" and m.get("tool_call_id") == "call_canvas" for m in calls[1]["messages"])
    assert any(getattr(ev, "t", None) == "thinking" and think in (getattr(ev, "text", "") or "") for ev in events)


# R1: exercise the actual os.write return contract, below the persist hooks.
def _inject_r1_writes(monkeypatch, target: Path, mode: str):
    real_open = os.open
    real_write = os.write
    real_replace = os.replace
    opened = {}
    writes = []
    replacements = []

    def tracking_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        # Record every open: a closed target descriptor can be reused by a later
        # ledger, marker or directory open during this same dispatch.
        opened[fd] = os.fspath(path)
        return fd

    def injected_write(fd, data):
        if opened.get(fd) != str(target) + ".tmp":
            return real_write(fd, data)
        writes.append(len(data))
        if mode == "zero":
            return 0
        if mode == "enospc" and len(writes) > 1:
            raise OSError(errno.ENOSPC, "injected disk full after short write")
        return real_write(fd, data[:7])

    def tracking_replace(src, dst, *args, **kwargs):
        replacements.append(os.fspath(dst))
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "open", tracking_open)
    monkeypatch.setattr(os, "write", injected_write)
    monkeypatch.setattr(os, "replace", tracking_replace)
    return writes, replacements


def _r1_existing_ledger(tmp_path, target_kind):
    path = tmp_path / "ledger.json"
    reserve_nano(str(path), nano=10_000_000, record=_reserve_record(10_000_000, "kept"))
    marker = Path(str(path) + ".activated")
    before = path.read_bytes()
    state = ledger_state(str(path))
    if target_kind == "marker":
        # Recovery of an already valid, nonzero ledger must write the missing
        # marker, without resetting funds. Its write must be complete too.
        marker.unlink()
    target = path if target_kind == "ledger" else marker
    return path, marker, target, before, state


@pytest.mark.parametrize("target_kind", ["ledger", "marker"])
def test_r1_segmented_writes_complete_before_send(tmp_path, monkeypatch, target_kind):
    path, marker, target, _, before = _r1_existing_ledger(tmp_path, target_kind)
    sent = []
    writes, replacements = _inject_r1_writes(monkeypatch, target, "segmented")

    async def send():
        # Verify both durable JSON documents are complete before transport.
        state = ledger_state(str(path))
        assert state["scope_id"] == before["scope_id"]
        assert state["accounted_nano"] > before["accounted_nano"]
        assert json.loads(marker.read_text())["scope_id"] == state["scope_id"]
        sent.append("sent")
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    asyncio.run(dispatch(
        _text(max_tokens=1), route=_route(), url=URL, send=send,
        ledger_path=str(path), bound_fn=_zero_bound,
    ))
    assert sent == ["sent"]
    assert len(writes) > 1
    assert writes[-1] <= 7
    assert str(target) in replacements
    assert json.loads(target.read_text())["scope_id"] == before["scope_id"]


@pytest.mark.parametrize("target_kind", ["ledger", "marker"])
@pytest.mark.parametrize("mode", ["enospc", "zero"])
def test_r1_incomplete_write_never_replaces_target_or_sends(tmp_path, monkeypatch, target_kind, mode):
    path, marker, target, old_bytes, before = _r1_existing_ledger(tmp_path, target_kind)
    lock_ino = Path(str(path) + ".lock").stat().st_ino
    sent = []
    writes, replacements = _inject_r1_writes(monkeypatch, target, mode)

    async def send():
        sent.append("sent")
        raise AssertionError("incomplete persistent reservation must not send")

    with pytest.raises(OSError) as error:
        asyncio.run(dispatch(
            _text(max_tokens=1), route=_route(), url=URL, send=send,
            ledger_path=str(path), bound_fn=_zero_bound,
        ))
    assert error.value.errno == (errno.ENOSPC if mode == "enospc" else errno.EIO)
    assert len(writes) == (2 if mode == "enospc" else 1)
    assert str(target) not in replacements
    assert sent == []
    assert Path(str(path) + ".lock").stat().st_ino == lock_ino
    state = ledger_state(str(path))
    assert state["scope_id"] == before["scope_id"]
    assert "kept" in state["reservations"]
    if target_kind == "ledger":
        assert path.read_bytes() == old_bytes
        assert state == before
        assert marker.is_file()
    else:
        # Ledger-first ordering means marker failure leaves the additional
        # reservation conservatively held, with a valid ledger and no send.
        assert state["accounted_nano"] > before["accounted_nano"]
        assert len(state["reservations"]) == 2
        assert not marker.exists()
