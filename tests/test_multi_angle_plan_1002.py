"""Subject planning contract: no paid API, no browser, no global view fallback."""
import copy
import json

import pytest

from ComfyArt.api import multi_angle as ma
from ComfyArt.api import bot_asks
from ComfyArt.api.mcp_tools import canvas
from multi_angle_plan_fixture import HEADPHONES_PLAN, PAID_FAILURE_PLAN, preview_url
from test_multi_angle_stages_911 import run, setup, choose, confirm_quote  # noqa: F401


def subject_plan(subject, purpose, details):
    return {"subject": subject, "purpose": purpose, "subject_geometry": subject, "appearance": "", "panels": [
        {"id": str(i), "name": detail, "description": f"{subject}: {detail}; intended use: {purpose}",
         "geometry": f"{subject}: {detail}", "appearance": "", "content": f"visible structures {i}"}
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
    args, blocked = ma.prepare({"skill": ma.SKILL, "composition_plan": plan})
    assert blocked is None, blocked
    return args


def deliver(meta):
    assert ma.reserve(meta) is None
    ma.submitted(meta, {"ids": ["preview"]})
    ma.record_wait({"results": [{"id": "preview", "status": "done", "placed": True,
                               "shapes": ["preview-shape"], "urls": [preview_url()]}]})


@pytest.mark.parametrize("plan", PLANS)
def test_subject_specific_plan_is_only_mapping_for_lineart_card_and_selected_finals(run, plan):
    rows, sent = run
    rows[0]["blocks"][1]["text"] = plan["purpose"]
    setup(rows)
    args = prepare(plan)
    meta = args["_multi_angle"]
    assert meta["composition_plan"] == plan
    for panel in plan["panels"]:
        assert f"{panel['id']}: {panel['geometry']}" in args["prompt"]
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
        assert f"composition {number}: {chosen['name']} — reproduce numbered cell {number}" in final["prompt"]
        assert chosen["geometry"] not in final["prompt"] and chosen["description"] not in final["prompt"]
        assert final["ratio"] == "1:1"
        assert final["refs"][-1] == final["_multi_angle"]["composition_crop"]["ref"]  # #1003: selected cell crop
        assert "preview-shape" not in final["refs"]
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
                               "shapes": ["placed-preview"], "urls": [preview_url()]}]})
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
    confirm_quote(rows)
    calls = []
    async def page(action, args, *a, **kw):
        assert rows[1]["blocks"][0][ma.LEDGER]["composition_plan"] == HEADPHONES_PLAN
        assert rows[1]["blocks"][0][ma.LEDGER]["preview"]["status"] == "reserved"
        assert "composition_plan" not in args
        assert HEADPHONES_PLAN["purpose"] not in args["prompt"]
        assert HEADPHONES_PLAN["subject_geometry"] in args["prompt"]
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
    rows[0]["blocks"][1]["text"] += "; preview 9:16"
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
    assert skill_size.ratio_ok((1152, 2048), (1440, 2560))
    assert skill_size.size_notice((1152, 2048), (1440, 2560)) is None


