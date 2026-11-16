"""Subject planning contract: no paid API, no browser, no global view fallback."""
import copy

import pytest

from ComfyArt.api import multi_angle as ma
from ComfyArt.api import bot_asks
from ComfyArt.api.mcp_tools import canvas
from multi_angle_plan_fixture import HEADPHONES_PLAN
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
