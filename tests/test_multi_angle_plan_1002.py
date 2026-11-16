"""Subject planning contract: no paid API, no browser, no global view fallback."""
import copy

import pytest

from ComfyArt.api import multi_angle as ma
from ComfyArt.api import bot_asks
from ComfyArt.api.mcp_tools import canvas
from multi_angle_plan_fixture import HEADPHONES_PLAN, PAID_FAILURE_PLAN
from test_multi_angle_stages_911 import run, setup, choose  # noqa: F401


def subject_plan(subject, purpose, details):
    return {"subject": subject, "purpose": purpose, "panels": [
        {"id": str(i), "name": detail, "description": f"{subject}: {detail}; intended use: {purpose}"}
        for i, detail in enumerate(details, 1)
    ]}


PLANS = [HEADPHONES_PLAN,
    subject_plan("ceramic teapot", "online shop product page", [
        "spout profile", "handle side", "lid fit", "open rim", "glaze detail", "pouring silhouette",
        "base stamp", "overhead opening", "whole pot three-quarter"]),
    subject_plan("courtyard building", "architectural presentation", [
        "street elevation", "courtyard entry", "roof plan", "garden-facing facade", "window detail",
        "entrance threshold", "courtyard perspective", "wall material", "roof edge"]),
]


def prepare(plan):
    args, blocked = ma.prepare({"skill": ma.SKILL, "ratio": "9:16", "composition_plan": plan})
    assert blocked is None, blocked
    return args


def deliver(meta):
    assert ma.reserve(meta) is None
    ma.submitted(meta, {"ids": ["preview"]})
    ma.record_wait({"results": [{"id": "preview", "status": "done", "placed": True,
                               "shapes": ["preview-shape"]}]})


@pytest.mark.parametrize("plan", PLANS)
def test_subject_specific_plan_is_only_mapping_for_lineart_card_and_selected_finals(run, plan):
    rows, sent = run
    rows[0]["blocks"][1]["text"] = plan["purpose"]
    setup(rows)
    args = prepare(plan)
    meta = args["_multi_angle"]
    assert meta["composition_plan"] == plan
    for panel in plan["panels"]:
        assert f"{panel['id']}: {panel['name']} — {panel['description']}" in args["prompt"]
    deliver(meta)
    choose(rows, ("2", "7", "9"))
    card = rows[-1]["blocks"][0]
    opts = card["questions"][0]["options"]
    assert [(p["id"], p["label"], p["description"]) for p in opts] == [
        (p["id"], f"{p['id']} {p['name']}", p["description"]) for p in plan["panels"]]
    for number in ("2", "7", "9"):
        final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": number})
        assert blocked is None
        chosen = plan["panels"][int(number) - 1]
        assert f"composition {number}: {chosen['name']} — {chosen['description']}" in final["prompt"]
        assert final["ratio"] == "1:1"
        assert final["refs"][-1] == "preview-shape"
    assert sent == []


def test_no_plan_blocks_preview_and_legacy_final_before_any_paid_submission(run):
    rows, sent = run
    block = setup(rows)
    _, blocked = ma.prepare({"skill": ma.SKILL})
    assert blocked["submitted"] is False and "composition_plan" in blocked["error"]
    # Legacy record may have a delivered image and valid setup, but no panel map.
    args = prepare(HEADPHONES_PLAN)
    deliver(args["_multi_angle"])
    # The durable row is re-read (save updates replaced the copied blocks).
    rows[1]["blocks"][0][ma.LEDGER].pop("composition_plan", None)
    with pytest.raises(ValueError, match="composition_plan"):
        bot_asks.validate_spec({"prompt": "choose"})
    rows.append({"id": "legacy-choice", "role": "assistant", "blocks": [{
        "type": "ask", "status": "answered", "answers": {ma.COMPOSITIONS: {"selected": ["1"]}}}]})
    _, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "1"})
    assert blocked["submitted"] is False
    assert sent == []


