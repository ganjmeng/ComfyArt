"""Lovart setup card: both questions always, custom aspect, no second upload ask."""
from __future__ import annotations

import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN
from test_multi_angle_stages_911 import run, setup  # noqa: F401

from ComfyArt.api import bot_asks, multi_angle as ma


def test_attached_refs_still_ask_both_questions_with_exact_copy(run, monkeypatch):
    rows, _ = run
    assert any(b.get("type") == "image" for b in rows[0]["blocks"])
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    card = bot_asks.validate_spec({"prompt": "setup"})
    assert [q["id"] for q in card["questions"]] == [ma.SOURCE, ma.ASPECT]
    source, aspect = card["questions"]
    assert source["prompt"] == "产品参考图怎么提供？"
    assert [o["label"] for o in source["options"]] == [
        "上传多角度产品图", "只上传 1 张正面主图", "暂无实拍图，先做产品示意"]
    assert source["allow_other"] is True and source["placeholder"] == "其他情况（直接说明）..."
    assert aspect["prompt"] == "详情页主画幅用哪个？"
    assert [o["label"] for o in aspect["options"]] == ["1:1 方图（推荐）", "3:4 竖图", "4:3 横图"]
    assert aspect["allow_other"] is True and aspect["placeholder"] == "自定义比例或像素尺寸..."
    assert all(q.get("defaults") in (None, []) for q in card["questions"])


@pytest.mark.parametrize("text,ratio,size", [
    ("16:9", "16:9", (2048, 1152)),
    ("1200x1600", "3:4", (1536, 2048)),
])
def test_custom_aspect_parses_to_a_supported_ratio(run, text, ratio, size):
    rows, _ = run
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": text}
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None
    final = args["_multi_angle"]["setup_snapshot"]["final"]
    assert final["ratio"] == ratio and final["exact_pixels"] is False
    assert (final["width"], final["height"]) == size
    assert (args["width"], args["height"], args["ratio"]) == (1152, 2048, "9:16")


def test_invalid_custom_aspect_asks_once_and_does_not_generate(run, monkeypatch):
    rows, _ = run
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "hello"}
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is not None and blocked["submitted"] is False
    assert "不要出图" in blocked["error"]
    card = bot_asks.validate_spec({"prompt": "clarify the aspect"})
    assert [q["id"] for q in card["questions"]] == [ma.ASPECT]
    assert card["questions"][0]["prompt"] == ma.ASPECT_CLARIFY_ZH
    rows.append({"id": "clarify", "role": "assistant", "blocks": [
        {"type": "ask", "ask_id": "clarify", "status": "pending", **card}]})
    with pytest.raises(ValueError, match="already clarified"):
        bot_asks.validate_spec({"prompt": "clarify again"})


def test_upload_reask_after_setup_is_rejected_and_refs_still_used(run):
    rows, _ = run
    root = setup(rows, "1:1", source="no_photo")
    with pytest.raises(ValueError, match="不要再要求上传"):
        bot_asks.validate_spec({"prompt": "请再上传一张参考图", "questions": [
            {"id": ma.SOURCE, "prompt": "产品参考图怎么提供？", "options": [
                {"id": "multiple", "label": "上传多角度产品图"},
                {"id": "single_front", "label": "只上传 1 张正面主图"}], "allow_other": True}]})
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None
    assert args["refs"]
    assert args["_multi_angle"]["source"] == "no_photo"
    rows[0]["blocks"] = [b for b in rows[0]["blocks"] if b.get("type") != "image"]
    root["answers"][ma.SOURCE]["selected"] = ["single_front"]
    bare, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None and bare["refs"] == []


def test_composition_labels_use_the_fullwidth_bar(run, monkeypatch):
    rows, _ = run
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    from test_multi_angle_stages_911 import preview
    preview(rows)
    card = bot_asks.validate_spec({"prompt": "choose"})
    question = card["questions"][0]
    assert question["prompt"] == "选择想生成的构图（可多选，按图中编号）"
    assert question["allow_other"] is True and question["placeholder"] == "输入编号"
    assert question.get("defaults") in (None, [])
    assert question["options"][0]["label"] == "1｜正面全景"
    assert all("｜" in option["label"] for option in question["options"])
