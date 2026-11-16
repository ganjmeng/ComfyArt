"""#1002 product HOLD fixes: user specifications, not model guesses, own pixels.

Only mocked schemas, local persistence and canvas boundary calls. No network.
"""
from __future__ import annotations

import copy

import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN

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
    add_text(rows, text + "\n预览 1200x960")
    setup(rows, "5:4")
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "width": 1024, "height": 1024, "ratio": "1:1"})
    assert blocked is None
    assert (args["width"], args["height"], args["ratio"]) == (1200, 960, "5:4")
    assert args["_multi_angle"]["stage_spec"]["exact_pixels"] is True
    complete_preview(args)
    choose(rows, ("2",))
    final, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "2", "width": 4096, "height": 4096})
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
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None
    final_spec = args["_multi_angle"]["setup_snapshot"]["final"]
    assert (final_spec["width"], final_spec["height"], final_spec["ratio"], final_spec["exact_pixels"]) == expected
    complete_preview(args)
    choose(rows, ("1",))
    final, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "composition_id": "1"})
    assert blocked is None
    assert (final["width"], final["height"], final["ratio"]) == expected[:3]
    assert final["_strict_user_ratio_994"] == expected[2]


@pytest.mark.parametrize("text", ["全景补充参考图，沿用原主体", "Other source: CAD reference supplied"])
def test_source_other_text_is_kept_in_prompt_state_and_not_replaced_by_model(run, text):
    rows, _ = run
    root = setup(rows)
    assert all(q["allow_other"] for q in root["questions"])
    root["answers"][ma.SOURCE] = {"selected": [], "other_text": text}
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "prompt": "model invented source"})
    assert blocked is None and text in args["prompt"]
    assert "model invented source" not in args["prompt"]
    complete_preview(args)
    snap = ma._root("chat-ma")[1][ma.LEDGER]["setup_snapshot"]
    assert snap["source"]["other_text"] == text
    root = rows[1]["blocks"][0]
    root["answers"][ma.SOURCE]["other_text"] = "changed source"
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
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
    result = await canvas._relay("generate_image")({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert result["submitted"] is False and result["error"]
    assert sent == []


def test_explicit_user_preview_layout_overrides_model_choice(run):
    rows, _ = run
    add_text(rows, "final 1200x900; preview 800x800")
    setup(rows, "4:3")
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "9:16", "width": 1152, "height": 2048})
    assert blocked is None and (args["width"], args["height"], args["ratio"]) == (800, 800, "1:1")
    complete_preview(args)
    choose(rows, ("3",))
    final, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "3"})
    assert blocked is None and (final["width"], final["height"], final["ratio"]) == (1200, 900, "4:3")


def test_model_preview_layout_is_allowed_but_model_pixels_do_not_control_final(run):
    rows, _ = run
    setup(rows, "1:1")
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "width": 333, "height": 999, "ratio": "9:16"})
    assert blocked is None and (args["width"], args["height"], args["ratio"]) == (1152, 2048, "9:16")
    spec = args["_multi_angle"]["stage_spec"]
    assert not spec["exact_pixels"] and spec["default_policy"] == ma.DEFAULT_SIZE_POLICY
    complete_preview(args)
    choose(rows, ("1",))
    final, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "composition_id": "1", "ratio": "9:16", "width": 333, "height": 999})
    assert blocked is None and (final["width"], final["height"], final["ratio"]) == (2048, 2048, "1:1")


@pytest.mark.parametrize("props", [
    {"size": {"type": "string", "minimum": 256, "maximum": 1024}},
    {"size": {"type": "string", "enum": ["1024*1024"]}},
    {"size": {"type": "string", "multipleOf": 64}},
    {"aspect_ratio": {"enum": ["4:3", "1:1"]}, "resolution": {"enum": ["1k", "2k"]}},
])
@pytest.mark.asyncio
async def test_detectably_unsupported_exact_pixels_refused_without_model_fallback(run, monkeypatch, props):
    rows, sent = run
    add_text(rows, "1200x900; preview 1200x900")
    setup(rows, "4:3")
    monkeypatch.setattr(wavespeed, "cached_models", lambda: {"mock-pixels": metadata(props)})
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "mock-pixels", "auto": False, "category": "user", "reason": {"zh": "指定模型", "en": "Named model"}})
    result = await canvas._relay("generate_image")({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "model": "mock-pixels"})
    assert result["submitted"] is False and sent == []