@pytest.mark.parametrize("damage", ["missing", "empty", "count", "duplicate_id", "invalid_id", "empty_name",
                                     "empty_description", "duplicate_name", "duplicate_description", "missing_subject", "missing_purpose"])
def test_invalid_planning_never_proceeds(run, damage):
    rows, sent = run
    setup(rows)
    plan = copy.deepcopy(HEADPHONES_PLAN)
    if damage == "missing": plan = None
    elif damage == "empty": plan = {}
    elif damage == "count": plan["panels"].pop()
    elif damage == "duplicate_id": plan["panels"][1]["id"] = "1"
    elif damage == "invalid_id": plan["panels"][0]["id"] = "11"
    elif damage == "empty_name": plan["panels"][0]["name"] = " "
    elif damage == "empty_description": plan["panels"][0]["description"] = ""
    elif damage == "duplicate_name": plan["panels"][1]["name"] = plan["panels"][0]["name"]
    elif damage == "duplicate_description": plan["panels"][1]["description"] = plan["panels"][0]["description"]
    elif damage == "missing_subject": plan.pop("subject")
    elif damage == "missing_purpose": plan.pop("purpose")
    _, blocked = ma.prepare({"skill": ma.SKILL, "composition_plan": plan})
    assert blocked["submitted"] is False
    assert sent == []


def test_pure_quote_not_frozen_then_first_dispatch_persists_and_recovery_does_not_reorder(run, monkeypatch):
    rows, _ = run
    setup(rows)
    quoted = prepare(HEADPHONES_PLAN)
    assert not rows[1]["blocks"][0].get(ma.LEDGER)
    dispatched = prepare(PLANS[1])  # model may revise before any paid dispatch
    assert ma.reserve(dispatched["_multi_angle"]) is None
    assert rows[1]["blocks"][0][ma.LEDGER]["composition_plan"] == PLANS[1]
    ma.submitted(dispatched["_multi_angle"], {"ids": ["first-preview"]})
    # Simulated restart: only durable chat rows remain. A changed plan is ignored.
    from ComfyArt.api import bot_turns
    monkeypatch.setattr(bot_turns, "ACTIVE_TURNS", {})
    _, replay = ma.prepare({"skill": ma.SKILL, "composition_plan": PLANS[2]})
    assert replay["ids"] == ["first-preview"]
    ma.record_wait({"results": [{"id": "first-preview", "status": "done", "placed": True,
                               "shapes": ["placed-preview"]}]})
    choose(rows, ("3",))
    final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "3", "composition_plan": PLANS[2]})
    assert blocked is None
    assert final["_multi_angle"]["composition_plan"] == PLANS[1]
    assert "lid fit" in final["prompt"] and "roof plan" not in final["prompt"]
    assert quoted["_multi_angle"]["composition_plan"] == HEADPHONES_PLAN


def test_reserve_rejects_conflicting_plan_after_other_dispatch_wins(run):
    rows, _ = run
    setup(rows)
    first = prepare(HEADPHONES_PLAN)
    stale = prepare(PLANS[1])
    assert ma.reserve(first["_multi_angle"]) is None
    blocked = ma.reserve(stale["_multi_angle"])
    assert blocked["submitted"] is False and "concurrently" in blocked["error"]


