"""Quote-card copy: the confirmation reason must be true, and the line spec
comes from this quote's stage snapshot.

Offline only. Prices are injected. No provider, LLM, generation, or ledger.
The default 50-credit confirmation line is not changed, and a skill that
forces a card under that line still asks.
"""
from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN, preview_url
from test_multi_angle_stages_911 import DESC, REF

from ComfyArt.api import bot_asks, bot_turns, chat_store, multi_angle as ma
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.api.wavespeed import DEFAULT_CONFIRM_CREDITS
from ComfyArt.bot.plan_quote import _stage_spec_text, build_quote

ROOT = Path(__file__).resolve().parents[1]


SKILL_STEP = {
    "text": "线稿",
    "tool": "generate_image",
    "model": "mock/edit",
    "arguments": {"skill": ma.SKILL, "prompt": "lineart", "count": 1,
                  "multi_angle_stage": "preview"},
}
PLAIN_STEP = {
    "text": "海报",
    "tool": "generate_image",
    "model": "mock/edit",
    "arguments": {"prompt": "poster", "count": 1},
}


def test_default_confirm_line_stays_50_credits():
    assert DEFAULT_CONFIRM_CREDITS == 50


def test_spec_template_has_no_hardcoded_preview_size():
    """The line format reads the snapshot. It must not bake in the current default."""
    src = "\n".join((
        inspect.getsource(_stage_spec_text),
        inspect.getsource(ma.quote_stage_view),
        inspect.getsource(ma._size_view),
    ))
    for token in ("1152", "2048", "9:16"):
        assert token not in src


def test_stage_spec_text_prefers_the_snapshot_over_a_decoy_stage_spec():
    preview = _stage_spec_text({
        "stage": "preview",
        "snapshot": {
            "preview": {"width": 960, "height": 1280, "ratio": "3:4"},
            "final": {"width": 2048, "height": 2048, "ratio": "1:1"},
        },
        "stage_spec": {"width": 100, "height": 100, "ratio": "1:1"},
    }, "zh")
    final = _stage_spec_text({
        "stage": "final",
        "snapshot": {
            "preview": {"width": 960, "height": 1280, "ratio": "3:4"},
            "final": {"width": 1536, "height": 2048, "ratio": "3:4"},
        },
        "stage_spec": {"width": 100, "height": 100, "ratio": "1:1"},
        "composition_count": 2,
    }, "en")
    assert preview == "960×1280 / 3:4"
    assert final == "1536×2048 / 3:4 · 2 compositions"
    assert "1152×2048" not in preview and "9:16" not in preview
    assert "100×100" not in preview and "100×100" not in final


async def _quote(steps, *, price=0.11, threshold=0.50, lang="zh", router=None):
    seen = []

    async def pricer(_model, inputs):
        seen.append(dict(inputs))
        return price

    async def models_for(_feature):
        return [("mock/edit", price)]

    quote = await build_quote(steps, lang, threshold=threshold, pricer=pricer,
                              models_for=models_for, router=router)
    return quote, seen


def _reached(total, threshold):
    return (f"这次生成预计约 {total} 积分，达到了你设置的 {threshold} 积分确认线。确定开始吗？")


def _forced_one(total):
    return f"这次生成预计约 {total} 积分，这一步需要确认。确定开始吗？"


async def test_under_line_skill_card_does_not_claim_the_line_was_reached():
    """The screenshot case: 11 credits still asks, and does not say the 50 line was reached."""
    quote, _ = await _quote([SKILL_STEP], price=0.11, threshold=0.50)
    assert quote is not None and quote.ask is True and quote.acquired is True
    assert quote.total_credits == 11
    assert quote.prompt == _forced_one(11)
    assert "确认线" not in quote.prompt
    assert "50" not in quote.prompt
    en, _ = await _quote([SKILL_STEP], price=0.11, threshold=0.50, lang="en")
    assert en.prompt == (
        "This generation will cost about 11 credits, and this step needs confirmation. Start?"
    )
    assert "confirm limit" not in en.prompt
    assert "50" not in en.prompt


