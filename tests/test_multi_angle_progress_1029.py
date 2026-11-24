"""Authoritative multi-angle progress block. Not a budget or confirmation change."""
from __future__ import annotations

import os
import socket

os.environ["COMFYART_SKIP_KEY_CHECK"] = "1"
_LOCAL = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}
_connect = socket.socket.connect


def _guard(self, addr):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        host = addr[0] if isinstance(addr, tuple) else addr
        if host not in _LOCAL:
            raise OSError(f"non-loopback refused: {host}")
    return _connect(self, addr)


socket.socket.connect = _guard

import json
import subprocess
from pathlib import Path

import pytest

from ComfyArt.api import chat_store, multi_angle as ma
from ComfyArt.api.bot_turns import ACTIVE_TURNS

ROOT = Path(__file__).resolve().parent.parent
PANELS = [str(i) for i in range(1, 10)]


def _plan(**slots):
    return {
        "confirmation_id": "confirm-1",
        "preview": 1,
        "final_ids": PANELS,
        "generates": 10,
        "amount": 1.0,
        "units": 9,
        "slots": slots,
    }


def _ledger():
    slots = {"preview": {"status": "delivered", "delivered": True}}
    slots.update({f"final:{panel}": {"status": "authorized"} for panel in PANELS})
    return {
        "preview": {"status": "delivered", "delivered": True, "generation_succeeded": True, "result": {"ids": ["preview-holder"]}},
        "confirmed_plan": _plan(**slots),
    }


def _install(ledger):
    chat = chat_store.create_chat(user="default", project="angle-progress-1029", provider="local-llm")
    message = chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=[{
        "type": "ask",
        "ask_id": "setup-1",
        "status": "answered",
        "questions": [{"id": ma.SOURCE, "prompt": "source"}, {"id": ma.ASPECT, "prompt": "aspect"}],
        "answers": {ma.SOURCE: {"selected": ["single_front"]}, ma.ASPECT: {"selected": ["1:1"]}},
        ma.LEDGER: ledger,
    }])
    return chat, message


def _block(chat_id):
    found = []
    for message in chat_store.list_messages(chat_id):
        for block in message["blocks"]:
            if block.get("type") == "multi_angle_progress":
                found.append(block)
    assert len(found) == 1
    return found[0]


def _slot(block, slot_id):
    return next(slot for slot in block["slots"] if slot["id"] == slot_id)


def test_confirmed_block_is_preview_plus_zero_of_nine():
    chat, _message = _install(_ledger())
    view = ma.sync_progress(chat["id"], live=False)
    assert view["phase"] == "confirmed"
    assert view["preview"] == 1
    assert view["final_done"] == 0
    assert view["final_total"] == 9
    assert view["batch_retry"] is False
    assert "planned_images" not in view and "gen_cap" not in view
    stored = _block(chat["id"])
    assert stored == view
    again = ma.sync_progress(chat["id"], live=False)
    assert again == stored
    assert len([b for m in chat_store.list_messages(chat["id"]) for b in m["blocks"] if b.get("type") == "multi_angle_progress"]) == 1


def test_record_wait_refreshes_delivered_pending_and_failed():
    ledger = _ledger()
    plan = ledger["confirmed_plan"]
    for panel, status in (("1", "submitted"), ("2", "submitted"), ("4", "reserved"), ("6", "failed")):
        plan["slots"][f"final:{panel}"] = {"status": status, "delivered": False}
    ledger["final:1"] = {"status": "submitted", "result": {"ids": ["h1"]}}
    ledger["final:2"] = {"status": "submitted", "result": {"ids": ["h2"]}}
    ledger["final:4"] = {"status": "reserved"}
    ledger["final:6"] = {"status": "failed", "generation_succeeded": False, "delivered": False,
                         "result": {"ids": ["h6"], "generation_succeeded": False, "delivered": False}}
    chat, _message = _install(ledger)
    ma.record_wait({"results": [{
        "id": "h1", "status": "done", "placed": True, "generation_succeeded": True,
        "delivered": 1, "shapes": ["shape-1"], "urls": ["mock://final-1"],
    }]}, chat["id"])
    block = _block(chat["id"])
    assert _slot(block, "final:1")["state"] == "delivered"
    assert _slot(block, "final:2")["state"] == "pending_query"
    assert _slot(block, "final:2")["retry"] is False
    assert _slot(block, "final:4")["state"] == "pending_query"
    assert _slot(block, "final:6")["state"] == "failed"
    assert _slot(block, "final:6")["retry"] is True
    assert block["batch_retry"] is False
    assert block["final_done"] == 1
    assert block["final_total"] == 9
    assert all(slot["retry"] is False or slot["id"] == "final:6" for slot in block["slots"])