@pytest.mark.parametrize("auto", [False, True])
@pytest.mark.asyncio
async def test_exact_handler_and_quote_keep_user_pixels_and_pin_verified_model(run, monkeypatch, auto):
    rows, sent = run
    add_text(rows, "1200x900; preview 1200x900")
    setup(rows, "4:3")
    catalog = {"mock-pixels": metadata({"size": {"type": "string", "minimum": 64, "maximum": 4096}})}
    monkeypatch.setattr(wavespeed, "cached_models", lambda: catalog)
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "mock-pixels", "auto": auto, "category": "user", "reason": {"zh": "指定模型", "en": "Named model"}})
    model, inputs = canvas.quote_route("generate_image", {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "model": "mock-pixels"}, catalog=catalog)
    assert model == "mock-pixels" and (inputs["width"], inputs["height"]) == (1200, 900)
    result = await canvas._relay("generate_image")({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "model": "mock-pixels", "width": 2048, "height": 2048})
    assert result["ids"] and len(sent) == 1
    actual = sent[0][1]
    assert (actual["width"], actual["height"], actual["ratio"]) == (1200, 900, "4:3")
    assert actual["model"] == "mock-pixels" and actual["size_candidates"] == ["mock-pixels"]
    assert actual["auto_model"] is False and actual["size_lock"] is True


def test_provider_unknown_or_unsupported_custom_ratio_reports_actionable_limit(run):
    rows, _ = run
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "1200x900"}
    add_text(rows, "preview 1200x900")
    args, _ = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    blocked = ma.validate_provider_size(args, args["_multi_angle"], "unknown", {})
    assert blocked["submitted"] is False and "catalogue" in blocked["error"]
    rows[0]["blocks"].pop()
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "5:4"}
    args, _ = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    blocked = ma.validate_provider_size(args, args["_multi_angle"], "limited", {"limited": metadata({"aspect_ratio": {"enum": ["1:1"]}})})
    assert blocked["submitted"] is False and "unsupported" in blocked["error"]


def test_pixels_or_preview_edits_after_dispatch_fail_before_cached_replay(run):
    rows, _ = run
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "1200x1200"}
    args, _ = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    complete_preview(args)
    original = copy.deepcopy(rows)
    root = rows[1]["blocks"][0]
    root["answers"][ma.ASPECT]["other_text"] = "1000x1000"
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]
    rows[:] = original
    add_text(rows, "preview 800x800")
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]


def test_default_size_also_respects_detectable_provider_bounds(run):
    rows, _ = run
    setup(rows)
    args, _ = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    blocked = ma.validate_provider_size(args, args["_multi_angle"], "small-only", {
        "small-only": metadata({"size": {"type": "string", "maximum": 1024}})})
    assert blocked["submitted"] is False and "range/step" in blocked["error"]


def test_fresh_explicit_skill_start_does_not_inherit_old_user_dimensions(run):
    rows, _ = run
    add_text(rows, "1200x900")
    setup(rows, "4:3")
    args, _ = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    complete_preview(args)
    rows.append({"id": "new-start", "role": "user", "blocks": [
        {"type": "skill", "name": ma.SKILL},
        {"type": "text", "text": "新的商品图 1400x1000; preview 1400x1000"},
        {"type": "image", "url": "new-reference"}]})
    root = setup(rows)
    root["answers"][ma.ASPECT] = {"selected": [], "other_text": "7:5"}
    rows[-1]["id"] = "new-setup"
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None and args["_multi_angle"]["key"] == "preview"
    assert (args["width"], args["height"]) == (1400, 1000)
    assert "1200x900" not in args["prompt"] and args["refs"] == ["new-reference"]