async def test_at_and_above_the_line_keeps_the_reached_sentence_with_the_real_threshold():
    at, _ = await _quote([SKILL_STEP], price=0.50, threshold=0.50)
    over, _ = await _quote([SKILL_STEP], price=0.60, threshold=0.50)
    custom, _ = await _quote([SKILL_STEP], price=0.25, threshold=0.20)
    assert at is not None and at.ask is True and at.prompt == _reached(50, 50)
    assert over is not None and over.ask is True and over.prompt == _reached(60, 50)
    assert custom is not None and custom.prompt == _reached(25, 20)
    assert "这一步需要确认" not in at.prompt
    en, _ = await _quote([SKILL_STEP], price=0.50, threshold=0.50, lang="en")
    assert en.prompt == (
        "This generation will cost about 50 credits, at or above your 50 credits confirm limit. Start?"
    )


async def test_custom_line_under_the_estimate_still_uses_the_forced_sentence():
    quote, _ = await _quote([SKILL_STEP], price=0.11, threshold=0.20)
    assert quote is not None and quote.ask is True
    assert quote.prompt == _forced_one(11)
    assert "20" not in quote.prompt and "确认线" not in quote.prompt


async def test_zero_threshold_still_uses_the_reached_sentence():
    """Settings contract: 0 means always confirm. 11 credits did meet that line."""
    quote, _ = await _quote([SKILL_STEP], price=0.11, threshold=0)
    assert quote is not None and quote.ask is True
    assert quote.prompt == _reached(11, 0)


async def test_multi_step_wording_splits_the_same_way():
    steps = [SKILL_STEP, {**PLAIN_STEP, "text": "再来一张"}]
    under, _ = await _quote(steps, price=0.04, threshold=0.50)
    over, _ = await _quote(steps, price=0.30, threshold=0.50)
    assert under is not None and under.ask is True and under.total_credits == 8
    assert under.prompt == "这个任务共 2 步，预计约 8 积分，需要确认后才能开始。确定开始吗？"
    assert "确认线" not in under.prompt
    assert over is not None and over.ask is True and over.total_credits == 60
    assert over.prompt == "这个任务共 2 步，预计约 60 积分，超过了你设置的 50 积分确认线。确定开始吗？"
    en, _ = await _quote(steps, price=0.04, threshold=0.50, lang="en")
    assert en.prompt == (
        "This task has 2 steps and will cost about 8 credits, "
        "and confirmation is required before it starts. Start?"
    )
    assert "confirm limit" not in en.prompt


def test_quote_chrome_and_cancel_suffix_follow_the_ui_language():
    """Title, buttons, and the after-cancel suffix use the active UI language.

    Chinese interface: 确认费用 / 取消 / 开始, and 已取消 after cancel.
    English interface: Confirm cost / Cancel / Start, and Canceled.
    The primary button is this card only. jobs.confirmOk stays 继续生成 / Generate.
    """
    zh = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
    assert zh["jobs.confirmTitle"] == "确认费用" and en["jobs.confirmTitle"] == "Confirm cost"
    assert zh["common.cancel"] == "取消" and en["common.cancel"] == "Cancel"
    assert zh["jobs.planQuoteStart"] == "开始" and en["jobs.planQuoteStart"] == "Start"
    assert zh["jobs.confirmOk"] == "继续生成" and en["jobs.confirmOk"] == "Generate"
    assert zh["chatMessage.canceled"] == "已取消" and en["chatMessage.canceled"] == "Canceled"
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    chrome = chat.split("function planQuoteChrome()", 1)[1].split("function PlanQuote", 1)[0]
    memo = chat.split("function PlanQuote", 1)[1].split("function Task", 1)[0]
    for key in ("jobs.confirmTitle", "jobs.planQuoteStart", "common.cancel", "chatMessage.canceled"):
        assert f"t('{key}')" in chrome
    assert "jobs.confirmOk" not in chrome
    assert "Canceled" not in chrome and "Confirm cost" not in chrome and "Generate" not in chrome
    assert "chrome.title" in memo and "chrome.ok" in memo and "chrome.cancel" in memo
    assert "chrome.canceled" in memo
    assert "ca-chat__memo-suffix" in memo
    assert '"Canceled"' not in memo and "'Canceled'" not in memo