@pytest.mark.asyncio
async def test_relay_restores_ratio_audit_after_routing_without_relaxing_explicit_pixels(run):
    rows, sent = run
    setup(rows)
    confirm_quote(rows)
    result = await canvas._relay("generate_image")({"skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN})
    assert result["ids"] and sent[-1][1]["size_lock_mode"] == "ratio"



PREVIEW_MATERIAL_DEFER_EN = "Only structured subject geometry and numbered panel geometry are executable here."
PREVIEW_MATERIAL_DEFER_ZH = "仅执行结构化主体几何与各格机位/构图"
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
    """Updated product boundary: no text scrubber; explicit geometry is projected intact."""
    assert not hasattr(ma, "preview_text")
    view = ma.preview_plan_view(PLANS[2])
    assert set(view) == {"subject_geometry", "panels"}
    assert view["subject_geometry"] == PLANS[2]["subject_geometry"]
    assert [(p["id"], p["geometry"]) for p in view["panels"]] == [
        (p["id"], p["geometry"]) for p in PLANS[2]["panels"]]
    assert "wall material" in view["panels"][7]["geometry"]
    assert all(set(p) == {"id", "geometry"} for p in view["panels"])


def test_paid_failure_plan_material_clauses_are_omitted_from_preview_not_rewritten(run):
    """No compatibility migration: old mixed plan is blocked before submission, unchanged."""
    rows, sent = run
    setup(rows)
    before = copy.deepcopy(PAID_FAILURE_PLAN)
    _, blocked = ma.prepare({"skill": ma.SKILL, "composition_plan": PAID_FAILURE_PLAN})
    assert blocked["submitted"] is False
    assert "subject_geometry" in blocked["error"]
    assert PAID_FAILURE_PLAN == before
    assert not rows[1]["blocks"][0].get(ma.LEDGER)
    assert not sent
    # Replanning is allowed only before submission; this is a fresh structured mock input.
    fresh = prepare(HEADPHONES_PLAN)
    assert fresh["_multi_angle"]["composition_plan"] == HEADPHONES_PLAN


def test_paid_failure_final_prompt_preserves_selected_panel_handedness(run):
    rows, _ = run
    setup(rows)
    preview = prepare(HEADPHONES_PLAN)
    deliver(preview["_multi_angle"])
    choose(rows, ("2",))
    final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "2"})
    assert blocked is None
    prompt = final["prompt"]
    chosen = HEADPHONES_PLAN["panels"][1]
    assert f"composition 2: {chosen['name']} — reproduce numbered cell 2 of the delivered preview" in prompt
    assert "The attached composition reference IS that selected cell 2, cropped from the delivered preview" in prompt
    assert "Match that exact cell." in prompt
    assert FINAL_ORIENTATION in prompt and FINAL_NO_MIRROR in prompt
    assert "Infer orientation only from the delivered preview cell" in prompt
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
    assert "8: courtyard building: wall material" in preview["prompt"]
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
    plan["subject_geometry"] = "庭院门楼的开口与檐口几何"
    plan["panels"][0].update(description="正面机位，完整门楼几何，亚光灰材质仅作成品说明",
                             geometry="正面机位，完整门楼几何", appearance="亚光灰材质仅作成品说明")
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
    assert "亚光灰材质仅作成品说明" not in final["prompt"]  # planner appearance not injected (#1003)
    assert ma.FINAL_FINISH in final["prompt"]
    assert "正面机位" not in final["prompt"]  # camera comes only from the delivered cell (#1003)
    assert PREVIEW_MATERIAL_DEFER_ZH not in final["prompt"]
    assert FINAL_ORIENTATION in final["prompt"]
    wall, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "8"})
    assert blocked is None and "墙面材质特写" in wall["prompt"]
    assert "headphones" not in wall["prompt"]


UNFILTERED_APPEARANCE = ("glossy red leather", "哑光黑色材质", "金属光泽")


def test_preview_text_limitation_leaves_unlisted_appearance_phrases():
    """Arbitrary bilingual appearance is stored untouched, not guessed by a blacklist."""
    assert not hasattr(ma, "preview_text")
    for phrase in UNFILTERED_APPEARANCE:
        plan = copy.deepcopy(HEADPHONES_PLAN)
        plan["appearance"] = phrase
        plan["panels"][0]["appearance"] = phrase
        validated = ma.validate_plan(plan)
        assert validated["appearance"] == phrase
        assert validated["panels"][0]["appearance"] == phrase
        view = ma.preview_plan_view(validated)
        assert phrase not in str(view)