@pytest.mark.asyncio
async def test_actual_relay_persists_plan_before_command_and_strips_tool_only_field(run, monkeypatch):
    rows, _ = run
    setup(rows)
    calls = []
    async def page(action, args, *a, **kw):
        assert rows[1]["blocks"][0][ma.LEDGER]["composition_plan"] == HEADPHONES_PLAN
        assert rows[1]["blocks"][0][ma.LEDGER]["preview"]["status"] == "reserved"
        assert "composition_plan" not in args
        calls.append(args)
        return {"ids": ["paid-mock"]}
    monkeypatch.setattr(canvas, "submit_command", page)
    result = await canvas._relay("generate_image")({"skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN})
    assert result["ids"] == ["paid-mock"] and len(calls) == 1


# Reusable regression derived from the 2026-11-17 paid failure: Flare returned
# 1440x2560 for requested fallback 1152x2048; no new provider call is necessary.
def test_paid_preview_failure_prompt_is_line_only_and_final_restores_material(run):
    rows, _ = run
    setup(rows)
    preview = prepare(HEADPHONES_PLAN)
    assert "thin black contour/structural lines" in preview["prompt"]
    assert "No color, gray fills, shading, gradients, shadows" in preview["prompt"]
    assert "identity/geometry ONLY" in preview["prompt"]
    assert "actual top-facing geometry rather than reuse the front silhouette" in preview["prompt"]
    assert "Preserve subject identity, material" not in preview["prompt"]
    deliver(preview["_multi_angle"])
    choose(rows, ("1",))
    final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "1"})
    assert blocked is None
    assert "Restore the original subject's material, color and finish" in final["prompt"]
    assert "LINEART ONLY" not in final["prompt"]


@pytest.mark.parametrize("actual,passes", [((1440, 2560), True), ((1152, 2048), True),
                                           ((576, 1024), False), ((2048, 2048), False)])
def test_paid_preview_default_uses_ratio_and_minimum_size_not_exact_pixels(run, actual, passes):
    import io
    from PIL import Image
    from ComfyArt.api.skill_size import audit_file
    rows, _ = run
    setup(rows)
    preview = prepare(HEADPHONES_PLAN)
    assert preview["size_lock_mode"] == "ratio"
    image = io.BytesIO()
    Image.new("RGB", actual, "white").save(image, format="PNG")
    audit = audit_file(image.getvalue(), (preview["width"], preview["height"]), preview["size_lock_mode"])
    assert audit["match"] is passes
    assert audit["provider_output"] == {"width": actual[0], "height": actual[1]}
    if passes:
        assert audit["notice"] is None


def test_explicit_preview_pixels_keep_exact_audit_even_when_larger_file_has_same_ratio(run):
    from ComfyArt.api import skill_size
    rows, _ = run
    rows[0]["blocks"][1]["text"] += "; 预览1152x2048"
    setup(rows)
    preview = prepare(HEADPHONES_PLAN)
    assert preview["_multi_angle"]["stage_spec"]["exact_pixels"]
    assert "size_lock_mode" not in preview
    assert not skill_size.reconcile((1152, 2048), (1440, 2560))["match"]
    note = skill_size.size_notice((1152, 2048), (1440, 2560))
    assert "smaller" not in note["en"] and "低于" not in note["zh"]
    assert "1440×2560" in note["en"] and "1440×2560" in note["zh"]