def test_committed_dist_serves_the_quote_card_start_label():
    """The served bundle must include this card's 开始 / Start key. Source alone
    is not enough: the previous tip left dist equal to #1013."""
    js = "".join(p.read_text(errors="ignore") for p in (ROOT / "dist" / "assets").glob("*.js"))
    css = "".join(p.read_text(errors="ignore") for p in (ROOT / "dist" / "assets").glob("*.css"))
    assert "jobs.planQuoteStart" in js
    assert "jobs.confirmOk" in js
    assert "ca-chat-confirm__line" in css
    assert "ca-chat__memo-suffix" in css
    assert "word-break:keep-all" in css or "word-break: keep-all" in css


def test_quote_card_reason_is_not_a_single_line_ellipsis():
    """The trigger sentence and the quote line wrap. The shared library name
    still ellipsizes; only this card opts out. The size stays in the line text."""
    css = (ROOT / "src/styles/overlays.css").read_text(encoding="utf-8")
    assert ".ca-lib__name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }" in css
    row = css.split(".ca-chat-confirm .ca-keys__row {", 1)[1].split("}", 1)[0]
    name = css.split(".ca-chat-confirm .ca-keys__row .ca-lib__name,", 1)[1].split("}", 1)[0]
    desc = css.split(".ca-chat-confirm__desc {", 1)[1].split("}", 1)[0]
    price = css.split(".ca-chat-confirm .ca-keys__row .ca-panel__val {", 1)[1].split("}", 1)[0]
    assert "height: auto" in row
    assert ".ca-chat-confirm__line" in name
    assert "white-space: normal" in name and "text-overflow: clip" in name
    assert "ellipsis" not in name and "nowrap" not in name
    assert "white-space: pre-line" in desc and "text-overflow: clip" in desc
    assert "ellipsis" not in desc
    assert "white-space: nowrap" in price  # the credit amount itself stays intact
    suffix = css.split(".ca-chat__memo--quote .ca-chat__memo-suffix {", 1)[1].split("}", 1)[0]
    memo = css.split(".ca-chat__memo--quote {", 1)[1].split("}", 1)[0]
    assert "white-space: nowrap" in suffix and "word-break: keep-all" in suffix
    assert "break-all" not in suffix
    assert "line-height: 20px" in memo and "overflow: visible" in memo and "padding:" in memo


async def test_ordinary_calls_keep_the_threshold_and_unpriced_keeps_its_sentence():
    """Forcing stays on this skill. Other calls under the line still have no card."""
    missing = await _quote([PLAIN_STEP], price=0.11, threshold=0.50)
    assert missing[0] is None
    at, _ = await _quote([PLAIN_STEP], price=0.50, threshold=0.50)
    assert at is not None and at.ask is True and at.prompt == _reached(50, 50)

    async def unpriced(_model, _inputs):
        return None, "unpriced"

    async def models_for(_feature):
        return []

    quote = await build_quote([SKILL_STEP], "zh", threshold=0.50, pricer=unpriced,
                              models_for=models_for)
    assert quote is not None and quote.ask is False
    assert "暂未确定" in quote.prompt
    assert "确认线" not in quote.prompt and "这一步需要确认" not in quote.prompt


def _pick(*_a, **_k):
    return {"model": "mock/edit", "auto": True, "reason": {"zh": "测试路由", "en": "test route"}}


def _router(tool, args, position=0):
    return canvas.quote_route(tool, args, catalog={}, position=position)


def _bind(monkeypatch, text=DESC):
    """In-memory chat. No database and no ledger."""
    rows = [{"id": "start", "role": "user", "blocks": [
        {"type": "skill", "name": ma.SKILL},
        {"type": "text", "text": text},
        {"type": "image", "url": REF},
    ]}]

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

    monkeypatch.setattr(chat_store, "list_messages", lambda chat: copy.deepcopy(rows))
    monkeypatch.setattr(chat_store, "update_message", update)
    monkeypatch.setattr(chat_store, "compare_message_blocks", compare)
    monkeypatch.setattr(bot_turns, "ACTIVE_TURNS", {})
    return rows