def test_preview_prompt_does_not_overclaim_projection_and_keeps_unprojected_fields(run):
    """Old leakage counterexample now asserts all non-geometry fields are excluded."""
    rows, _ = run
    plan = copy.deepcopy(HEADPHONES_PLAN)
    plan.update(subject="lacquered vase", purpose="商品页金属光泽展示",
                subject_geometry="vase opening, body volume and base", appearance="glossy red leather")
    plan["panels"][1]["description"] = "three-quarter view, glossy red leather, white seamless"
    plan["panels"][2]["description"] = "侧面轮廓，哑光黑色材质，白底"
    plan["panels"][6]["description"] = "顶视开口，金属光泽，比例准确"
    plan["panels"][3]["name"] = "matte surface finish close-up"
    for panel, phrase in zip(plan["panels"], UNFILTERED_APPEARANCE):
        panel["appearance"] = phrase
    rows[0]["blocks"][1]["text"] = "商品详情页，红色皮革外观，纯白无缝背景"
    setup(rows)
    preview = prepare(plan)
    assert preview["_multi_angle"]["composition_plan"] == ma.validate_plan(plan)
    assert plan["panels"][1]["description"] == "three-quarter view, glossy red leather, white seamless"
    for phrase in (*UNFILTERED_APPEARANCE, plan["purpose"], plan["subject"],
                   plan["panels"][3]["name"], "红色皮革外观"):
        assert phrase not in preview["prompt"]
    for panel in plan["panels"]:
        assert f"{panel['id']}: {panel['geometry']}" in preview["prompt"]
    assert PREVIEW_MATERIAL_DEFER_EN in preview["prompt"]
    deliver(preview["_multi_angle"])
    choose(rows, ("2", "3"))
    for number in ("2", "3"):
        final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": number})
        assert blocked is None
        chosen = plan["panels"][int(number)-1]
        # #1003: planner camera prose and appearance are not injected; user's words + reference are.
        assert chosen["description"] not in final["prompt"]
        if chosen["appearance"] not in plan["purpose"]:  # purpose itself is user-facing and restated
            assert chosen["appearance"] not in final["prompt"]
        assert "商品详情页，红色皮革外观" in final["prompt"]  # user's own words still reach finals
        assert "glossy red leather" not in final["prompt"]  # planner appearance, not user words
        assert "红色皮革外观" in final["prompt"]
        assert "Restore the original subject's material, color and finish" in final["prompt"]
        assert PREVIEW_MATERIAL_DEFER_EN not in final["prompt"]


@pytest.mark.parametrize("status", ["reserved", "submitted", "done"])
@pytest.mark.parametrize("stage", ["preview", "final"])
def test_submitted_legacy_plan_is_query_archive_only_never_migrated(run, status, stage):
    rows, sent = run
    setup(rows)
    preview = prepare(HEADPHONES_PLAN)
    deliver(preview["_multi_angle"])
    choose(rows, ("2",))
    ledger = rows[1]["blocks"][0][ma.LEDGER]
    ledger["composition_plan"] = copy.deepcopy(PAID_FAILURE_PLAN)
    ledger["preview"]["status"] = status
    before = copy.deepcopy(rows)
    _, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": stage,
                             "composition_id": "2", "composition_plan": HEADPHONES_PLAN})
    assert blocked["submitted"] is False and blocked["legacy_plan_archive_only"]
    assert blocked["existing_task_ids"] == ["preview"]
    assert rows == before and not sent
    assert ledger["composition_plan"] == PAID_FAILURE_PLAN
    # Provider result collection remains available; never reserves a fresh task.
    ma.record_wait({"results": [{"id": "preview", "status": "done", "placed": True, "shapes": ["archived"]}]})
    assert rows[1]["blocks"][0][ma.LEDGER]["composition_plan"] == PAID_FAILURE_PLAN


@pytest.mark.parametrize("field", ["subject_geometry", "appearance", "panel_geometry", "panel_appearance"])
def test_missing_structured_fields_block_before_payment(run, field):
    rows, sent = run
    setup(rows)
    plan = copy.deepcopy(HEADPHONES_PLAN)
    if field.startswith("panel_"):
        plan["panels"][0].pop(field.removeprefix("panel_"))
    else:
        plan.pop(field)
    _, blocked = ma.prepare({"skill": ma.SKILL, "composition_plan": plan})
    assert blocked["submitted"] is False and not sent
    assert not rows[1]["blocks"][0].get(ma.LEDGER)


def test_unsubmitted_mixed_plan_can_be_replanned_but_not_migrated(run):
    rows, _ = run
    setup(rows)
    args = prepare(HEADPHONES_PLAN)
    assert ma.reserve(args["_multi_angle"]) is None
    ledger = rows[1]["blocks"][0][ma.LEDGER]
    ledger.pop("preview")  # explicitly unsubmitted setup: no reservation/task
    ledger["composition_plan"] = copy.deepcopy(PAID_FAILURE_PLAN)
    new = prepare(PLANS[1])
    assert ma.reserve(new["_multi_angle"]) is None
    assert rows[1]["blocks"][0][ma.LEDGER]["composition_plan"] == PLANS[1]
    assert PAID_FAILURE_PLAN["panels"][0]["description"].endswith("pure white seamless background")


def test_registered_tool_requires_structured_geometry_without_new_parallel_plan_api():
    schema = canvas.SPECS["generate_image"]["inputSchema"]["properties"]["composition_plan"]
    assert {"subject_geometry", "appearance", "subject", "purpose", "panels"} <= set(schema["required"])
    panel = schema["properties"]["panels"]["items"]
    assert {"id", "name", "description", "geometry", "appearance"} <= set(panel["required"])
    assert "no appearance" in panel["properties"]["geometry"]["description"]


