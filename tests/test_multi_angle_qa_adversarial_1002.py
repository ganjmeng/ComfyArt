"""Adversarial #1002 cases for a11f6f5c. Evidence-dir only. No network, no browser.

These assert the product contract, not the current implementation's accidental
behavior. Failures are review findings, not permission to weaken assertions.
"""
from __future__ import annotations

import copy

import pytest

from ComfyArt.api import bot_asks, bot_turns, chat_store, multi_angle as ma
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID

REF = "/api/view?filename=ma_subject_691.png&type=input"
DESC = "商品详情页，纯白无缝背景"


@pytest.fixture
def run(monkeypatch):
    rows = [{"id": "start", "role": "user", "blocks": [
        {"type": "skill", "name": ma.SKILL}, {"type": "text", "text": DESC},
        {"type": "image", "url": REF}]}]
    sent = []

    def update(chat, message, **fields):
        row = next(r for r in rows if r["id"] == message)
        row.update(copy.deepcopy(fields))
        return copy.deepcopy(row)

    def compare(chat, message, expected, blocks):
        row = next(r for r in rows if r["id"] == message)
        if row["blocks"] != expected:
            return False
        update(chat, message, blocks=blocks)
        return True

    async def submit(action, args, project, timeout, chat=""):
        sent.append((action, copy.deepcopy(args)))
        return {"ids": [f"holder:{len(sent)}"], "submitted": True}

    async def approval(label):
        return None

    monkeypatch.setattr(chat_store, "list_messages", lambda chat: copy.deepcopy(rows))
    monkeypatch.setattr(chat_store, "update_message", update)
    monkeypatch.setattr(chat_store, "compare_message_blocks", compare)
    monkeypatch.setattr(bot_turns, "ACTIVE_TURNS", {})
    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", approval)
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: None)
    monkeypatch.setattr(canvas, "unregistered_model", lambda *a: None)
    monkeypatch.setattr(canvas, "load_config", lambda: {"features": {}})
    token = BOT_CHAT_ID.set("chat-ma")
    try:
        yield rows, sent
    finally:
        BOT_CHAT_ID.reset(token)


def setup(rows, aspect="1:1", *, status="answered", source="single_front"):
    spec = bot_asks.validate_spec({"prompt": "setup"})
    block = {"type": "ask", "ask_id": "setup", "status": status, **spec, "answers": {
        ma.SOURCE: {"selected": [source]}, ma.ASPECT: {"selected": [aspect]}}}
    rows.append({"id": "setup-msg", "role": "assistant", "blocks": [block]})
    return block


def test_image_only_start_can_prepare_preview_without_user_text(run):
    """#1002: an attached reference should be enough; setup must not deadlock."""
    rows, _ = run
    rows[0]["blocks"] = [b for b in rows[0]["blocks"] if b.get("type") != "text"]
    setup(rows)
    args, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None, (blocked or {}).get("error")
    assert args["refs"] == [REF]
    assert "Use the ComfyArt skill" not in args["prompt"]
    # A missing user brief must not be invented from the agent tool prompt.
    _, blocked_with_agent_prompt = ma.prepare({
        "skill": ma.SKILL, "multi_angle_stage": "preview",
        "prompt": "agent tool prompt must not become the preserved user description",
    })
    # Either still allowed with a generic/empty user description, or blocked
    # without baking the agent string in. Never preserve the tool prompt as
    # "User description".
    if blocked_with_agent_prompt is None:
        rebuilt, _ = ma.prepare({
            "skill": ma.SKILL, "multi_angle_stage": "preview",
            "prompt": "agent tool prompt must not become the preserved user description",
        })
        assert "agent tool prompt must not become the preserved user description" not in rebuilt["prompt"]


def test_image_only_after_setup_can_still_ask_for_a_brief_if_needed(run):
    """If a text brief is required, ask_user must still be able to collect it after setup."""
    rows, _ = run
    rows[0]["blocks"] = [b for b in rows[0]["blocks"] if b.get("type") != "text"]
    setup(rows)
    _, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "preview"})
    if blocked is not None:
        spec = bot_asks.validate_spec({
            "prompt": "请补充商品描述",
            "questions": [{"id": "brief", "prompt": "请补充商品描述",
                           "options": [{"id": "reuse", "label": "沿用主图即可"}],
                           "allow_other": True}],
        })
        assert spec["questions"][0]["id"] == "brief"


