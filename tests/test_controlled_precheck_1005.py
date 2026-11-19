"""COMFYART_CONTROLLED_PRECHECK_ONLY lets generate_image precheck, not submit."""
from __future__ import annotations

import json

import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN
from test_multi_angle_stages_911 import confirm_quote, run, setup  # noqa: F401

from ComfyArt.api import mcp, multi_angle as ma, paid_guard


def _text(out: dict) -> str:
    return next(b["text"] for b in out["content"] if b["type"] == "text")


@pytest.mark.asyncio
async def test_precheck_returns_the_lineart_quote_and_does_not_call_wavespeed(run, monkeypatch):
    rows, sent = run
    setup(rows, "1:1")
    catalog = []

    async def boom(*_a, **_k):
        catalog.append("catalog")
        return {}

    monkeypatch.setenv("COMFYART_CONTROLLED_PRECHECK_ONLY", "1")
    monkeypatch.setattr("ComfyArt.api.wavespeed.catalog", boom)
    paid_guard.begin_turn("chat-ma", text="商品详情页", provider_text="商品详情页")
    used = dict(paid_guard.TURNS["chat-ma"].used)
    try:
        out = await mcp._tools_call({"name": "generate_image", "arguments": {
            "skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN, "multi_angle_stage": "preview"}})
        after = dict(paid_guard.TURNS["chat-ma"].used)
    finally:
        paid_guard.end_turn("chat-ma")
    body = json.loads(_text(out))
    assert body["next_step"] == "quote_card" and body["quote_card"] == "线稿预览"
    assert body["submitted"] is False
    assert sent == [] and catalog == [] and after == used


@pytest.mark.asyncio
async def test_precheck_pass_is_refused_before_submit(run, monkeypatch):
    rows, sent = run
    setup(rows, "1:1")
    confirm_quote(rows)
    catalog = []

    async def boom(*_a, **_k):
        catalog.append("catalog")
        return {}

    monkeypatch.setenv("COMFYART_CONTROLLED_PRECHECK_ONLY", "1")
    monkeypatch.setattr("ComfyArt.api.wavespeed.catalog", boom)
    paid_guard.begin_turn("chat-ma", text="商品详情页", provider_text="商品详情页")
    used = dict(paid_guard.TURNS["chat-ma"].used)
    try:
        out = await mcp._tools_call({"name": "generate_image", "arguments": {
            "skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN, "multi_angle_stage": "preview"}})
        after = dict(paid_guard.TURNS["chat-ma"].used)
    finally:
        paid_guard.end_turn("chat-ma")
    text = _text(out)
    assert "controlled_precheck_only" in text and "受控模式，生图要等出图步骤" in text
    assert "PermissionError" in text
    assert sent == [] and catalog == [] and after == used


@pytest.mark.asyncio
async def test_without_the_env_a_confirmed_quote_still_submits(run, monkeypatch):
    rows, sent = run
    setup(rows, "1:1")
    confirm_quote(rows)
    monkeypatch.delenv("COMFYART_CONTROLLED_PRECHECK_ONLY", raising=False)
    paid_guard.begin_turn("chat-ma", text="商品详情页", provider_text="商品详情页")
    try:
        out = await mcp._tools_call({"name": "generate_image", "arguments": {
            "skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN, "multi_angle_stage": "preview"}})
    finally:
        paid_guard.end_turn("chat-ma")
    body = json.loads(_text(out))
    assert body.get("submitted") is True and sent
    assert "controlled_precheck_only" not in _text(out)
