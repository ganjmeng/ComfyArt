"""#1003: quote confirm, preview-first, one-card Lovart zh copy, attached-ref source skip.

No paid WaveSpeed/DeepSeek calls and no live preview instance.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from multi_angle_plan_fixture import HEADPHONES_PLAN

from ComfyArt.api import bot_asks, multi_angle as ma
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.plan_quote import build_quote
from test_multi_angle_stages_911 import run, setup, choose, confirm_quote, REF  # noqa: F401


ZH_SOURCE = "产品参考图怎么提供？"
ZH_SOURCE_OPTS = ["上传多角度产品图", "只上传 1 张正面主图", "暂无实拍图，先做产品示意"]
ZH_ASPECT = "详情页主画幅用哪个？"
ZH_ASPECT_OPTS = ["1:1 方图（推荐）", "3:4 竖图", "4:3 横图"]


def _drop_images(rows):
    rows[0]["blocks"] = [b for b in rows[0]["blocks"] if b.get("type") != "image"]


def test_setup_card_is_one_page_two_questions_with_skip_and_lovart_zh_copy(run, monkeypatch):
    rows, _ = run
    _drop_images(rows)
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    card = bot_asks.validate_spec({"prompt": "setup"})
    assert card["page_count"] == 1 and card["allow_skip"] is True
    assert [q["id"] for q in card["questions"]] == [ma.SOURCE, ma.ASPECT]
    assert all(q["page"] == 1 and not q.get("defaults") for q in card["questions"])
    source, aspect = card["questions"]
    assert source["prompt"] == ZH_SOURCE
    assert [o["id"] for o in source["options"]] == ["multiple", "single_front", "no_photo"]
    assert [o["label"] for o in source["options"]] == ZH_SOURCE_OPTS
    assert source["allow_other"] is True
    assert source["placeholder"] == "直接说明"
    assert "/" not in source["placeholder"]
    assert aspect["prompt"] == ZH_ASPECT
    assert [o["id"] for o in aspect["options"]] == list(ma.CARD_ASPECTS)
    assert [o["label"] for o in aspect["options"]] == ZH_ASPECT_OPTS
    assert aspect["allow_other"] is False
    assert "1:1（推荐）" not in aspect["prompt"]
    assert all(o["id"] not in {"16:9", "9:16", "4:5", "5:4", "3:2", "2:3"} for o in aspect["options"])


def test_setup_card_english_is_faithful_not_claimed_official_lovart(run, monkeypatch):
    rows, _ = run
    _drop_images(rows)
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "en")
    card = bot_asks.validate_spec({"prompt": "setup"})
    source, aspect = card["questions"]
    assert source["prompt"] == "How should product reference images be provided?"
    assert [o["label"] for o in source["options"]] == [
        "Upload multi-angle product photos",
        "Upload only 1 front hero image",
        "No real product photos yet, start with a product concept",
    ]
    assert source["placeholder"] == "Describe the other situation"
    assert aspect["prompt"] == "Which aspect should the detail-page hero use?"
    assert [o["label"] for o in aspect["options"]] == [
        "1:1 square (recommended)",
        "3:4 portrait",
        "4:3 landscape",
    ]


def test_attached_reference_skips_source_question_and_infers_single_front(run, monkeypatch):
    rows, _ = run
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    card = bot_asks.validate_spec({"prompt": "setup"})
    assert [q["id"] for q in card["questions"]] == [ma.ASPECT]
    assert card["questions"][0]["prompt"] == ZH_ASPECT
    setup(rows, "3:4")
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                "multi_angle_stage": "preview"})
    assert blocked is None
    assert args["_multi_angle"]["source"] == "single_front"
    assert args["refs"] == [REF]
    assert args["ratio"] == "9:16"
    assert args["_multi_angle"]["setup_snapshot"]["final"]["ratio"] == "3:4"


def test_multiple_attached_references_infer_multi_angle_source(run, monkeypatch):
    rows, _ = run
    rows[0]["blocks"].append({"type": "image", "url": REF + "-side"})
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    card = bot_asks.validate_spec({"prompt": "setup"})
    assert [q["id"] for q in card["questions"]] == [ma.ASPECT]
    card = bot_asks.validate_spec({"prompt": "setup"})
    rows.append({"id": "setup-msg", "role": "assistant", "blocks": [{
        "type": "ask", "ask_id": "setup", "status": "answered", **card,
        "answers": {ma.ASPECT: {"selected": ["4:3"]}}}]})
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                "multi_angle_stage": "preview"})
    assert blocked is None
    assert args["_multi_angle"]["source"] == "multiple"
    assert args["refs"] == [REF, REF + "-side"]


def test_legacy_description_source_and_new_no_photo_source_do_not_require_refs(run):
    rows, _ = run
    _drop_images(rows)
    for source in ("description", "no_photo"):
        rows[:] = [rows[0]]
        root = setup(rows, "1:1", source=source)
        root["answers"][ma.SOURCE]["selected"] = [source]
        args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                    "multi_angle_stage": "preview"})
        assert blocked is None, (source, blocked)
        assert args["refs"] == []
        assert args["_multi_angle"]["source"] == source


def test_preview_is_independent_of_final_aspect_and_agent_ratio(run):
    rows, _ = run
    setup(rows, "3:4")
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                "multi_angle_stage": "preview", "ratio": "1:1"})
    assert blocked is None
    assert (args["width"], args["height"], args["ratio"]) == (1152, 2048, "9:16")
    assert "ONE lineart preview" in args["prompt"] and "3x3 nine-panel" in args["prompt"]


@pytest.mark.asyncio
async def test_generate_image_relay_is_blocked_without_confirmed_quote(run):
    rows, sent = run
    setup(rows, "3:4")
    result = await canvas._relay("generate_image")({
        "composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
        "multi_angle_stage": "preview", "ratio": "1:1",
    })
    assert result["submitted"] is False and result["kind"] == "multiAngleStage"
    assert "quote" in result["error"].lower() or "报价" in result["error"]
    assert sent == []
    confirm_quote(rows)
    allowed = await canvas._relay("generate_image")({
        "composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
        "multi_angle_stage": "preview", "ratio": "1:1",
    })
    assert allowed.get("submitted") is True and sent
    assert (sent[0][1]["width"], sent[0][1]["height"], sent[0][1]["ratio"]) == (1152, 2048, "9:16")


@pytest.mark.asyncio
async def test_quote_route_does_not_require_confirmation(run, monkeypatch):
    rows, sent = run
    setup(rows, "3:4")
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "mock", "auto": True})
    model, inputs = canvas.quote_route(
        "generate_image",
        {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"},
        catalog={},
    )
    assert model == "mock" and (inputs["width"], inputs["height"], inputs["ratio"]) == (1152, 2048, "9:16")
    assert sent == []
    assert ma.LEDGER not in (ma._root("chat-ma")[1] or {})


def test_finals_and_composition_card_still_wait_for_preview(run):
    rows, _ = run
    setup(rows, "3:4")
    confirm_quote(rows)
    with pytest.raises(ValueError, match="preview"):
        bot_asks.validate_spec({"prompt": "choose early"})
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                             "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked is not None and blocked["submitted"] is False


@pytest.mark.asyncio
async def test_build_quote_always_asks_for_this_skill_even_under_threshold():
    async def pricer(name, args):
        return 0.1035

    async def models_for(feature):
        return [("mock/edit", 0.1035)]

    steps = [{"text": "preview", "tool": "generate_image", "model": "mock/edit",
              "arguments": {"skill": ma.SKILL, "multi_angle_stage": "preview", "prompt": "lineart"}}]
    quote = await build_quote(steps, "zh", threshold=1.0, pricer=pricer, models_for=models_for)
    assert quote is not None and quote.ask is True

    other = [{"text": "logo", "tool": "generate_image", "model": "mock/edit",
              "arguments": {"skill": "logo-design", "prompt": "logo"}}]
    passthrough = await build_quote(other, "zh", threshold=1.0, pricer=pricer, models_for=models_for)
    assert passthrough is None


def test_aspect_card_omits_generic_other_row():
    """#1003: aspect has no D 其他（输入你的答案）; #763 still shows Other on other choice cards."""
    src = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    block = src.split("function QuestionBlock")[1].split("/** #328/#330")[0]
    assert "showOtherRow = q.id !== 'ma_aspect'" in block
    assert "{allowOther && (" not in block
    assert 'data-other=""' in block and "disabled={!allowOther}" in block

