"""Brand quote cards expire on their own 10-minute clock and bind the real execution."""
from __future__ import annotations

import os
import threading
import time

import pytest

from ComfyArt.api import bot_asks, brand_identity as brand, wavespeed
from ComfyArt.api.bot_turns import ACTIVE_TURNS
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest


class _Turn:
    owner_id = "local"
    project_id = "proj-1"
    chat_id = "c"


def _steps(prompt: str = "logo_a", **over):
    args = {
        "skill": brand.SKILL,
        "brand_slot": "logo_a",
        "width": 2048,
        "height": 2048,
        "count": 1,
        "prompt": prompt,
    }
    args.update(over)
    return [{"tool": "generate_image", "arguments": args}]


def _three(prompt_for=lambda slot: slot):
    steps = []
    for slot in ("logo_a", "logo_b", "logo_c"):
        steps.append({
            "tool": "generate_image",
            "arguments": {
                "skill": brand.SKILL,
                "brand_slot": slot,
                "width": 2048,
                "height": 2048,
                "count": 1,
                "prompt": prompt_for(slot),
            },
        })
    return steps


def test_isolated_probe_stays_on_the_loopback_stand_in():
    if os.environ.get("BRAND_CONFIRM_ISOLATED") != "1":
        pytest.skip("network guard is installed by tests/run_brand_confirm_isolated.py")
    from tests.brand_confirm_guard import PROBE_URLS, REAL_CONNECTS

    class SyncThread:
        def __init__(self, target=None, name=None, daemon=None, args=(), kwargs=None):
            self._target = target
            self._args = args
            self._kwargs = kwargs or {}

        def start(self):
            if self._target:
                self._target(*self._args, **self._kwargs)

    before = len(PROBE_URLS)
    connects = len(REAL_CONNECTS)
    saved = threading.Thread
    try:
        threading.Thread = SyncThread
        wavespeed.check_key_at_startup()
    finally:
        threading.Thread = saved
    new = PROBE_URLS[before:]
    assert new == ["http://127.0.0.1:9/api/v3/balance"]
    assert REAL_CONNECTS[connects:] == []


def test_confirm_ttl_is_ten_minutes_and_not_the_quote_cache():
    assert brand.BRAND_CONFIRM_TTL_S == 600.0
    assert wavespeed.QUOTE_TTL == 300.0
    assert brand.BRAND_CONFIRM_TTL_S != wavespeed.QUOTE_TTL


def test_width_normalizes_without_a_new_grant_and_prompt_does_not(monkeypatch):
    brand.reset_for_tests()
    token = BOT_CHAT_ID.set("c")
    try:
        clock = {"t": 1_700_000_000.0}
        monkeypatch.setattr(brand, "_clock", lambda: clock["t"])
        wide = _steps("same prompt")
        narrow = _steps("same prompt", width=1024, height=1024, edit_model="other-model")
        assert brand.stage_fingerprint(wide) != brand.stage_fingerprint(narrow)
        spec = brand.stamp_confirm_spec(
            {"prompt": "确认", "kind": "plan_quote", "options": [{"id": "start"}, {"id": "cancel"}]},
            wide, _Turn(), amount=0.12, lang="zh",
        )
        assert spec["size_locked"] is True
        assert spec["expires_at"] == clock["t"] + 600.0
        assert "尺寸固定，不可修改" in spec["prompt"]
        assert [opt["id"] for opt in spec["options"]] == ["start", "cancel"]
        grant = brand.commit_confirmed_grant(wide, spec, _Turn(), amount=0.12)
        assert grant["expires_at"] == spec["expires_at"]
        assert grant["currency"] == "USD"
        assert grant["user"] == "local" and grant["project"] == "proj-1" and grant["chat"] == "c"
        assert brand.grant_still_authorizes(narrow, _Turn(), now=clock["t"] + 599.0)
        changed = _steps("a different prompt", base="http://127.0.0.1/other.png")
        assert not brand.grant_still_authorizes(changed, _Turn(), now=clock["t"] + 1)
        assert brand.submit_block_reason(changed[0]["arguments"], _Turn(), now=clock["t"] + 1) == "mismatch"
        again = brand.commit_confirmed_grant(wide, spec, _Turn(), amount=0.12)
        assert again["expires_at"] == grant["expires_at"]
        assert brand.grant_still_authorizes(narrow, _Turn(), now=clock["t"] + 600.0) is False
        assert brand.submit_block_reason(wide[0]["arguments"], _Turn(), now=clock["t"] + 600.0) == "expired"
    finally:
        BOT_CHAT_ID.reset(token)


def test_partial_requote_keeps_the_user_text_and_the_submitted_slot(monkeypatch):
    brand.reset_for_tests()
    token = BOT_CHAT_ID.set("c")
    try:
        clock = {"t": 50.0}
        monkeypatch.setattr(brand, "_clock", lambda: clock["t"])
        steps = _three(lambda slot: f"user text {slot}")
        spec = brand.stamp_confirm_spec({"prompt": "p", "kind": "plan_quote"}, steps, _Turn(), amount=0.09, lang="zh")
        brand.commit_confirmed_grant(steps, spec, _Turn(), amount=0.09)
        brand.remember_stage_plan(steps, fresh=True)
        brand.note_brand_submitted(steps[0]["arguments"])
        open_steps = brand.unsubmitted_steps(steps)
        assert [step["arguments"]["brand_slot"] for step in open_steps] == ["logo_b", "logo_c"]
        assert open_steps[0]["arguments"]["prompt"] == "user text logo_b"
        assert brand.submitted_slots(2) == {"logo_a"}
        assert brand.grant_still_authorizes(open_steps, _Turn())
        brand.drop_memory_for_tests()
        assert brand.submitted_slots(2) == {"logo_a"}
        saved = brand._grant_of(2)
        assert saved["digest"] and saved["expires_at"] == spec["expires_at"]
    finally:
        BOT_CHAT_ID.reset(token)


