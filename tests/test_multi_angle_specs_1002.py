"""#1002 product HOLD fixes: user specifications, not model guesses, own pixels.

Only mocked schemas, local persistence and canvas boundary calls. No network.
"""
from __future__ import annotations

import copy

import pytest

from ComfyArt.api import multi_angle as ma, wavespeed
from ComfyArt.api.mcp_tools import canvas
from test_multi_angle_stages_911 import run, setup, choose  # noqa: F401


def add_text(rows, text):
    rows[0]["blocks"].append({"type": "text", "text": text})


def complete_preview(args):
    meta = args["_multi_angle"]
    ma.reserve(meta)
    ma.submitted(meta, {"ids": ["preview-holder"], "submitted": True})
    ma.record_wait({"results": [{"id": "preview-holder", "status": "done", "placed": True,
                                 "delivered": 1, "shapes": ["preview-shape"]}]})


def metadata(properties):
    return {"api_schema": {"api_schemas": [{"request_schema": {"properties": properties}}]}}


@pytest.mark.parametrize("text", ["商品图 1200×960 px", "PDP width=1200 height=960", "成品 宽1200 高960 像素"])
def test_explicit_description_pixels_override_model_guesses_and_survive_resume(run, text):
    rows, _ = run
    add_text(rows, text)
    setup(rows, "5:4")
    args, blocked = ma.prepare({"skill": ma.SKILL, "width": 1024, "height": 1024, "ratio": "1:1"})
    assert blocked is None
    assert (args["width"], args["height"], args["ratio"]) == (1200, 960, "5:4")
    assert args["_multi_angle"]["stage_spec"]["exact_pixels"] is True
    complete_preview(args)
    choose(rows, ("2",))
    final, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "2", "width": 4096, "height": 4096})
    assert blocked is None and (final["width"], final["height"]) == (1200, 960)
    assert "Final specification: 1200x960" in final["prompt"]
    assert ma._root("chat-ma")[1][ma.LEDGER]["setup_snapshot"]["final"]["width"] == 1200


@pytest.mark.parametrize("other,expected", [("5:4", (2048, 1638, "5:4", False)),
                                           ("custom aspect 7:5", (2048, 1463, "7:5", False)),
                                           ("1250x1000 pixels", (1250, 1000, "5:4", True))])
def test_existing_aspect_other_field_accepts_custom_ratio_or_exact_pixels(run, other, expected):
    rows, _ = run
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": other}
    args, blocked = ma.prepare({"skill": ma.SKILL})
    assert blocked is None
    assert (args["width"], args["height"], args["ratio"], args["_multi_angle"]["stage_spec"]["exact_pixels"]) == expected
    assert args["_strict_user_ratio_994"] == expected[2]


@pytest.mark.parametrize("text", ["全景补充参考图，沿用原主体", "Other source: CAD reference supplied"])
def test_source_other_text_is_kept_in_prompt_state_and_not_replaced_by_model(run, text):
    rows, _ = run
    root = setup(rows)
    assert all(q["allow_other"] for q in root["questions"])
    root["answers"][ma.SOURCE] = {"selected": [], "other_text": text}
    args, blocked = ma.prepare({"skill": ma.SKILL, "prompt": "model invented source"})
    assert blocked is None and text in args["prompt"]
    assert "model invented source" not in args["prompt"]
    complete_preview(args)
    snap = ma._root("chat-ma")[1][ma.LEDGER]["setup_snapshot"]
    assert snap["source"]["other_text"] == text
    root = rows[1]["blocks"][0]
    root["answers"][ma.SOURCE]["other_text"] = "changed source"
    _, blocked = ma.prepare({"skill": ma.SKILL})
    assert blocked is not None and "changed after submission" in blocked["error"]


@pytest.mark.parametrize("text,aspect", [("1200x900", "1:1"), ("5:4", "3:4"),
                                        ("1200x900 and 800x800", "4:3"),
                                        ("0x900", "1:1"), ("-1200x900", "4:3"),
                                        ("1200.5x900", "4:3"), ("40000x30000", "4:3"), ("0:1", "1:1")])
@pytest.mark.asyncio
async def test_conflicting_or_invalid_user_specs_block_before_submit(run, text, aspect):
    rows, sent = run
    add_text(rows, text)
    setup(rows, aspect)
    result = await canvas._relay("generate_image")({"skill": ma.SKILL})
    assert result["submitted"] is False and result["error"]
    assert sent == []


def test_user_preview_layout_is_independent_but_model_layout_guess_is_not(run):
    rows, _ = run
    add_text(rows, "final 1200x900; preview 800x800")
    setup(rows, "4:3")
    args, blocked = ma.prepare({"skill": ma.SKILL, "ratio": "9:16", "width": 1152, "height": 2048})
    assert blocked is None and (args["width"], args["height"], args["ratio"]) == (800, 800, "1:1")
    complete_preview(args)
    choose(rows, ("3",))
    final, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "3"})
    assert blocked is None and (final["width"], final["height"], final["ratio"]) == (1200, 900, "4:3")


def test_normal_default_has_named_strategy_and_does_not_trust_model_pixels(run):
    rows, _ = run
    setup(rows, "1:1")
    args, blocked = ma.prepare({"skill": ma.SKILL, "width": 333, "height": 999, "ratio": "9:16"})
    assert blocked is None and (args["width"], args["height"], args["ratio"]) == (2048, 2048, "1:1")
    spec = args["_multi_angle"]["stage_spec"]
    assert not spec["exact_pixels"] and spec["default_policy"] == ma.DEFAULT_SIZE_POLICY