@pytest.mark.asyncio
async def test_relay_restores_ratio_audit_after_routing_without_relaxing_explicit_pixels(run):
    rows, sent = run
    setup(rows)
    result = await canvas._relay("generate_image")({"skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN})
    assert result["ids"] and sent[-1][1]["size_lock_mode"] == "ratio"



PREVIEW_MATERIAL_DEFER_EN = (
    "Material, color, finish, lighting, shading, and photographic rendering clauses "
    "are omitted from this LINEART ONLY stage and remain in the persisted plan for finished images")
PREVIEW_MATERIAL_DEFER_ZH = "规划文案中的材质、色彩、表面处理、光线、明暗与写实渲染条款在本线稿阶段不可执行"
FINAL_ORIENTATION = (
    "Preserve that selected panel's screen-left/right orientation, camera direction and handedness")
FINAL_NO_MIRROR = "do not mirror, horizontally flip, or reverse the composition"
ARCHIVE_PLAN = (
    "/workspace/qa1002-0f0e9328-appstack-paid/paid/chat-after-composition-card.json")


def test_paid_failure_plan_matches_archived_ledger_when_present():
    import json
    from pathlib import Path
    path = Path(ARCHIVE_PLAN)
    if not path.exists():
        return
    chat = json.loads(path.read_text())
    archived = chat[1]["blocks"][0][ma.LEDGER]["composition_plan"]
    assert archived == PAID_FAILURE_PLAN
    assert "exact gray materials" in archived["panels"][0]["description"]
    assert "matte surface finish" in archived["panels"][4]["description"]


def test_preview_text_drops_appearance_directives_and_keeps_geometry_subjects():
    assert ma.preview_text("exact gray materials, pure white seamless background") == "pure white seamless background"
    assert "matte surface finish" not in ma.preview_text(
        "outer earcup shell and matte surface finish close-up matching the reference plastic, white seamless")
    assert "matching the reference plastic" not in ma.preview_text(
        "outer earcup shell and matte surface finish close-up matching the reference plastic, white seamless")
    assert "outer earcup shell" in ma.preview_text(
        "outer earcup shell and matte surface finish close-up matching the reference plastic, white seamless")
    assert ma.preview_text("inside earcup cushion detail and lining texture") == "inside earcup cushion detail and lining texture"
    assert ma.preview_text("outer earcup shell and surface finish close-up") == "outer earcup shell and surface finish close-up"
    assert ma.preview_text("courtyard building: wall material; intended use: architectural presentation") == (
        "courtyard building: wall material; intended use: architectural presentation")
    assert ma.preview_text("正面机位，完整门楼几何，亚光灰材质仅作成品说明") == "正面机位，完整门楼几何"
    assert ma.preview_text("墙面材质特写") == "墙面材质特写"
    assert "matte gray" not in ma.preview_text(
        "matte gray over-ear headphones in the supplied front-view reference").casefold()
    assert "over-ear headphones" in ma.preview_text(
        "matte gray over-ear headphones in the supplied front-view reference")
    view = ma.preview_plan_view(PAID_FAILURE_PLAN)
    assert view["purpose"] == PAID_FAILURE_PLAN["purpose"]
    assert [p["id"] for p in view["panels"]] == [p["id"] for p in PAID_FAILURE_PLAN["panels"]]
    assert [p["name"] for p in view["panels"]] == [p["name"] for p in PAID_FAILURE_PLAN["panels"]]
    assert view != PAID_FAILURE_PLAN
    assert "exact gray materials" not in view["panels"][0]["description"]
    assert "front-on full product" in view["panels"][0]["description"]


def test_paid_failure_plan_material_clauses_are_omitted_from_preview_not_rewritten(run):
    rows, _ = run
    setup(rows)
    preview = prepare(PAID_FAILURE_PLAN)
    assert preview["_multi_angle"]["composition_plan"] == PAID_FAILURE_PLAN
    prompt = preview["prompt"]
    view = ma.preview_plan_view(PAID_FAILURE_PLAN)
    assert "exact gray materials" not in prompt
    assert "matte surface finish" not in prompt
    assert "same gray headphones" not in prompt
    assert "matching the reference plastic" not in prompt
    assert "matte gray" not in prompt
    for panel, projected in zip(PAID_FAILURE_PLAN["panels"], view["panels"]):
        assert f"{panel['id']}: {panel['name']} — {projected['description']}" in prompt
        assert panel["name"] in prompt
    assert "front-on full product" in prompt
    assert "top-down view of the headband arc" in prompt
    assert PREVIEW_MATERIAL_DEFER_EN in prompt and PREVIEW_MATERIAL_DEFER_ZH in prompt
    assert "LINEART ONLY" in prompt
    assert "Preserve subject identity, material" not in prompt
    deliver(preview["_multi_angle"])
    choose(rows, ("1", "5"))
    for number, phrase in (("1", "exact gray materials"), ("5", "matte surface finish")):
        final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": number})
        assert blocked is None
        assert final["_multi_angle"]["composition_plan"] == PAID_FAILURE_PLAN
        assert phrase in final["prompt"]
        assert f"{PAID_FAILURE_PLAN['panels'][int(number) - 1]['name']} — {PAID_FAILURE_PLAN['panels'][int(number) - 1]['description']}" in final["prompt"]
        assert "Restore the original subject's material, color and finish" in final["prompt"]
        assert "LINEART ONLY" not in final["prompt"]
        assert PREVIEW_MATERIAL_DEFER_EN not in final["prompt"]
        assert PREVIEW_MATERIAL_DEFER_ZH not in final["prompt"]


def test_paid_failure_final_prompt_preserves_selected_panel_handedness(run):
    rows, _ = run
    setup(rows)
    preview = prepare(PAID_FAILURE_PLAN)
    deliver(preview["_multi_angle"])
    choose(rows, ("2",))
    final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "2"})
    assert blocked is None
    prompt = final["prompt"]
    chosen = PAID_FAILURE_PLAN["panels"][1]
    assert f"composition 2: {chosen['name']} — {chosen['description']}" in prompt
    assert "Match that exact numbered panel in the delivered preview" in prompt
    assert FINAL_ORIENTATION in prompt and FINAL_NO_MIRROR in prompt
    assert "Infer orientation only from the selected frozen panel" in prompt
    assert "do not invent a preferred facing" in prompt
    assert "LINEART ONLY" not in prompt
    assert "facing left" not in prompt.lower()
    assert "face left" not in prompt.lower()
    assert "headphones face" not in prompt.lower()