def test_restart_rejects_the_old_card_and_a_double_start_has_one_winner(monkeypatch):
    brand.reset_for_tests()
    token = BOT_CHAT_ID.set("c")
    try:
        clock = {"t": 80.0}
        monkeypatch.setattr(brand, "_clock", lambda: clock["t"])
        steps = _steps("kept")
        spec = brand.stamp_confirm_spec(
            {"prompt": "p", "kind": "plan_quote", "options": [{"id": "start", "label": "开始"}, {"id": "cancel", "label": "取消"}],
             "min_selections": 1, "max_selections": 1, "allow_other": False},
            steps, _Turn(), amount=0.04, lang="zh",
        )
        brand.commit_confirmed_grant(steps, spec, _Turn(), amount=0.04)
        brand.remember_stage_plan(steps, fresh=True)
        brand.drop_memory_for_tests()
        clock["t"] = spec["expires_at"]
        assert brand.submit_block_reason(steps[0]["arguments"], _Turn()) == "expired"

        live = dict(spec)
        live["expires_at"] = clock["t"] + 10
        ask = bot_asks.create_ask("c", "m1", live)
        ask.abandoned = True
        assert bot_asks.resolve_confirm_answer(ask, ["start"], now=clock["t"] + 9) == "answered"
        assert bot_asks.resolve_confirm_answer(ask, ["start"], now=clock["t"] + 9) == "lost"

        late = dict(spec)
        late["expires_at"] = clock["t"] - 1
        late_ask = bot_asks.create_ask("c", "m2", late)
        late_ask.abandoned = True
        assert bot_asks.resolve_confirm_answer(late_ask, ["start"], now=clock["t"]) == "expired"
        assert bot_asks.resolve_confirm_answer(late_ask, ["start"], now=clock["t"]) == "lost"
        raced = bot_asks.create_ask("c", "m3", live)
        raced.abandoned = True
        bot_asks.resolve_ask(raced.id, "expired")
        assert bot_asks.resolve_confirm_answer(raced, ["start"], now=clock["t"]) == "lost"

        pending = {
            "id": "m2",
            "blocks": [{
                "type": "ask", "status": "pending", "ask_id": "gone",
                "brand_confirm": True, "expires_at": clock["t"] - 1,
                "prompt": "old",
            }],
        }
        brand.settle_restored_cards("c", [pending], now=clock["t"])
        assert pending["blocks"][0]["status"] == "expired"
    finally:
        BOT_CHAT_ID.reset(token)


async def test_brand_card_expires_on_a_real_timer(monkeypatch):
    brand.reset_for_tests()
    monkeypatch.setattr(brand, "BRAND_CONFIRM_TTL_S", 0.15)
    steps = _steps("timer")
    spec = brand.stamp_confirm_spec(
        {"prompt": "p", "kind": "plan_quote", "options": [{"id": "start", "label": "开始"}, {"id": "cancel", "label": "取消"}]},
        steps, _Turn(), amount=0.04, lang="zh",
    )
    assert spec["expires_at"] - spec["created_at"] == pytest.approx(0.15)
    from ComfyArt.api.bot_turns import _TurnState
    ACTIVE_TURNS["c"] = _TurnState(TurnHandle(), "c", "m-timer")
    provider = LocalLlmProvider(base_url=lambda: "http://127.0.0.1:9/v1")
    started = time.time()
    choice = await provider._confirm_plan(
        spec, TurnRequest(chat_id="c", user_text="确认", lang="zh"), TurnHandle(),
    )
    elapsed = time.time() - started
    block = ACTIVE_TURNS["c"].blocks[-1]
    ACTIVE_TURNS.pop("c", None)
    assert choice == "expired"
    assert block["status"] == "expired"
    assert elapsed >= 0.1


async def test_prompt_change_before_submit_does_not_reuse_the_old_grant(monkeypatch):
    from test_agent_budget_391 import Rig, calls, reply
    from test_brand_identity_1019 import _logos_ready

    brand.reset_for_tests()
    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        confirms = []

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _three()}))
            return reply("好")

        rig = Rig(monkeypatch, script)

        async def price(model, inputs):
            return (0.03, "quote", "test")

        monkeypatch.setattr(rig.p, "_price_one", price)
        monkeypatch.setattr(rig.p, "_models_for", lambda feature: [])

        async def answer(spec, turn, handle, **kwargs):
            confirms.append(spec)
            return "start" if len(confirms) == 1 else "cancel"

        monkeypatch.setattr(rig.p, "_confirm_plan", answer)
        await rig.send("做这一阶段")
        assert len(confirms) == 1
        assert confirms[0]["brand_confirm"] is True
        assert isinstance(confirms[0]["expires_at"], float)
        assert rig.paid_mcp() == []

        changed = _three(lambda slot: f"changed {slot}")
        for step in changed:
            step["arguments"]["base"] = "http://127.0.0.1/new-base.png"
            step["arguments"]["width"] = 1024

        def again(messages, n):
            if n == 0:
                return calls(("generate_image", dict(changed[0]["arguments"])))
            return reply("好")

        rig.script = again
        rig.n = 0
        await rig.send("改提示词")
        assert len(confirms) == 2
        assert rig.paid_mcp() == []
        assert brand.submitted_slots(2) == set()
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()
