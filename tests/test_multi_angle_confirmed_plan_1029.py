"""Confirmed multi-angle plan: the default send queries its own finals.

The 4c0aabca on-site stop was gen_calls 10 against gen_cap 6 after the nine
submits, before the next model turn could wait. These counts are from this
process. They are not the earlier JSON replay and not that on-site stop.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api import multi_angle as ma
from test_multi_angle_quote_snapshot_1029 import PREVIEW, _send

PANELS = [str(i) for i in range(1, 10)]


def _ledger(cid):
    token = BOT_CHAT_ID.set(cid)
    try:
        return ma._root(cid)[1][ma.LEDGER]
    finally:
        BOT_CHAT_ID.reset(token)


def _fields(row):
    return (row["paid_calls"], row["total_calls"], row["gen_calls"], row["gen_cap"],
            row["planned_images"], row["plan_items"])


def _generates(sent):
    return [args for action, args in sent if action == "generate_image"]


@pytest.mark.asyncio
async def test_default_chain_queries_nine_finals_inside_send(monkeypatch, tmp_path):
    out = await _send(monkeypatch, finals=PANELS, wait_finals=True)
    assert not (getattr(out["result"], "error", None) or ""), out["result"]
    names = [name for name, _text in out["tools"]]
    assert names.count("generate_image") == 10
    assert names.count("wait_generation") == 2
    assert names.index("wait_generation", names.index("generate_image") + 1) > names.index("generate_image")
    assert len(_generates(out["sent"])) == 10
    ledger = _ledger(out["cid"])
    plan = ledger["confirmed_plan"]
    assert plan["final_ids"] == PANELS
    assert plan["generates"] == 10
    assert plan["preview"] == 1
    for panel in PANELS:
        entry = ledger["final:" + panel]
        assert entry["status"] == "submitted" or entry.get("delivered") is True
        assert entry.get("delivered") is True
        assert entry.get("generation_succeeded") is True
        assert entry["status"] != "failed"
    points = {row["point"]: row for row in plan["counts"]}
    assert _fields(points["before_confirm"])[:4] == (1, 4, 1, 6)
    assert points["before_confirm"]["planned_images"] == 0
    assert points["before_confirm"]["plan_items"] == []
    assert _fields(points["after_confirm"])[:4] == (1, 4, 1, 10)
    assert _fields(points["before_dispatch"])[:4] == (1, 4, 1, 10)
    assert _fields(points["after_dispatch"])[:4] == (10, 13, 10, 10)
    assert _fields(points["after_query"])[2:4] == (10, 10)
    assert points["after_query"]["gen_calls"] == points["after_dispatch"]["gen_calls"]
    artifact = {
        "source": "in-process candidate; not the JSON replay and not the 4c0aabca on-site stop",
        "prior_json_replay": {"paid_calls": 10, "total_calls": 13, "gen_calls": 10, "gen_cap": 6,
                              "planned_images": 0, "plan_items": []},
        "qa_onsite_4c0aabca": {"rounds": 5, "fields": [10, 13, 10, 6, 0, []],
                               "note": "send ended at step 5 before the script's next-turn wait"},
        "counts": plan["counts"],
    }
    text = json.dumps(artifact, ensure_ascii=False, indent=2)
    path = tmp_path / "confirmed-plan-counts.json"
    path.write_text(text, encoding="utf-8")
    assert "after_query" in path.read_text(encoding="utf-8")
    from pathlib import Path
    artifact_dir = Path("/opt/cursor/artifacts")
    if artifact_dir.is_dir():
        (artifact_dir / "confirmed-plan-counts.json").write_text(text, encoding="utf-8")


@pytest.mark.asyncio
async def test_resume_queries_the_same_holders_without_new_generates(monkeypatch):
    out = await _send(monkeypatch, finals=PANELS, wait_finals=True, drop_before_wait=True)
    dropped = out["dropped"]
    assert dropped is not None and dropped.error
    assert "卡住" not in dropped.error
    assert "budget" not in (dropped.run or {}).get("stop", {}).get("sub", "")
    assert not (out["result"].error or ""), out["result"].error
    assert len(_generates(out["sent"])) == 10
    ledger = _ledger(out["cid"])
    assert all(ledger["final:" + panel].get("delivered") is True for panel in PANELS)
    points = {row["point"]: row for row in ledger["confirmed_plan"]["counts"]}
    assert _fields(points["after_dispatch"])[:4] == (10, 13, 10, 10)
    assert points["after_resume"]["gen_calls"] == 10
    assert points["after_resume"]["gen_cap"] == 10
    assert points["after_resume"]["planned_images"] == 0
    assert points["after_resume"]["plan_items"] == []
    from pathlib import Path
    artifact_dir = Path("/opt/cursor/artifacts")
    if artifact_dir.is_dir():
        (artifact_dir / "confirmed-plan-resume-counts.json").write_text(json.dumps({
            "source": "in-process resume after the send stopped on a transport drop, then continued",
            "note": "The 10/13/10/6/0/[] figures are the 4c0aabca on-site stop and the earlier JSON replay, not this resume.",
            "counts": ledger["confirmed_plan"]["counts"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    before = len(_generates(out["sent"]))
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        replay = await canvas._relay("generate_image")({
            "composition_plan": ledger["composition_plan"], "skill": ma.SKILL,
            "refs": ["r"], "multi_angle_stage": "final", "composition_id": "1"})
    finally:
        BOT_CHAT_ID.reset(token)
    assert replay.get("multi_angle_replay") is True
    assert len(_generates(out["sent"])) == before


@pytest.mark.asyncio
async def test_same_confirmation_does_not_add_k(monkeypatch):
    out = await _send(monkeypatch, finals=["1"], wait_finals=True)
    ledger = _ledger(out["cid"])
    plan = ledger["confirmed_plan"]
    again = ma.register_confirmed_finals(
        out["cid"], plan["confirmation_id"], ["1", "2", "3"], 99, 9, {"1": 1, "2": 1, "3": 1})
    repeated = ma.register_confirmed_finals(
        out["cid"], plan["confirmation_id"] + "-same-panels", ["1"], 99, 1, {"1": 1})
    assert again["generates"] == plan["generates"] == 2
    assert repeated["final_ids"] == ["1"]
    assert repeated["generates"] == 2
    added = ma.register_confirmed_finals(
        out["cid"], plan["confirmation_id"] + "-new", ["2"], 0.1, 1, {"2": 0.1})
    assert added["final_ids"] == ["1", "2"]
    assert added["generates"] == 3
    added_again = ma.register_confirmed_finals(
        out["cid"], plan["confirmation_id"] + "-new", ["2", "3"], 0.2, 2, {"2": 0.1, "3": 0.1})
    assert added_again["generates"] == 3
    assert added_again["final_ids"] == ["1", "2"]


@pytest.mark.asyncio
async def test_cancel_second_card_does_not_authorize_nine(monkeypatch):
    out = await _send(monkeypatch, finals=PANELS, second_choice="cancel")
    assert len(_generates(out["sent"])) == 1
    ledger = _ledger(out["cid"])
    assert "confirmed_plan" not in ledger
    assert "final:1" not in ledger


@pytest.mark.asyncio
async def test_duplicate_and_unconfirmed_panel_are_not_submitted(monkeypatch):
    out = await _send(monkeypatch, finals=["1"], duplicate=True, selected=["1", "2"], wait_finals=True)
    assert len(_generates(out["sent"])) == 2, out["tools"]
    transcript = "\n".join(getattr(event, "text", "") or "" for event in out["events"])
    assert "Duplicate composition" in transcript
    before = len(_generates(out["sent"]))
    ledger = _ledger(out["cid"])
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        blocked = await canvas._relay("generate_image")({
            "composition_plan": ledger["composition_plan"], "skill": ma.SKILL,
            "refs": ["r"], "multi_angle_stage": "final", "composition_id": "2"})
    finally:
        BOT_CHAT_ID.reset(token)
    assert blocked["submitted"] is False
    assert "outside the confirmed plan" in blocked["error"]
    assert len(_generates(out["sent"])) == before


@pytest.mark.asyncio
async def test_amount_cap_blocks_a_resend_without_a_page_call(monkeypatch):
    out = await _send(monkeypatch, finals=["1"], wait_finals=True)
    current = _ledger(out["cid"])
    edited = dict(current)
    edited.pop("final:1", None)
    plan = dict(current["confirmed_plan"])
    plan["amount"] = 0.0
    plan["reserved_amount"] = 0.0
    plan["reserved_generates"] = 1
    slots = dict(plan.get("slots") or {})
    slots["final:1"] = {"status": "authorized"}
    plan["slots"] = slots
    edited["confirmed_plan"] = plan
    ma._save(out["cid"], edited, current)
    before = len(_generates(out["sent"]))
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        blocked = await canvas._relay("generate_image")(dict(PREVIEW) | {
            "multi_angle_stage": "final", "composition_id": "1"})
    finally:
        BOT_CHAT_ID.reset(token)
    assert blocked["submitted"] is False
    assert "amount" in blocked["error"].lower() or "金额" in blocked["error"]
    assert len(_generates(out["sent"])) == before


@pytest.mark.asyncio
async def test_timeout_stays_unknown_and_is_not_resent(monkeypatch):
    out = await _send(monkeypatch, finals=["1"], timeout_panel="1")
    ledger = _ledger(out["cid"])
    assert ledger["final:1"]["status"] == "unknown"
    assert ledger["final:1"]["result"]["multi_angle_hold"] is True
    attempts = len(_generates(out["sent"]))
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        again = await canvas._relay("generate_image")({
            "composition_plan": ledger["composition_plan"], "skill": ma.SKILL,
            "refs": ["r"], "multi_angle_stage": "final", "composition_id": "1"})
    finally:
        BOT_CHAT_ID.reset(token)
    assert again.get("multi_angle_replay") is True
    assert again.get("status") == "unknown"
    assert len(_generates(out["sent"])) == attempts


@pytest.mark.asyncio
async def test_failed_final_is_not_delivered_and_retry_does_not_resend(monkeypatch):
    out = await _send(monkeypatch, finals=PANELS, wait_finals=True, fail_panel="6")
    ledger = _ledger(out["cid"])
    failed = ledger["final:6"]
    assert failed["status"] == "failed"
    assert failed.get("delivered") is False
    assert failed.get("generation_succeeded") is False
    for panel in PANELS:
        if panel == "6":
            continue
        assert ledger["final:" + panel].get("delivered") is True
    before = len(_generates(out["sent"]))
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        replay = await canvas._relay("generate_image")({
            "composition_plan": ledger["composition_plan"], "skill": ma.SKILL,
            "refs": ["r"], "multi_angle_stage": "final", "composition_id": "6"})
    finally:
        BOT_CHAT_ID.reset(token)
    assert replay.get("multi_angle_replay") is True
    assert replay.get("generation_succeeded") is False
    assert replay.get("delivered") is False
    assert len(_generates(out["sent"])) == before