def _answer_setup(rows, aspect="1:1"):
    token = BOT_CHAT_ID.set("chat-copy")
    try:
        spec = bot_asks.validate_spec({"prompt": "setup"})
    finally:
        BOT_CHAT_ID.reset(token)
    block = {"type": "ask", "ask_id": "setup", "status": "answered", **spec, "answers": {
        ma.SOURCE: {"selected": ["single_front"]},
        ma.ASPECT: {"selected": [aspect]},
    }}
    rows.append({"id": "setup-msg", "role": "assistant", "blocks": [block]})


def _deliver_preview(rows):
    token = BOT_CHAT_ID.set("chat-copy")
    try:
        args, blocked = ma.prepare({
            "composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview",
        })
        assert blocked is None, blocked
        assert ma.reserve(args["_multi_angle"]) is None
        ma.submitted(args["_multi_angle"], {"ids": ["preview-holder"], "submitted": True})
        ma.record_wait({"results": [{
            "id": "preview-holder", "status": "done", "placed": True,
            "shapes": ["preview-shape"], "urls": [preview_url()],
        }]})
    finally:
        BOT_CHAT_ID.reset(token)


def _choose(rows, ids):
    rows.append({"id": "composition-msg", "role": "assistant", "blocks": [{
        "type": "ask", "ask_id": "compositions", "status": "answered",
        "answers": {ma.COMPOSITIONS: {"selected": list(ids)}},
    }]})


def _tool(**extra):
    return {
        "skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN, "prompt": "lineart",
        "width": 100, "height": 100, "ratio": "1:1", "count": 4, **extra,
    }


async def _routed_quote(steps, *, price=0.11, threshold=0.50, lang="zh"):
    token = BOT_CHAT_ID.set("chat-copy")
    try:
        return await _quote(steps, price=price, threshold=threshold, lang=lang, router=_router)
    finally:
        BOT_CHAT_ID.reset(token)


def _step(text, tool):
    return {"text": text, "tool": "generate_image", "model": "", "arguments": tool}


@pytest.mark.parametrize("price,threshold,prompt", [
    (0.11, 0.50, _forced_one(11)),
    (0.50, 0.50, _reached(50, 50)),
])
async def test_default_preview_line_shows_the_snapshot_after_the_stage_label(
        monkeypatch, price, threshold, prompt):
    monkeypatch.setattr(canvas, "select_model", _pick)
    rows = _bind(monkeypatch)
    _answer_setup(rows, "1:1")
    token = BOT_CHAT_ID.set("chat-copy")
    try:
        prepared, blocked = ma.prepare(_tool(multi_angle_stage="final"))
        assert blocked is None and prepared["_multi_angle"]["key"] == "preview"
        snap = prepared["_multi_angle"]["setup_snapshot"]["preview"]
        assert (snap["width"], snap["height"], snap["ratio"]) == (1152, 2048, "9:16")
        routed = canvas.quote_route("generate_image", _tool(multi_angle_stage="final"), catalog={})
    finally:
        BOT_CHAT_ID.reset(token)
    assert routed and routed[0] == "mock/edit"
    assert "_multi_angle" not in routed[1]
    view = routed[1]["_quote_stage"]
    assert view["stage"] == "preview"
    assert view["snapshot"]["preview"] == {"width": snap["width"], "height": snap["height"], "ratio": snap["ratio"]}
    assert "composition_count" not in view
    quote, seen = await _routed_quote([_step("线稿", _tool(multi_angle_stage="final"))],
                                      price=price, threshold=threshold)
    assert quote is not None and quote.ask is True and quote.prompt == prompt
    text = quote.lines[0].text
    parts = text.split(" · ")
    assert parts[0] == "线稿预览"
    assert parts[1] == f"{snap['width']}×{snap['height']} / {snap['ratio']}"
    assert len(parts) > 2  # the spec is not the trailing segment the ellipsis cuts
    assert "100×100" not in text
    assert all("_quote_stage" not in item and "snapshot" not in item for item in seen)