@pytest.mark.asyncio
async def test_model_routing_cannot_rewrite_explicit_dimensions(run, monkeypatch):
    rows, sent = run
    add_text(rows, "1200x900; preview 1200x900")
    setup(rows, "4:3")

    def rewritten(action, args, **kwargs):
        return {"model": "mock-pixels", "auto": False, "category": "user",
                "_exact_args": {**args, "width": 2048, "height": 1536}}

    monkeypatch.setattr(canvas, "select_model", rewritten)
    result = await canvas._relay("generate_image")({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert result["submitted"] is False and "Routing changed" in result["error"]
    assert sent == [] and ma.LEDGER not in ma._root("chat-ma")[1]


@pytest.mark.parametrize("ratio", ["9:16", "5:4"])
def test_model_preview_choice_frozen_on_first_dispatch_not_pure_prepare(run, ratio):
    rows, _ = run
    setup(rows, "1:1")
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": ratio})
    assert blocked is None and args["ratio"] == ratio
    # A quote/preflight is pure and cannot freeze a model layout prematurely.
    changed, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "4:3"})
    assert blocked is None and changed["ratio"] == "4:3"
    ma.reserve(args["_multi_angle"])
    ma.submitted(args["_multi_angle"], {"ids": ["same-preview"], "submitted": True})
    _, replay = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "3:4"})
    assert replay["ids"] == ["same-preview"] and replay["multi_angle_replay"]
    ledger = ma._root("chat-ma")[1][ma.LEDGER]
    assert ledger["setup_snapshot"]["preview"]["ratio"] == ratio
    ma.record_wait({"results": [{"id": "same-preview", "status": "done", "placed": True,
                                 "delivered": 1, "shapes": ["preview-shape"]}]})
    choose(rows, ("1",))
    final, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "composition_id": "1", "ratio": "9:16", "width": 999, "height": 333})
    assert blocked is None and (final["width"], final["height"], final["ratio"]) == (2048, 2048, "1:1")
    assert final["_multi_angle"]["setup_snapshot"]["preview"]["ratio"] == ratio


def test_prepare_and_quote_consistent_for_model_preview_and_final_exact_pixels(run, monkeypatch):
    rows, _ = run
    add_text(rows, "1200x900")
    setup(rows, "4:3")
    raw = {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "9:16", "width": 333, "height": 999}
    args, blocked = ma.prepare(raw)
    assert blocked is None and not args["_multi_angle"]["stage_spec"]["exact_pixels"]
    repeated, blocked = ma.prepare(args)
    assert blocked is None and repeated == args
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "mock", "auto": True})
    model, quote = canvas.quote_route("generate_image", raw, catalog={})
    assert model == "mock" and (quote["width"], quote["height"], quote["ratio"]) == (1152, 2048, "9:16")
    assert ma.LEDGER not in ma._root("chat-ma")[1]
    complete_preview(args)
    choose(rows, ("1",))
    final, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "composition_id": "1", "width": 2048, "height": 2048, "ratio": "1:1"})
    assert blocked is None and (final["width"], final["height"], final["ratio"]) == (1200, 900, "4:3")
    assert ma.validate_provider_size(final, final["_multi_angle"], "unknown", {})["submitted"] is False


def test_explicit_preview_request_cannot_be_added_after_model_layout_dispatched(run):
    rows, _ = run
    setup(rows)
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "9:16"})
    assert blocked is None
    complete_preview(args)
    # Even the same ratio cannot silently change the frozen request's authority.
    add_text(rows, "preview 9:16")
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]


def test_prepare_is_idempotent_when_only_final_pixels_requested(run):
    rows, _ = run
    add_text(rows, "1200x900")
    setup(rows, "4:3")
    once, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None
    twice, blocked = ma.prepare(once)
    assert blocked is None and twice == once
    assert once["_multi_angle"]["setup_snapshot"]["final"]["exact_pixels"]
    assert not once["_multi_angle"]["stage_spec"]["exact_pixels"]


@pytest.mark.parametrize("preview_request,expected", [("9:16", (1152, 2048, "9:16")),
                                              ("1200x960", (1200, 960, "5:4"))])
def test_explicit_preview_request_wins_and_is_immutable_through_replay(run, preview_request, expected):
    rows, _ = run
    add_text(rows, "preview " + preview_request)
    setup(rows, "1:1")
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "4:3", "width": 999, "height": 333})
    assert blocked is None and (args["width"], args["height"], args["ratio"]) == expected
    ma.reserve(args["_multi_angle"])
    ma.submitted(args["_multi_angle"], {"ids": ["explicit-preview"], "submitted": True})
    _, replay = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "3:4"})
    assert replay["ids"] == ["explicit-preview"] and replay["multi_angle_replay"]
    rows[0]["blocks"][-1]["text"] = "preview 4:3"
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]


