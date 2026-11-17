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
    assert (args["width"], args["height"]) == (1152, 2048)
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
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked is None and args["_multi_angle"]["key"] == "preview"
    assert (args["width"], args["height"], args["ratio"]) == (1152, 2048, "9:16")


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
    """#1003: allow_other=false (aspect) does not render D 其他（输入你的答案）."""
    src = (ROOT / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    block = src.split("function QuestionBlock")[1].split("/** #328/#330")[0]
    assert "showOtherRow = allowOther" in block
    assert "{showOtherRow && (" in block
    assert 'data-other=""' in block


@pytest.mark.parametrize("aspect,expected", [
    ("1:1", (1152, 2048, "9:16")),
    ("3:4", (1152, 2048, "9:16")),
    ("4:3", (1152, 2048, "9:16")),
    ("16:9", (1152, 2048, "9:16")),
    ("9:16", (1152, 2048, "9:16")),
])
def test_prepare_rewrites_first_generate_to_independent_preview(run, aspect, expected):
    rows, _ = run
    setup(rows, aspect)
    # Agent ratio/size is a guess and must not win over the independent preview default.
    args, blocked = ma.prepare({
        "composition_plan": HEADPHONES_PLAN, "prompt": "generic product images",
        "multi_angle_stage": "final", "composition_id": "1",
        "ratio": "1:1", "width": 1024, "height": 1024,
    })
    assert blocked is None
    assert args["skill"] == ma.SKILL
    assert args["multi_angle_stage"] == "preview"
    assert args["_multi_angle"]["key"] == "preview"
    assert (args["width"], args["height"], args["ratio"]) == expected


def test_unskilled_and_final_generates_blocked_or_rewritten_until_preview_and_composition(run):
    rows, _ = run
    setup(rows, "3:4")
    rewritten, blocked = ma.prepare({"prompt": "生成图像", "refs": [REF]})
    assert blocked is not None and blocked["submitted"] is False
    assert "composition_plan" in blocked["error"]
    rewritten, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "prompt": "生成图像"})
    assert blocked is None and rewritten["_multi_angle"]["key"] == "preview"
    assert (rewritten["width"], rewritten["height"], rewritten["ratio"]) == (1152, 2048, "9:16")
    meta = rewritten["_multi_angle"]
    assert ma.reserve(meta) is None
    ma.submitted(meta, {"ids": ["preview-holder"], "submitted": True})
    ma.record_wait({"results": [{"id": "preview-holder", "status": "done", "placed": True,
                                 "shapes": ["preview-shape"]}]})
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                             "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked is not None and blocked["submitted"] is False
    choose(rows, ("1",))
    final, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                 "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked is None and final["_multi_angle"]["key"] == "final:1"
    assert (final["width"], final["height"], final["ratio"]) == (1536, 2048, "3:4")


def test_missing_composition_plan_is_fail_closed_not_auto_priced(run, monkeypatch):
    rows, _ = run
    setup(rows, "3:4")
    banana = {"model": "google/nano-banana-pro/edit", "auto": True, "category": "image_edit",
              "reason": {"zh": "自动", "en": "Auto"}}
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: banana)
    model, payload = canvas.quote_route("generate_image", {
        "skill": ma.SKILL, "multi_angle_stage": "preview", "ratio": "3:4", "prompt": "numbered lineart",
    }, catalog={})
    assert model == ""
    blocked = payload["param_blocked"]
    assert blocked["submitted"] is False and blocked["kind"] == "multiAngleStage"
    assert "composition_plan" in blocked["error"]
    assert "nano-banana" not in str(payload).lower()


@pytest.mark.parametrize("status", [None, "pending", "expired", "cancelled"])
def test_unanswered_or_expired_setup_cannot_be_priced(run, monkeypatch, status):
    rows, _ = run
    if status:
        setup(rows, "3:4", status=status)
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {
        "model": "google/nano-banana-pro/edit", "auto": True, "category": "image_edit"})
    model, payload = canvas.quote_route("generate_image", {
        "composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview",
    }, catalog={})
    assert model == ""
    blocked = payload["param_blocked"]
    assert blocked["submitted"] is False and blocked["kind"] == "multiAngleStage"
    assert "nano-banana" not in str(payload).lower()


@pytest.mark.asyncio
async def test_quote_line_leads_with_lineart_preview_label(run, monkeypatch):
    from ComfyArt.bot.local_llm import _step_label
    rows, _ = run
    setup(rows, "3:4")
    args = {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"}
    assert _step_label("generate_image", args, "zh") == "线稿预览"
    assert _step_label("generate_image", args, "en") == "Lineart preview"
    # A generic generate in this skill chat is still labelled as the forced preview.
    assert _step_label("generate_image", {"prompt": "生成图像"}, "zh") == "线稿预览"
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "mock", "auto": True})

    async def pricer(name, inputs):
        return 0.1035

    async def models_for(feature):
        return [("mock", 0.1035)]

    def router(tool, arguments, position=0):
        return canvas.quote_route(tool, arguments, catalog={}, position=position)

    quote = await build_quote(
        [{"text": "生成图像", "tool": "generate_image", "model": "mock",
          "arguments": args}],
        "zh", threshold=0, pricer=pricer, models_for=models_for, router=router,
    )
    assert quote is not None and quote.lines
    assert quote.lines[0].text.startswith("线稿预览")
    assert not quote.lines[0].text.startswith("生成图像")