def test_live_generating_becomes_pending_query_on_resume():
    ledger = _ledger()
    plan = ledger["confirmed_plan"]
    plan["slots"]["final:1"] = {"status": "delivered", "delivered": True}
    plan["slots"]["final:4"] = {"status": "reserved"}
    ledger["final:1"] = {"status": "delivered", "delivered": True, "generation_succeeded": True,
                         "result": {"ids": ["h1"], "generation_succeeded": True}}
    ledger["final:4"] = {"status": "reserved"}
    chat, message = _install(ledger)
    state_blocks = chat_store.list_messages(chat["id"])[0]["blocks"]
    ACTIVE_TURNS[chat["id"]] = type("Turn", (), {"message_id": message["id"], "blocks": state_blocks})()
    try:
        live = ma.sync_progress(chat["id"], live=True)
        assert _slot(live, "final:4")["state"] == "generating"
        assert _slot(live, "final:1")["state"] == "delivered"
    finally:
        ACTIVE_TURNS.pop(chat["id"], None)
    resumed = ma.sync_progress(chat["id"], live=False)
    assert _slot(resumed, "final:4")["state"] == "pending_query"
    assert _slot(resumed, "final:1")["state"] == "delivered"
    assert resumed["batch_retry"] is False
    assert _slot(resumed, "final:4")["retry"] is False


@pytest.mark.asyncio
async def test_reopen_chat_rebuilds_the_block_from_the_ledger(bot_client):
    ledger = _ledger()
    plan = ledger["confirmed_plan"]
    plan["slots"]["final:2"] = {"status": "submitted"}
    plan["slots"]["final:6"] = {"status": "failed", "delivered": False}
    ledger["final:2"] = {"status": "submitted", "result": {"ids": ["h2"]}}
    ledger["final:6"] = {"status": "failed", "generation_succeeded": False, "delivered": False,
                         "result": {"ids": ["h6"], "generation_succeeded": False}}
    chat, message = _install(ledger)
    first = await (await bot_client.get(f"/comfyart/bot/chats/{chat['id']}")).json()
    block = next(b for m in first["messages"] for b in m["blocks"] if b.get("type") == "multi_angle_progress")
    assert block["phase"] == "partial"
    assert _slot(block, "final:2")["state"] == "pending_query"
    assert _slot(block, "final:6")["state"] == "failed"
    assert _slot(block, "final:6")["retry"] is True
    assert block["final_total"] == 9
    saved = chat_store.list_messages(chat["id"])[0]
    ask = next(b for b in saved["blocks"] if b.get("type") == "ask")
    ask[ma.LEDGER]["final:2"]["status"] = "delivered"
    ask[ma.LEDGER]["final:2"]["delivered"] = True
    ask[ma.LEDGER]["final:2"]["generation_succeeded"] = True
    ask[ma.LEDGER]["confirmed_plan"]["slots"]["final:2"] = {"status": "delivered", "delivered": True}
    chat_store.update_message(chat["id"], message["id"], blocks=saved["blocks"])
    second = await (await bot_client.get(f"/comfyart/bot/chats/{chat['id']}")).json()
    again = [b for m in second["messages"] for b in m["blocks"] if b.get("type") == "multi_angle_progress"]
    assert len(again) == 1
    assert _slot(again[0], "final:2")["state"] == "delivered"
    assert _slot(again[0], "final:6")["state"] == "failed"
    assert again[0]["final_done"] == 1


def test_card_renders_four_states_in_both_locales():
    rolldown = ROOT / "node_modules" / ".bin" / "rolldown"
    if not rolldown.exists() or not shutil_which("node"):
        pytest.skip("needs node + npm install")
    out = ROOT / "tests" / "js" / ".angle-progress-1029.mjs"
    try:
        subprocess.run([str(rolldown), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                       capture_output=True, text=True, env={**os.environ, "OUT": str(out), "ENTRY": "angle_progress_1029.ts"})
        ran = subprocess.run(["node", str(out)], cwd=ROOT, check=True, capture_output=True, text=True)
    finally:
        out.unlink(missing_ok=True)
    payload = json.loads(ran.stdout)
    assert payload["ok"] is True
    assert payload["cards"] == 8


def shutil_which(name):
    import shutil
    return shutil.which(name)