@pytest.mark.parametrize("props", [
    {"size": {"type": "string", "minimum": 256, "maximum": 1024}},
    {"size": {"type": "string", "enum": ["1024*1024"]}},
    {"size": {"type": "string", "multipleOf": 64}},
    {"aspect_ratio": {"enum": ["4:3", "1:1"]}, "resolution": {"enum": ["1k", "2k"]}},
])
@pytest.mark.asyncio
async def test_detectably_unsupported_exact_pixels_refused_without_model_fallback(run, monkeypatch, props):
    rows, sent = run
    add_text(rows, "1200x900")
    setup(rows, "4:3")
    monkeypatch.setattr(wavespeed, "cached_models", lambda: {"mock-pixels": metadata(props)})
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "mock-pixels", "auto": False, "category": "user", "reason": {"zh": "指定模型", "en": "Named model"}})
    result = await canvas._relay("generate_image")({"skill": ma.SKILL, "model": "mock-pixels"})
    assert result["submitted"] is False and sent == []


@pytest.mark.parametrize("auto", [False, True])
@pytest.mark.asyncio
async def test_exact_handler_and_quote_keep_user_pixels_and_pin_verified_model(run, monkeypatch, auto):
    rows, sent = run
    add_text(rows, "1200x900")
    setup(rows, "4:3")
    catalog = {"mock-pixels": metadata({"size": {"type": "string", "minimum": 64, "maximum": 4096}})}
    monkeypatch.setattr(wavespeed, "cached_models", lambda: catalog)
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "mock-pixels", "auto": auto, "category": "user", "reason": {"zh": "指定模型", "en": "Named model"}})
    model, inputs = canvas.quote_route("generate_image", {"skill": ma.SKILL, "model": "mock-pixels"}, catalog=catalog)
    assert model == "mock-pixels" and (inputs["width"], inputs["height"]) == (1200, 900)
    result = await canvas._relay("generate_image")({"skill": ma.SKILL, "model": "mock-pixels", "width": 2048, "height": 2048})
    assert result["ids"] and len(sent) == 1
    actual = sent[0][1]
    assert (actual["width"], actual["height"], actual["ratio"]) == (1200, 900, "4:3")
    assert actual["model"] == "mock-pixels" and actual["size_candidates"] == ["mock-pixels"]
    assert actual["auto_model"] is False and actual["size_lock"] is True


def test_provider_unknown_or_unsupported_custom_ratio_reports_actionable_limit(run):
    rows, _ = run
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "1200x900"}
    args, _ = ma.prepare({"skill": ma.SKILL})
    blocked = ma.validate_provider_size(args, args["_multi_angle"], "unknown", {})
    assert blocked["submitted"] is False and "catalogue" in blocked["error"]
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "5:4"}
    args, _ = ma.prepare({"skill": ma.SKILL})
    blocked = ma.validate_provider_size(args, args["_multi_angle"], "limited", {"limited": metadata({"aspect_ratio": {"enum": ["1:1"]}})})
    assert blocked["submitted"] is False and "unsupported" in blocked["error"]


def test_pixels_or_preview_edits_after_dispatch_fail_before_cached_replay(run):
    rows, _ = run
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "1200x1200"}
    args, _ = ma.prepare({"skill": ma.SKILL})
    complete_preview(args)
    original = copy.deepcopy(rows)
    root = rows[1]["blocks"][0]
    root["answers"][ma.ASPECT]["other_text"] = "1000x1000"
    _, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]
    rows[:] = original
    add_text(rows, "preview 800x800")
    _, blocked = ma.prepare({"skill": ma.SKILL})
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]


def test_default_size_also_respects_detectable_provider_bounds(run):
    rows, _ = run
    setup(rows)
    args, _ = ma.prepare({"skill": ma.SKILL})
    blocked = ma.validate_provider_size(args, args["_multi_angle"], "small-only", {
        "small-only": metadata({"size": {"type": "string", "maximum": 1024}})})
    assert blocked["submitted"] is False and "range/step" in blocked["error"]


def test_fresh_explicit_skill_start_does_not_inherit_old_user_dimensions(run):
    rows, _ = run
    add_text(rows, "1200x900")
    setup(rows, "4:3")
    args, _ = ma.prepare({"skill": ma.SKILL})
    complete_preview(args)
    rows.append({"id": "new-start", "role": "user", "blocks": [
        {"type": "skill", "name": ma.SKILL},
        {"type": "text", "text": "新的商品图 1400x1000"},
        {"type": "image", "url": "new-reference"}]})
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "7:5"}
    rows[-1]["id"] = "new-setup"
    args, blocked = ma.prepare({"skill": ma.SKILL})
    assert blocked is None and args["_multi_angle"]["key"] == "preview"
    assert (args["width"], args["height"]) == (1400, 1000)
    assert "1200x900" not in args["prompt"] and args["refs"] == ["new-reference"]


@pytest.mark.asyncio
async def test_model_routing_cannot_rewrite_explicit_dimensions(run, monkeypatch):
    rows, sent = run
    add_text(rows, "1200x900")
    setup(rows, "4:3")

    def rewritten(action, args, **kwargs):
        return {"model": "mock-pixels", "auto": False, "category": "user",
                "_exact_args": {**args, "width": 2048, "height": 1536}}

    monkeypatch.setattr(canvas, "select_model", rewritten)
    result = await canvas._relay("generate_image")({"skill": ma.SKILL})
    assert result["submitted"] is False and "Routing changed" in result["error"]
    assert sent == [] and ma.LEDGER not in ma._root("chat-ma")[1]