async def test_explicit_preview_snapshot_replaces_the_default_size(monkeypatch):
    monkeypatch.setattr(canvas, "select_model", _pick)
    # Exact user pixels have no schema in this empty catalog. The capability
    # guard is not this test; the line still has to read the snapshot prepare() built.
    monkeypatch.setattr(ma, "validate_provider_size", lambda *a, **k: None)
    rows = _bind(monkeypatch, DESC + "\npreview 960x1280")
    _answer_setup(rows, "1:1")
    token = BOT_CHAT_ID.set("chat-copy")
    try:
        prepared, blocked = ma.prepare(_tool())
        assert blocked is None
        snap = prepared["_multi_angle"]["setup_snapshot"]["preview"]
        assert (snap["width"], snap["height"], snap["ratio"]) == (960, 1280, "3:4")
        assert prepared["_multi_angle"]["setup_snapshot"]["final"]["ratio"] == "1:1"
    finally:
        BOT_CHAT_ID.reset(token)
    quote, _seen = await _routed_quote([_step("线稿", _tool())])
    text = quote.lines[0].text
    parts = text.split(" · ")
    assert parts[0] == "线稿预览"
    assert parts[1] == "960×1280 / 3:4"
    assert "1152×2048" not in text and "9:16" not in text
    en, _ = await _routed_quote([_step("lineart", _tool())], lang="en")
    en_parts = en.lines[0].text.split(" · ")
    assert en_parts[0] == "Lineart preview"
    assert en_parts[1] == "960×1280 / 3:4"


@pytest.mark.parametrize("aspect,size,ids", [
    ("1:1", (2048, 2048, "1:1"), ("1",)),
    ("3:4", (1536, 2048, "3:4"), ("2", "3")),
    ("16:9", (2048, 1152, "16:9"), ("1", "5", "9")),
])
async def test_final_line_uses_the_chosen_aspect_and_composition_count(monkeypatch, aspect, size, ids):
    monkeypatch.setattr(canvas, "select_model", _pick)
    rows = _bind(monkeypatch)
    _answer_setup(rows, aspect)
    _deliver_preview(rows)
    _choose(rows, ids)
    steps = [_step("成品", _tool(multi_angle_stage="final", composition_id=panel)) for panel in ids]
    token = BOT_CHAT_ID.set("chat-copy")
    try:
        prepared, blocked = ma.prepare(steps[0]["arguments"])
        assert blocked is None and prepared["_multi_angle"]["key"].startswith("final:")
        snap = prepared["_multi_angle"]["setup_snapshot"]["final"]
        assert (snap["width"], snap["height"], snap["ratio"]) == size
        assert len(ma.selection("chat-copy")) == len(ids)
    finally:
        BOT_CHAT_ID.reset(token)
    quote, seen = await _routed_quote(steps, price=0.11, threshold=0.50)
    assert quote is not None and quote.ask is True and len(quote.lines) == len(ids)
    credits = 11 * len(ids)
    if len(ids) == 1:
        assert quote.prompt == _forced_one(credits)
    else:
        assert quote.prompt == (
            f"这个任务共 {len(ids)} 步，预计约 {credits} 积分，需要确认后才能开始。确定开始吗？"
        )
    spec = f"{snap['width']}×{snap['height']} / {snap['ratio']} · {len(ids)} 个构图"
    for line in quote.lines:
        assert line.text.startswith(spec + " · ")
        assert "线稿预览" not in line.text
        assert "1152×2048" not in line.text and "9:16" not in line.text
        assert "100×100" not in line.text
    assert all("_quote_stage" not in item for item in seen)
    en, _ = await _routed_quote(steps, lang="en")
    word = "composition" if len(ids) == 1 else "compositions"
    en_spec = f"{snap['width']}×{snap['height']} / {snap['ratio']} · {len(ids)} {word}"
    assert en.lines[0].text.startswith(en_spec + " · ")