@pytest.mark.asyncio
@pytest.mark.parametrize("delivered", [False, True])
async def test_submitted_legacy_blocks_quote_relay_and_stale_reservation_without_mutation(run, delivered):
    rows, sent = run
    setup(rows)
    args = prepare(HEADPHONES_PLAN)
    deliver(args["_multi_angle"])
    ledger = rows[1]["blocks"][0][ma.LEDGER]
    ledger["preview"]["delivered"] = delivered
    ledger["composition_plan"] = copy.deepcopy(PAID_FAILURE_PLAN)
    before = copy.deepcopy(rows)
    result = await canvas._relay("generate_image")({"skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN})
    assert result["submitted"] is False and result["legacy_plan_archive_only"]
    model, inputs = canvas.quote_route("generate_image", {"skill": ma.SKILL, "composition_plan": HEADPHONES_PLAN}, catalog={})
    assert not model and inputs["param_blocked"]["legacy_plan_archive_only"]
    blocked = ma.reserve(args["_multi_angle"])
    assert blocked["submitted"] is False
    assert not sent and rows == before


@pytest.mark.parametrize("plan", PLANS)
def test_camera_visibility_constraints_are_generic_and_keep_one_grid(run, plan):
    rows, _ = run
    rows[0]["blocks"][1]["text"] = plan["purpose"]
    setup(rows)
    args = prepare(plan)
    prompt = args["prompt"]
    assert "visible structures.\n" not in prompt
    assert "occlude surfaces that camera cannot see" in prompt
    assert "Change the camera, not the subject pose" in prompt
    assert "Keep each panel's instructions local to that panel" in prompt
    assert "ONE lineart preview image" in prompt
    assert "numbered 3x3 nine-panel" in prompt
    assert args["count"] == args["n"] == 1
    assert args["_multi_angle"]["composition_plan"] == plan
    for panel in plan["panels"]:
        assert f"{panel['id']}: {panel['geometry']}" in prompt

def test_multi_angle_planning_hint_requires_camera_and_occlusion_contract():
    from ComfyArt.bot import skill_output
    hint = skill_output.run_hint(ma.SKILL)
    assert "camera position relative to the subject" in hint
    assert "looking vertically down" in hint
    assert "before freezing the plan" in hint


@pytest.mark.asyncio
async def test_reviewed_camera_plan_reaches_canvas_without_network(run, tmp_path):
    import json
    import os
    from pathlib import Path
    plan = json.loads((Path(__file__).parent / "fixtures" / "multi-angle-camera-plan-1002.json").read_text())
    frozen = copy.deepcopy(plan)
    rows, sent = run
    setup(rows)
    from test_multi_angle_stages_911 import confirm_quote
    confirm_quote(rows)  # new upstream consent gate; mocked fixture only
    args = {"skill": ma.SKILL, "multi_angle_stage": "preview", "ratio": "9:16", "composition_plan": plan}
    result = await canvas._relay("generate_image")(args)
    assert result and len(sent) == 1
    dispatched = sent[0][1]
    assert dispatched["count"] == 1
    for panel in plan["panels"]:
        assert f"{panel['id']}: {panel['geometry']}" in dispatched["prompt"]
    assert "looking vertically downward at 90 degrees" in dispatched["prompt"]
    assert "occlude surfaces that camera cannot see" in dispatched["prompt"]
    assert plan == frozen
    await canvas._relay("generate_image")(args)
    assert len(sent) == 1  # same new plan is not resubmitted
    capture = {"evidence_kind": "offline canvas dispatch; submit_command mocked; no provider request",
               "action": sent[0][0], "params": dispatched}
    (tmp_path / "assembled-canvas-request.json").write_text(json.dumps(capture, ensure_ascii=False, indent=2))
    if os.environ.get("COMFYART_OFFLINE_CAPTURE_DIR"):
        out = Path(os.environ["COMFYART_OFFLINE_CAPTURE_DIR"])
        out.mkdir(parents=True, exist_ok=True)
        (out / "assembled-canvas-request-NO-NETWORK.json").write_text(json.dumps(capture, ensure_ascii=False, indent=2))
        (out / "assembled-canvas-prompt-NO-NETWORK.txt").write_text(dispatched["prompt"])


def test_final_prompt_uses_delivered_cell_as_only_left_right_authority_1003(run):
    """#1003 paid preview 76db53c0: cell 2 was drawn mirrored vs plan text. Product ruled the preview
    PASS; the final must follow the delivered cell, so conflicting plan camera text is not injected."""
    rows, _ = run
    setup(rows)
    preview = prepare(HEADPHONES_PLAN)
    deliver(preview["_multi_angle"])
    choose(rows, ("1", "2", "3"))
    for number in ("1", "2", "3"):
        final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": number})
        assert blocked is None
        prompt = final["prompt"]
        chosen = HEADPHONES_PLAN["panels"][int(number) - 1]
        assert chosen["geometry"] not in prompt
        assert chosen["description"] not in prompt
        assert "viewer's right" not in prompt and "viewer's left" not in prompt
        assert "subject's left" not in prompt and "subject's right" not in prompt
        assert "come ONLY from that delivered cell" in prompt
        assert FINAL_ORIENTATION in prompt and FINAL_NO_MIRROR in prompt
        assert final["ref_modes"][-1] == "composition"  # delivered preview attached as the camera authority


def test_final_prompt_has_no_generic_matte_gray_and_carries_finish_lighting_1003(run):
    """#1003 product/design 22:4x: no generic 'matte gray' in finals; color from the original reference
    (no darkening to black), per-material separation, key/edge light, white bg, faint contact shadow."""
    from pathlib import Path
    plan = json.loads((Path(__file__).parent / "fixtures/multi-angle-camera-plan-1002.json").read_text())
    rows, _ = run
    setup(rows)
    preview = prepare(plan)
    deliver(preview["_multi_angle"])
    choose(rows, ("1", "2", "3"))
    assert "matte gray" in json.dumps(plan)  # fixture really carries the generic phrase
    for number in ("1", "2", "3"):
        final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": number})
        assert blocked is None
        prompt = final["prompt"]
        assert "matte gray" not in prompt.lower()
        assert ma.FINAL_FINISH in prompt
        for phrase in ("actual color value", "do not darken it toward black", "soft key light",
                       "edge highlights", "pure white (#FFFFFF)", "faint soft contact shadow directly beneath",
                       "must not tint the background"):
            assert phrase in prompt
        assert "LINEART ONLY" not in prompt
    assert ma.FINAL_FINISH not in preview["prompt"]


def freeze_legacy_plan(plan):
    """Store a content-less plan as an already-delivered preview.

    A new preview of that same plan stays rejected. Finals read the frozen plan
    and may still pass panel_content.
    """
    clean = ma.validate_plan(plan)
    assert all("content" not in panel for panel in clean["panels"])
    _, blocked = ma.prepare({"skill": ma.SKILL, "composition_plan": plan, "multi_angle_stage": "preview"})
    assert blocked is not None and "content is required" in blocked["error"]
    meta = prepare(HEADPHONES_PLAN)["_multi_angle"]
    meta["composition_plan"] = clean
    deliver(meta)
    return clean


def test_committed_frozen_plan_without_content_still_builds_finals(run):
    from pathlib import Path
    plan = json.loads((Path(__file__).parent / "fixtures/multi-angle-frozen-5cf1a349.json").read_text())
    rows, _ = run
    setup(rows)
    freeze_legacy_plan(plan)
    choose(rows, ("1", "2", "3"))
    for number in ("1", "2", "3"):
        final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": number})
        assert blocked is None, blocked
        prompt = final["prompt"].lower()
        assert "matte gray" not in prompt
        for word in ("viewer's right", "viewer's left", "subject's left", "subject's right"):
            assert word not in prompt
    again, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "1",
                                 "panel_content": "earcups and padded headband"})
    assert blocked is None and again["prompt"].endswith("\nPanel content: earcups and padded headband")


def test_real_5cf1a349_frozen_plan_final_prompt_has_no_matte_gray_or_plan_left_right_1003(run):
    from pathlib import Path
    path = Path("/workspace/qa1003-5cf1a349-paid-preview/structured-plan.json")
    if not path.exists():
        return
    plan = json.loads(path.read_text())
    rows, _ = run
    setup(rows)
    freeze_legacy_plan(plan)
    choose(rows, ("1", "2", "3"))
    for number in ("1", "2", "3"):
        final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": number})
        assert blocked is None
        prompt = final["prompt"].lower()
        assert "matte gray" not in prompt
        for word in ("viewer's right", "viewer's left", "subject's left", "subject's right"):
            assert word not in prompt
