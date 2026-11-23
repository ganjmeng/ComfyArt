"""Six industry templates: the canvas relay's apply_generate, with submit stubbed.

plan_for alone does not prove a generate_image call. This drives the real
generate_image handler and records the body that would have been submitted.
Nothing is sent to WaveSpeed.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from ComfyArt.api import brand_identity as brand
from ComfyArt.api import paid_guard
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID

PRESETS = ("geometric", "handmade", "tech", "beauty", "foodbev", "pet")
SENT: list[tuple[str, dict]] = []


@pytest.fixture
def relay(monkeypatch):
    SENT.clear()
    brand.reset_for_tests()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        return {"ids": ["holder-stub"], "model": args.get("edit_model") or args.get("model") or "stub"}

    async def no_approval(_label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)
    yield
    brand.reset_for_tests()


def _run(**args):
    chat = paid_guard.noturn_key(f"brand-{uuid.uuid4().hex}")
    guard = GUARD_CHAT_ID.set(chat)
    bot = BOT_CHAT_ID.set(chat)
    try:
        return asyncio.run(canvas.TOOLS["generate_image"]["handler"](args))
    finally:
        BOT_CHAT_ID.reset(bot)
        GUARD_CHAT_ID.reset(guard)
        paid_guard.TURNS.pop(chat, None)


def test_six_templates_submit_three_square_then_one_board(relay):
    for pid in PRESETS:
        SENT.clear()
        stage1 = [_run(skill=brand.SKILL, preset=pid, prompt=f"{pid} direction {i}") for i in range(3)]
        assert len(SENT) == 3, (pid, stage1, SENT)
        for out, (_action, body) in zip(stage1, SENT):
            assert out.get("submitted") is not False and "brand_slot" not in body, (pid, out, body)
            assert (body["width"], body["height"], body["ratio"], body["stage"], body["count"]) == (
                1024, 1024, "1:1", 1, 1), (pid, body)
            assert body["preset"] == pid and body.get("size_lock") is True
        SENT.clear()
        stage2 = _run(skill=brand.SKILL, preset=pid, stage=2, prompt=f"{pid} board")
        assert len(SENT) == 1, (pid, stage2)
        body = SENT[0][1]
        assert (body["width"], body["height"], body["ratio"], body["stage"], body["count"]) == (
            2048, 1152, "16:9", 2, 1), (pid, body)
        assert body["preset"] == pid
        assert "brand_slot" not in body


def test_no_template_does_not_use_the_stub_as_a_1024_board(relay):
    out = _run(skill=brand.SKILL, prompt="栖木咖啡")
    assert SENT == []
    assert out.get("submitted") is False
    assert out.get("width") != 1024


def test_unknown_preset_still_submits_the_first_template(relay):
    out = _run(skill=brand.SKILL, preset="nope", prompt="direction")
    assert len(SENT) == 1, out
    body = SENT[0][1]
    assert (body["width"], body["height"], body["preset"], body["stage"]) == (1024, 1024, "geometric", 1)