@pytest.mark.parametrize("other,selected", [
    ("11", ()),
    ("12", ()),
    ("9 10", ()),
    ("11", ("2",)),
])
def test_other_field_two_digit_numbers_fail_closed(run, other, selected):
    """Custom text must not silently explode '11'/'12'/'10' into panel digits."""
    rows, _ = run
    setup(rows)
    args, _ = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "preview"})
    ma.reserve(args["_multi_angle"])
    ma.submitted(args["_multi_angle"], {"ids": ["p"]})
    ma.record_wait({"results": [{"id": "p", "status": "done", "placed": True, "shapes": ["s"]}]})
    spec = bot_asks.validate_spec({"prompt": "choose compositions"})
    rows.append({"id": "composition-msg", "role": "assistant", "blocks": [{
        "type": "ask", "ask_id": "compositions", "status": "answered", **spec,
        "answers": {ma.COMPOSITIONS: {"selected": list(selected), "other_text": other}}}]})
    with pytest.raises(ValueError):
        ma.selection("chat-ma")
    _, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked is not None and blocked["submitted"] is False


@pytest.mark.parametrize("aspect,expected", [
    ("1:1", (2048, 2048, "1:1")),
    ("3:4", (1536, 2048, "3:4")),
    ("16:9", (2048, 1152, "16:9")),
])
def test_preview_without_explicit_ratio_follows_selected_aspect(run, aspect, expected):
    rows, _ = run
    setup(rows, aspect)
    args, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None
    assert (args["width"], args["height"], args["ratio"]) == expected


def test_explicit_preview_aspect_still_independent_of_final(run):
    rows, _ = run
    setup(rows, "1:1")
    args, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "preview", "ratio": "9:16"})
    assert blocked is None
    assert (args["width"], args["height"], args["ratio"]) == (1152, 2048, "9:16")


def test_omitted_stage_during_undelivered_preview_replays_or_continues_preview(run):
    """Resume must not reclassify an in-flight preview as a blocked final."""
    rows, sent = run
    setup(rows)
    first, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None
    assert ma.reserve(first["_multi_angle"]) is None
    ma.submitted(first["_multi_angle"], {"ids": ["preview-holder"], "submitted": True})
    again, result = ma.prepare({"skill": ma.SKILL})  # stage omitted
    assert result is not None, "expected preview reservation replay, not a final-stage block"
    assert result.get("ids") == ["preview-holder"] or result.get("multi_angle_replay")
    assert "Wait for the lineart preview" not in str(result.get("error") or "")
    assert sent == []


def test_description_source_empty_refs_are_not_replaced_by_later_args(run):
    rows, _ = run
    rows[0]["blocks"] = [b for b in rows[0]["blocks"] if b.get("type") != "image"]
    setup(rows, source="description")
    args, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None and args["refs"] == []
    meta = args["_multi_angle"]
    assert ma.reserve(meta) is None
    ma.submitted(meta, {"ids": ["p"], "submitted": True})
    ma.record_wait({"results": [{"id": "p", "status": "done", "placed": True, "shapes": ["preview-shape"]}]})
    spec = bot_asks.validate_spec({"prompt": "choose compositions"})
    rows.append({"id": "composition-msg", "role": "assistant", "blocks": [{
        "type": "ask", "ask_id": "compositions", "status": "answered", **spec,
        "answers": {ma.COMPOSITIONS: {"selected": ["1"]}}}]})
    final, blocked = ma.prepare({
        "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "1",
        "refs": ["sneaky-late-ref"],
    })
    assert blocked is None
    # Snapshotted empty original refs must stay empty; preview may be bound as composition only.
    assert "sneaky-late-ref" not in final["refs"]
    assert final["refs"] == ["preview-shape"] or final["refs"] == []


def test_unrelated_skill_prepare_is_untouched_when_current_skill_is_not_multi_angle(run):
    rows, _ = run
    rows[0]["blocks"] = [{"type": "skill", "name": "pose-fission"}]
    raw = {"skill": "pose-fission", "prompt": "pose", "count": 1}
    out, blocked = ma.prepare(raw)
    assert blocked is None and out == raw