def test_geometry_label_wall_material_is_not_stripped_from_frozen_plan(run):
    rows, _ = run
    rows[0]["blocks"][1]["text"] = PLANS[2]["purpose"]
    setup(rows)
    preview = prepare(PLANS[2])
    assert preview["_multi_angle"]["composition_plan"] == PLANS[2]
    assert "8: wall material — " in preview["prompt"]
    assert PREVIEW_MATERIAL_DEFER_EN in preview["prompt"]
    deliver(preview["_multi_angle"])
    choose(rows, ("8",))
    final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "8"})
    assert blocked is None
    assert "composition 8: wall material — " in final["prompt"]
    assert "headphones" not in final["prompt"]
    assert FINAL_ORIENTATION in final["prompt"]
    assert PREVIEW_MATERIAL_DEFER_EN not in final["prompt"]


def test_chinese_camera_and_material_clauses_follow_stage_priority(run):
    rows, _ = run
    plan = subject_plan("红砖庭院门楼", "建筑展示册", [
        "临街立面", "庭院入口", "屋顶平面", "朝园立面", "窗楣细节",
        "门槛进深", "庭院透视", "墙面材质特写", "檐口轮廓"])
    plan["panels"][0]["description"] = "正面机位，完整门楼几何，亚光灰材质仅作成品说明"
    rows[0]["blocks"][1]["text"] = plan["purpose"]
    setup(rows)
    preview = prepare(plan)
    assert preview["_multi_angle"]["composition_plan"] == ma.validate_plan(plan)
    assert "亚光灰材质仅作成品说明" not in preview["prompt"]
    assert "正面机位，完整门楼几何" in preview["prompt"]
    assert "墙面材质特写" in preview["prompt"]
    assert PREVIEW_MATERIAL_DEFER_ZH in preview["prompt"]
    deliver(preview["_multi_angle"])
    choose(rows, ("1", "8"))
    final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "1"})
    assert blocked is None
    assert "亚光灰材质仅作成品说明" in final["prompt"] and "正面机位" in final["prompt"]
    assert PREVIEW_MATERIAL_DEFER_ZH not in final["prompt"]
    assert FINAL_ORIENTATION in final["prompt"]
    wall, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "8"})
    assert blocked is None and "墙面材质特写" in wall["prompt"]
    assert "headphones" not in wall["prompt"]