@pytest.mark.asyncio
async def test_explicit_user_pixels_survive_skill_pin_and_quote_with_exact_audit(run, monkeypatch):
    """Explicit 1152x2048 must keep exact audit after _pin_args and on the quote path.

    A same-ratio larger file (the paid 1440x2560 mismatch) must not pass exact audit.
    No provider call is made.
    """
    import io
    from PIL import Image
    from ComfyArt.api.skill_size import RATIO_MODE, audit_file, size_notice

    rows, sent = run
    add_text(rows, "预览1152x2048")
    setup(rows, "1:1")
    catalog = {"mock-pixels": metadata({"size": {"type": "string", "minimum": 64, "maximum": 4096}})}
    pin = {"model": "mock-pixels", "auto": False, "category": "skill", "skill": ma.SKILL,
           "reason": {"zh": "技能钉", "en": "Skill pin"}}
    monkeypatch.setattr(wavespeed, "cached_models", lambda: catalog)
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: dict(pin))

    preview, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "9:16"})
    assert blocked is None
    meta = preview["_multi_angle"]
    spec = meta["stage_spec"]
    assert spec["exact_pixels"] is True
    assert (spec["width"], spec["height"], spec["ratio"]) == (1152, 2048, "9:16")
    assert (preview["width"], preview["height"]) == (1152, 2048)
    assert "size_lock_mode" not in preview

    pinned = canvas._pin_args({k: v for k, v in preview.items() if k != "_multi_angle"}, pin)
    assert "width" not in pinned and "height" not in pinned
    assert "size_lock_mode" not in pinned
    # Metadata from prepare stays authoritative and is not rewritten by the pin.
    assert (meta["stage_spec"]["width"], meta["stage_spec"]["height"]) == (1152, 2048)
    ma.apply_audit_mode(pinned, meta)
    assert (pinned["width"], pinned["height"], pinned["ratio"]) == (1152, 2048, "9:16")
    assert "size_lock_mode" not in pinned and pinned["size_lock"] is True
    assert ma.validate_provider_size(pinned, meta, "mock-pixels", catalog) is None

    rewritten = {**preview, "width": 1440, "height": 2560}
    ma.apply_audit_mode(rewritten, meta)
    assert (rewritten["width"], rewritten["height"]) == (1440, 2560)
    assert ma.validate_provider_size(rewritten, meta, "mock-pixels", catalog)["submitted"] is False

    image = io.BytesIO()
    Image.new("RGB", (1440, 2560), "white").save(image, format="PNG")
    data = image.getvalue()
    exact = audit_file(data, (pinned["width"], pinned["height"]), pinned.get("size_lock_mode", ""))
    assert exact["match"] is False
    assert exact["provider_output"] == {"width": 1440, "height": 2560}
    note = size_notice((1152, 2048), (1440, 2560), pinned.get("size_lock_mode", ""))
    assert "smaller" not in note["en"] and "低于" not in note["zh"]
    assert "1440×2560" in note["en"] and "1440×2560" in note["zh"]
    # Contrast only: the same file would pass ratio audit, which must not be used here.
    assert audit_file(data, (1152, 2048), RATIO_MODE)["match"] is True

    model, inputs = canvas.quote_route(
        "generate_image",
        {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "model": "mock-pixels"},
        catalog=catalog)
    assert model == "mock-pixels"
    assert (inputs["width"], inputs["height"], inputs["ratio"]) == (1152, 2048, "9:16")
    assert "size_lock_mode" not in inputs
    assert ma.LEDGER not in ma._root("chat-ma")[1]

    result = await canvas._relay("generate_image")(
        {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "width": 2048, "height": 2048})
    assert result["ids"] and len(sent) == 1
    actual = sent[0][1]
    assert (actual["width"], actual["height"], actual["ratio"]) == (1152, 2048, "9:16")
    assert "size_lock_mode" not in actual
    assert actual["size_lock"] is True
    assert actual["auto_model"] is False and actual["size_candidates"] == ["mock-pixels"]
    assert (meta["stage_spec"]["width"], meta["stage_spec"]["height"]) == (1152, 2048)
