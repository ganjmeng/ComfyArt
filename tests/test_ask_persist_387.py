"""#387: pending ask persistence across process restart / page refresh.

Mocks only ($0). AC1–6 + must-red mutations. No paid calls.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from ComfyArt.api import bot_asks, chat_store
from ComfyArt.api.ask_store import JsonAskStore, get_store, set_store


SPEC_2Q = {
    "questions": [
        {
            "id": "brand",
            "prompt": "品牌名？",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "defaults": ["a"],
            "min_selections": 1,
            "max_selections": 1,
        },
        {
            "id": "tone",
            "prompt": "语气？",
            "options": [{"id": "warm", "label": "暖"}, {"id": "cool", "label": "冷"}],
            "min_selections": 1,
            "max_selections": 1,
        },
    ],
    "allow_skip": True,
}


def _spec() -> dict:
    return bot_asks.validate_spec(SPEC_2Q)


def _simulate_restart() -> int:
    """Clear in-memory PENDING and rehydrate from the AskStore (process restart)."""
    bot_asks.PENDING.clear()
    bot_asks.ANSWERED_RUN_APPROVALS.clear()
    return bot_asks.reload_pending_from_store()


async def test_ac1_list_survives_restart(bot_client, fake_provider):
    chat = await (await bot_client.post("/comfyart/bot/chats",
                                        json={"project": "p", "provider": "fake-test"})).json()
    chat = chat["chat"]
    msg = chat_store.create_message(chat_id=chat["id"], role="assistant",
                                    blocks=[{"type": "text", "text": "…"}], status="streaming")
    spec = _spec()
    ask = bot_asks.create_ask(chat["id"], msg["id"], spec)
    assert get_store().list_all() and get_store().list_all()[0]["id"] == ask.id

    n = _simulate_restart()
    assert n == 1
    assert ask.id in bot_asks.PENDING
    assert bot_asks.PENDING[ask.id].abandoned is True

    resp = await bot_client.get(f"/comfyart/bot/chats/{chat['id']}/asks")
    assert resp.status == 200
    asks = (await resp.json())["asks"]
    assert len(asks) == 1
    got = asks[0]
    assert got["ask_id"] == ask.id
    assert got["status"] == "pending"
    assert got["prompt"] == spec["prompt"]
    assert got["questions"][0]["defaults"] == ["a"]
    assert got["questions"][0]["min_selections"] == 1
    assert got["questions"][1]["max_selections"] == 1
    assert len(got["questions"][0]["options"]) == 2


async def test_ac2_answer_after_restart(bot_client, fake_provider):
    chat = await (await bot_client.post("/comfyart/bot/chats",
                                        json={"project": "p", "provider": "fake-test"})).json()
    chat = chat["chat"]
    spec = _spec()
    msg = chat_store.create_message(
        chat_id=chat["id"], role="assistant",
        blocks=[{"type": "ask", "ask_id": "will-replace", "status": "pending", **spec}],
        status="streaming",
    )
    ask = bot_asks.create_ask(chat["id"], msg["id"], spec)
    chat_store.update_message(chat["id"], msg["id"], blocks=[
        {"type": "ask", "ask_id": ask.id, "status": "pending", **spec},
    ])

    _simulate_restart()
    assert ask.id in bot_asks.PENDING

    answers = {
        "brand": {"selected": ["a"]},
        "tone": {"selected": ["warm"]},
    }
    ok = await bot_client.post(
        f"/comfyart/bot/chats/{chat['id']}/asks/{ask.id}/answer",
        json={"selected": [], "other_text": "", "answers": answers},
    )
    assert ok.status == 202, await ok.text()
    assert ask.id not in bot_asks.PENDING
    assert get_store().list_all() == []

    msgs = chat_store.list_messages(chat["id"])
    block = next(b for b in msgs[0]["blocks"] if b.get("type") == "ask")
    assert block["status"] == "answered"
    assert block["answers"]["brand"]["selected"] == ["a"]


async def test_ac3_answered_not_listed(bot_client, fake_provider):
    chat = await (await bot_client.post("/comfyart/bot/chats",
                                        json={"project": "p", "provider": "fake-test"})).json()
    chat = chat["chat"]
    ask = bot_asks.create_ask(chat["id"], "m1", _spec())
    listed = (await (await bot_client.get(f"/comfyart/bot/chats/{chat['id']}/asks")).json())["asks"]
    assert len(listed) == 1
    bot_asks.resolve_ask(ask.id, "answered", selected=["a"], answers={
        "brand": {"selected": ["a"]}, "tone": {"selected": ["warm"]},
    })
    listed2 = (await (await bot_client.get(f"/comfyart/bot/chats/{chat['id']}/asks")).json())["asks"]
    assert listed2 == []
    assert get_store().list_all() == []


async def test_ac4_abandon_then_restart_empty(bot_client, fake_provider):
    chat = await (await bot_client.post("/comfyart/bot/chats",
                                        json={"project": "p", "provider": "fake-test"})).json()
    chat = chat["chat"]
    ask = bot_asks.create_ask(chat["id"], "m1", _spec())
    bot_asks.abandon_ask(ask.id)
    assert ask.id in bot_asks.PENDING
    assert get_store().list_all() == []
    n = _simulate_restart()
    assert n == 0
    assert bot_asks.PENDING == {}


async def test_ac4_stop_cancel_then_restart_empty(bot_client, fake_provider):
    chat = await (await bot_client.post("/comfyart/bot/chats",
                                        json={"project": "p", "provider": "fake-test"})).json()
    chat = chat["chat"]
    bot_asks.create_ask(chat["id"], "m1", _spec())
    cancelled = bot_asks.cancel_chat_asks(chat["id"])
    assert len(cancelled) == 1
    assert get_store().list_all() == []
    assert _simulate_restart() == 0


async def test_ac5_stale_run_approval_store_one(bot_client, fake_provider):
    chat = await (await bot_client.post("/comfyart/bot/chats",
                                        json={"project": "p", "provider": "fake-test"})).json()
    chat = chat["chat"]
    spec1 = {"kind": "run_approval", "prompt": "run A?", "options": [
        {"id": "run", "label": "Run"}, {"id": "skip", "label": "Skip"},
    ], "min_selections": 1, "max_selections": 1, "allow_other": False, "allow_skip": False}
    spec2 = {**spec1, "prompt": "run B?"}
    a1 = bot_asks.create_ask(chat["id"], "m1", spec1)
    a2 = bot_asks.create_ask(chat["id"], "m2", spec2)
    assert a1.id not in bot_asks.PENDING
    assert a2.id in bot_asks.PENDING
    store = get_store().list_all()
    assert len(store) == 1
    assert store[0]["id"] == a2.id


def test_ac6_corrupt_store_starts_empty(tmp_path, caplog):
    path = tmp_path / "pending-asks.json"
    path.write_text("{not json", encoding="utf-8")
    store = JsonAskStore(str(path))
    with caplog.at_level(logging.WARNING, logger="comfyart.ask_store"):
        assert store.list_all() == []
    assert any("unreadable" in r.message or "corrupt" in r.message for r in caplog.records)

    path.write_text(json.dumps({"asks": "nope"}), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="comfyart.ask_store"):
        assert store.list_all() == []


def test_ownership_defaults_stamped(tmp_path):
    store = JsonAskStore(str(tmp_path / "pending-asks.json"))
    set_store(store)
    try:
        ask = bot_asks.create_ask("c1", "m1", _spec())
        rec = store.list_all()[0]
        assert rec["owner_id"] == "local"
        assert rec["workspace_id"] == "local"
        assert rec["project_id"] == "local"
        assert rec["id"] == ask.id
    finally:
        bot_asks.PENDING.clear()
        set_store(None)


def test_mutation_memory_only_no_disk_reds_ac1(tmp_path, monkeypatch):
    store = JsonAskStore(str(tmp_path / "pending-asks.json"))
    set_store(store)
    try:
        monkeypatch.setattr(bot_asks, "_store_put", lambda ask: None)
        ask = bot_asks.PendingAsk("c", "m", _spec())
        bot_asks.PENDING[ask.id] = ask
        assert get_store().list_all() == []
        bot_asks.PENDING.clear()
        assert bot_asks.reload_pending_from_store() == 0
    finally:
        set_store(None)
        bot_asks.PENDING.clear()


def test_mutation_resolve_keeps_disk_reds_ac3(tmp_path, monkeypatch):
    store = JsonAskStore(str(tmp_path / "pending-asks.json"))
    set_store(store)
    try:
        ask = bot_asks.create_ask("c", "m", _spec())
        monkeypatch.setattr(bot_asks, "_store_delete", lambda ask_id: None)
        bot_asks.resolve_ask(ask.id, "answered", selected=["a"])
        assert ask.id not in bot_asks.PENDING
        assert len(store.list_all()) == 1
        assert bot_asks.reload_pending_from_store() == 1
    finally:
        set_store(None)
        bot_asks.PENDING.clear()


def test_mutation_stale_memory_only_reds_ac5(tmp_path, monkeypatch):
    store = JsonAskStore(str(tmp_path / "pending-asks.json"))
    set_store(store)
    try:
        spec = {"kind": "run_approval", "prompt": "run?", "options": [
            {"id": "run", "label": "Run"}, {"id": "skip", "label": "Skip"},
        ], "min_selections": 1, "max_selections": 1, "allow_other": False, "allow_skip": False}
        a1 = bot_asks.create_ask("c", "m1", spec)
        monkeypatch.setattr(bot_asks, "_store_delete", lambda ask_id: None)
        bot_asks.resolve_ask(a1.id, "cancelled")
        monkeypatch.undo()
        a2 = bot_asks.create_ask("c", "m2", {**spec, "prompt": "run2?"})
        ids = {r["id"] for r in store.list_all()}
        assert a1.id in ids and a2.id in ids and len(ids) == 2
    finally:
        set_store(None)
        bot_asks.PENDING.clear()


def test_no_reference_brand_in_tip_files():
    """Tip source must not name the competitor brand (issue house rule)."""
    root = Path(__file__).resolve().parents[1]
    needle = "lov" + "art"  # split so this test file itself is not a hit
    for rel in ("api/ask_store.py", "api/bot_asks.py", "src/bot.ts"):
        text = (root / rel).read_text(encoding="utf-8").lower()
        assert needle not in text, rel
