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


def _logo_call(slot: str):
    return ("generate_image", {
        "prompt": slot, "skill": brand.SKILL, "brand_slot": slot,
    })


def _stage_message(*extra):
    from test_agent_budget_391 import calls
    return calls(("quote_plan", {"steps": _three()}), *extra)


async def _brand_provider(monkeypatch, price):
    """LocalLlmProvider.send with a scripted model. Pricing and MCP stay on loopback."""
    from test_agent_budget_391 import Rig, reply
    from test_brand_identity_1019 import _logos_ready

    brand.reset_for_tests()
    _logos_ready()
    confirms = []
    rig = Rig(monkeypatch, reply)

    async def priced(model, inputs):
        return price()

    monkeypatch.setattr(rig.p, "_price_one", priced)
    monkeypatch.setattr(rig.p, "_models_for", lambda feature: [])

    async def answer(spec, turn, handle, **kwargs):
        confirms.append(spec)
        return "start" if len(confirms) == 1 else "cancel"

    monkeypatch.setattr(rig.p, "_confirm_plan", answer)
    rig.confirms = confirms
    rig._reply = reply
    return rig


def _refs_of(spec):
    return [row.get("refs") for row in (spec.get("frozen_slots") or [])]


async def test_wait_keeps_the_reference_that_was_frozen_on_the_card(monkeypatch):
    from test_agent_budget_391 import reply

    token = BOT_CHAT_ID.set("c")
    try:
        rig = await _brand_provider(
            monkeypatch, lambda: (0.03, "quote", "refs", "q-refs", "USD"))

        async def answer(spec, turn, handle, **kwargs):
            rig.confirms.append(spec)
            brand._progress()["shapes"]["moodboard"] = "shape:changed-before-start"
            return "start"

        monkeypatch.setattr(rig.p, "_confirm_plan", answer)

        def script(messages, n):
            if n == 0:
                return _stage_message(_logo_call("logo_a"), _logo_call("logo_b"), _logo_call("logo_c"))
            return reply("好")

        rig.script = script
        _res, events = await rig.send("做这一阶段")
        assert rig.confirms and _refs_of(rig.confirms[0]) == [["shape:mood"]] * 3
        saved = brand._grant_of(2)
        assert saved is not None
        assert [row["refs"] for row in saved["slots"]] == [["shape:mood"]] * 3
        assert rig.paid_mcp() == []
        assert any("参数已变化" in (event.text or "") for event in events)
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_a_failed_grant_write_does_not_dispatch(monkeypatch):
    from ComfyArt.api import memory

    token = BOT_CHAT_ID.set("c")
    try:
        rig = await _brand_provider(
            monkeypatch, lambda: (0.03, "quote", "disk", "q-disk", "USD"))

        def script(messages, n):
            if n == 0:
                return _stage_message(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = script
        real = memory.atomic_write_json

        def broken(path, data):
            if str(path).endswith("brand-confirm.json"):
                raise OSError("disk full")
            return real(path, data)

        monkeypatch.setattr(memory, "atomic_write_json", broken)
        _res, events = await rig.send("做这一阶段")
        assert rig.paid_mcp() == []
        assert brand._grant_of(2) is None
        shown = "确认没有保存成功，没有开始，也没有扣积分。请重新取价。"
        visible = [event for event in events if event.t in ("delta", "tool_result")]
        assert visible and all(event.text == shown for event in visible)
        assert _res.error.startswith("[error]")
        assert "BrandGrantPersistError" in (_res.error or "")
    finally:
        monkeypatch.undo()
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_a_failed_submit_record_stays_unknown_and_is_not_sent_again(monkeypatch):
    from ComfyArt.api import memory
    from test_agent_budget_391 import calls

    token = BOT_CHAT_ID.set("c")
    try:
        rig = await _brand_provider(
            monkeypatch, lambda: (0.03, "quote", "after", "q-after", "USD"))

        def first(messages, n):
            if n == 0:
                return _stage_message()
            return rig._reply("好")

        rig.script = first
        await rig.send("先确认")
        assert rig.paid_mcp() == []
        assert brand._grant_of(2) is not None

        real = memory.atomic_write_json

        def break_submitted(path, data):
            chats = (data.get("chats") or {}) if isinstance(data, dict) else {}
            for chat in chats.values():
                for rec in ((chat or {}).get("quoted_stages") or {}).values():
                    if "logo_a" in (rec.get("submitted_slots") or []):
                        raise OSError("disk full")
            return real(path, data)

        monkeypatch.setattr(memory, "atomic_write_json", break_submitted)

        def second(messages, n):
            if n == 0:
                return _stage_message(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = second
        rig.n = 0
        failed, _events = await rig.send("提交第一张")
        assert "disk full" in (failed.error or "")
        assert len(rig.paid_mcp()) == 1
        assert "logo_a" in brand.unknown_slots(2)
        assert "logo_a" not in brand.submitted_slots(2)

        brand.drop_memory_for_tests()
        assert "logo_a" in brand.unknown_slots(2)

        def third(messages, n):
            if n == 0:
                return calls(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = third
        rig.n = 0
        _res, events = await rig.send("再试一次")
        assert len(rig.paid_mcp()) == 1
        assert any("待核对" in (event.text or "") for event in events)
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_same_execution_with_a_new_price_does_not_reuse_the_grant(monkeypatch):
    token = BOT_CHAT_ID.set("c")
    prices = [
        (0.03, "quote", "price", "q-same", "USD"),
        (0.05, "quote", "price", "q-same", "USD"),
    ]
    try:
        rig = await _brand_provider(monkeypatch, lambda: prices[0])
        seen = {"n": 0}

        async def priced(model, inputs):
            seen["n"] += 1
            return prices[0] if seen["n"] <= 3 else prices[1]

        monkeypatch.setattr(rig.p, "_price_one", priced)

        def first(messages, n):
            if n == 0:
                return _stage_message()
            return rig._reply("好")

        rig.script = first
        await rig.send("确认原价")
        assert len(rig.confirms) == 1
        assert rig.paid_mcp() == []

        def second(messages, n):
            if n == 0:
                return _stage_message(_logo_call("logo_a"), _logo_call("logo_b"), _logo_call("logo_c"))
            return rig._reply("好")

        rig.script = second
        rig.n = 0
        await rig.send("同参数新价")
        assert len(rig.confirms) == 2
        assert rig.paid_mcp() == []
        assert rig.confirms[1]["amount"] == pytest.approx(0.15)
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_same_execution_with_a_new_currency_or_quote_id_does_not_reuse_the_grant(monkeypatch):
    token = BOT_CHAT_ID.set("c")
    try:
        for follow in (
            (0.03, "quote", "currency", "q-same", "EUR"),
            (0.03, "quote", "quote-id", "q-new", "USD"),
        ):
            brand.reset_for_tests()
            prices = [(0.03, "quote", "first", "q-same", "USD"), follow]
            rig = await _brand_provider(monkeypatch, lambda: prices[0])
            seen = {"n": 0}

            async def priced(model, inputs, prices=prices, seen=seen):
                seen["n"] += 1
                return prices[0] if seen["n"] <= 3 else prices[1]

            monkeypatch.setattr(rig.p, "_price_one", priced)

            def first(messages, n):
                if n == 0:
                    return _stage_message()
                return rig._reply("好")

            rig.script = first
            await rig.send("确认")
            assert len(rig.confirms) == 1

            def second(messages, n):
                if n == 0:
                    return _stage_message(_logo_call("logo_a"), _logo_call("logo_b"), _logo_call("logo_c"))
                return rig._reply("好")

            rig.script = second
            rig.n = 0
            await rig.send("同参数变更")
            assert len(rig.confirms) == 2
            assert rig.paid_mcp() == []
            brand.reset_for_tests()
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


def test_stage1_stays_text_to_image_and_later_slots_refuse_without_a_base():
    brand.reset_for_tests()
    try:
        mood = brand.fill_default({"brand_slot": "moodboard", "prompt": "板"})
        assert mood["model"] == brand.QWEN_T2I
        assert "_brand_block" not in mood

        bare = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C"})
        assert bare.get("model") != brand.QWEN_T2I
        assert "edit_model" not in bare
        assert "Logo 方向 C缺少情绪板底图，无法修复，未报价、未扣费。" in bare["_brand_block"]["error"]
        assert "logo_c" not in bare["_brand_block"]["error"]
        assert "moodboard" not in bare["_brand_block"]["error"]

        brand._progress()["shapes"]["moodboard"] = "shape:mood"
        logo = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C"})
        assert logo["edit_model"] == brand.QWEN_EDIT
        assert logo["refs"] == ["shape:mood"]
        assert "_brand_block" not in logo

        spec = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})
        assert "规范卡缺少Logo 方向 A底图，无法修复，未报价、未扣费。" in spec["_brand_block"]["error"]
        assert "logo_a" not in spec["_brand_block"]["error"]
        assert spec.get("model") != brand.QWEN_T2I
        brand._progress()["shapes"]["logo_a"] = "shape:logo_a"
        ready = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})
        assert ready["edit_model"] == brand.QWEN_EDIT
        assert ready["refs"] == ["shape:logo_a", "shape:mood"]
    finally:
        brand.reset_for_tests()


async def test_an_estimate_keeps_approx_and_does_not_offer_start():
    from ComfyArt.bot.plan_quote import build_quote

    brand.reset_for_tests()
    try:
        async def estimated(_model, _inputs):
            return (0.03, "estimate", "live")

        async def models(_feature):
            return []

        steps = _three()
        for step in steps:
            step["model"] = brand.QWEN_EDIT
        quote = await build_quote(steps, "zh", threshold=0.5, pricer=estimated, models_for=models)
        assert quote is not None
        assert quote.prompt == "预计约 9 积分，实时价暂不可用。"
        assert "确认线" not in quote.prompt
        assert "约" in quote.total_text
        assert "开始" not in quote.prompt
        spec = brand.stamp_confirm_spec(
            quote.ask_spec(), steps, _Turn(), amount=quote.total, lang="zh",
            currency=quote.currency, quote_id=quote.quote_id)
        assert spec["price_state"] == "estimate"
        assert [row["id"] for row in spec["options"]] == ["requote", "cancel"]
        assert spec["options"][0]["label"] == "重新取价"
        assert spec["expires_at"] - spec["created_at"] == pytest.approx(600.0)
    finally:
        brand.reset_for_tests()


async def test_an_unpriced_brand_card_shows_no_amount_and_no_start():
    from ComfyArt.bot.plan_quote import build_quote

    brand.reset_for_tests()
    try:
        async def missing(_model, _inputs):
            return (None, "unpriced", "")

        async def models(_feature):
            return []

        steps = _three()
        for step in steps:
            step["model"] = brand.QWEN_EDIT
        quote = await build_quote(steps, "zh", threshold=0.5, pricer=missing, models_for=models)
        assert quote is not None
        assert quote.total_text == "未定价"
        assert not any(ch.isdigit() for ch in quote.total_text)
        assert "开始" not in quote.prompt
        assert all(not any(ch.isdigit() for ch in line.price) for line in quote.lines)
        spec = brand.stamp_confirm_spec(
            quote.ask_spec(), steps, _Turn(), amount=quote.total, lang="zh")
        assert spec["price_state"] == "unpriced"
        assert [row["id"] for row in spec["options"]] == ["requote", "cancel"]
    finally:
        brand.reset_for_tests()


async def test_a_real_brand_price_offers_start():
    from ComfyArt.bot.plan_quote import build_quote

    brand.reset_for_tests()
    try:
        async def priced(_model, _inputs):
            return (0.03, "quote", "live")

        async def models(_feature):
            return []

        steps = _three()
        for step in steps:
            step["model"] = brand.QWEN_EDIT
        quote = await build_quote(steps, "zh", threshold=0.5, pricer=priced, models_for=models)
        assert quote is not None
        assert quote.price_state == "quote"
        assert "约" not in quote.total_text
        spec = brand.stamp_confirm_spec(
            quote.ask_spec(), steps, _Turn(), amount=quote.total, lang="zh",
            currency=quote.currency, quote_id=quote.quote_id)
        assert [row["id"] for row in spec["options"]] == ["start", "cancel"]
        assert spec["options"][0]["label"] == "开始"
        assert spec["expires_at"] - spec["created_at"] == pytest.approx(600.0)
    finally:
        brand.reset_for_tests()


class _Crash(BaseException):
    """Leaves send() the way a process kill after POST would: not an Exception."""


def _logo_args(slot: str = "logo_a") -> dict:
    return {
        "skill": brand.SKILL, "brand_slot": slot, "prompt": slot,
        "width": 2048, "height": 2048, "count": 1, "refs": ["shape:mood"],
    }


async def _confirmed_stage(monkeypatch):
    rig = await _brand_provider(
        monkeypatch, lambda: (0.03, "quote", "reserve", "q-reserve", "USD"))

    def first(messages, n):
        if n == 0:
            return _stage_message()
        return rig._reply("好")

    rig.script = first
    await rig.send("先确认")
    assert rig.paid_mcp() == []
    grant = brand._grant_of(2)
    assert grant is not None
    return rig, grant["expires_at"]


async def test_crash_after_post_before_submit_record_is_not_sent_again(monkeypatch):
    from test_agent_budget_391 import calls

    token = BOT_CHAT_ID.set("c")
    try:
        rig, expires_at = await _confirmed_stage(monkeypatch)

        def boom(_args):
            raise _Crash("after post")

        monkeypatch.setattr(brand, "note_brand_submitted", boom)

        def second(messages, n):
            if n == 0:
                return _stage_message(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = second
        rig.n = 0
        with pytest.raises(_Crash):
            await rig.send("提交后崩溃")
        assert len(rig.paid_mcp()) == 1
        assert "logo_a" in brand.dispatching_slots(2)

        brand.drop_memory_for_tests()
        assert brand.submit_block_reason(_logo_args(), _Turn()) == "reconcile"
        assert brand._grant_of(2)["expires_at"] == expires_at

        def third(messages, n):
            if n == 0:
                return calls(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = third
        rig.n = 0
        _res, events = await rig.send("重启后再试")
        assert len(rig.paid_mcp()) == 1
        assert len(rig.confirms) == 1
        assert any("待核对" in (event.text or "") for event in events)
        assert brand._grant_of(2)["expires_at"] == expires_at
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_a_failed_dispatching_write_does_not_dispatch(monkeypatch):
    from ComfyArt.api import memory

    token = BOT_CHAT_ID.set("c")
    try:
        rig, expires_at = await _confirmed_stage(monkeypatch)
        real = memory.atomic_write_json

        def break_reserve(path, data):
            chats = (data.get("chats") or {}) if isinstance(data, dict) else {}
            for chat in chats.values():
                for rec in ((chat or {}).get("quoted_stages") or {}).values():
                    if "logo_a" in (rec.get("dispatching_slots") or []):
                        raise OSError("disk full")
            return real(path, data)

        monkeypatch.setattr(memory, "atomic_write_json", break_reserve)

        def second(messages, n):
            if n == 0:
                return _stage_message(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = second
        rig.n = 0
        _res, events = await rig.send("预留写不进去")
        assert rig.paid_mcp() == []
        assert "logo_a" not in brand.dispatching_slots(2)
        assert "logo_a" not in brand.submitted_slots(2)
        failed = [event for event in events if event.t == "tool_result" and event.is_error]
        assert failed
        assert all(event.text == "确认没有保存成功，没有开始，也没有扣积分。请重新取价。" for event in failed)
        assert not any("BrandGrantPersistError" in (event.text or "") or "[error]" in (event.text or "") for event in failed)
        assert brand._grant_of(2)["expires_at"] == expires_at
    finally:
        monkeypatch.undo()
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_restart_after_submit_writes_fail_does_not_resend(monkeypatch):
    from ComfyArt.api import memory
    from test_agent_budget_391 import calls

    token = BOT_CHAT_ID.set("c")
    try:
        rig, expires_at = await _confirmed_stage(monkeypatch)
        real = memory.atomic_write_json
        reserved = {"ok": False}

        def break_after_reserve(path, data):
            chats = (data.get("chats") or {}) if isinstance(data, dict) else {}
            has_dispatch = False
            for chat in chats.values():
                for rec in ((chat or {}).get("quoted_stages") or {}).values():
                    if "logo_a" in (rec.get("dispatching_slots") or []):
                        has_dispatch = True
            if has_dispatch and not reserved["ok"]:
                reserved["ok"] = True
                return real(path, data)
            if reserved["ok"] and str(path).endswith("brand-confirm.json"):
                raise OSError("disk full")
            return real(path, data)

        monkeypatch.setattr(memory, "atomic_write_json", break_after_reserve)

        def second(messages, n):
            if n == 0:
                return _stage_message(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = second
        rig.n = 0
        failed, _events = await rig.send("提交记录写盘失败")
        assert "disk full" in (failed.error or "")
        assert len(rig.paid_mcp()) == 1

        brand.drop_memory_for_tests()
        assert brand.dispatching_slots(2) == {"logo_a"}
        assert "logo_a" not in brand.unknown_slots(2)
        assert "logo_a" not in brand.submitted_slots(2)
        assert brand.submit_block_reason(_logo_args(), _Turn()) == "reconcile"
        assert brand._grant_of(2)["expires_at"] == expires_at

        def third(messages, n):
            if n == 0:
                return calls(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = third
        rig.n = 0
        _res, events = await rig.send("重启后同授权")
        assert len(rig.paid_mcp()) == 1
        assert len(rig.confirms) == 1
        assert any("待核对" in (event.text or "") for event in events)
        assert brand._grant_of(2)["expires_at"] == expires_at
    finally:
        monkeypatch.undo()
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_a_brand_generate_without_a_slot_is_filled_and_reserved(monkeypatch):
    from test_agent_budget_391 import calls

    token = BOT_CHAT_ID.set("c")
    try:
        rig, expires_at = await _confirmed_stage(monkeypatch)

        def boom(_args):
            raise _Crash("after post")

        monkeypatch.setattr(brand, "note_brand_submitted", boom)

        def second(messages, n):
            if n == 0:
                return calls(
                    ("quote_plan", {"steps": _three()}),
                    ("generate_image", {"prompt": "logo_a", "skill": brand.SKILL}),
                )
            return rig._reply("好")

        rig.script = second
        rig.n = 0
        with pytest.raises(_Crash):
            await rig.send("生成参数没有槽位")
        assert len(rig.paid_mcp()) == 1
        assert rig.paid_mcp()[0][1].get("brand_slot") == "logo_a"
        assert brand.dispatching_slots(2) == {"logo_a"}
        assert brand._grant_of(2)["expires_at"] == expires_at
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_a_logo_without_its_base_is_not_quoted_or_dispatched(monkeypatch):
    token = BOT_CHAT_ID.set("c")
    try:
        rig, expires_at = await _confirmed_stage(monkeypatch)
        brand._progress()["shapes"].pop("moodboard", None)

        def second(messages, n):
            if n == 0:
                return _stage_message(_logo_call("logo_a"))
            return rig._reply("好")

        rig.script = second
        rig.n = 0
        _res, events = await rig.send("没有情绪板还要出 Logo")
        assert rig.paid_mcp() == []
        assert any("无法修复，未报价、未扣费。" in (event.text or "") for event in events)
        assert not any("[error]" in (event.text or "") or "moodboard" in (event.text or "") for event in events)
        assert brand._grant_of(2)["expires_at"] == expires_at
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_a_dispatching_slot_is_not_sent_when_generate_omits_brand_slot(monkeypatch):
    """While a slot is dispatching, a generate_image that omits brand_slot pays nothing.

    Parse fills the slot (apply_generate → fill_default). The reservation is already
    on disk, so this send must not call the paid tool. The clock on the grant stays put.
    """
    from test_agent_budget_391 import calls

    token = BOT_CHAT_ID.set("c")
    try:
        rig, expires_at = await _confirmed_stage(monkeypatch)
        brand.reserve_brand_dispatch(_logo_args("logo_a"))
        assert brand.dispatching_slots(2) == {"logo_a"}
        assert rig.paid_mcp() == []

        def second(messages, n):
            if n == 0:
                return calls(("generate_image", {"prompt": "logo_a", "skill": brand.SKILL}))
            return rig._reply("好")

        rig.script = second
        rig.n = 0
        _res, events = await rig.send("派发中的槽位，生成参数没有 brand_slot")
        assert rig.paid_mcp() == []
        assert brand.dispatching_slots(2) == {"logo_a"}
        assert len(rig.confirms) == 1
        assert any("待核对" in (event.text or "") for event in events)
        assert not any("缺少底图" in (event.text or "") for event in events)
        assert brand._grant_of(2)["expires_at"] == expires_at
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


_QUOTE_FAIL = {
    "zh": "这次没能拿到报价，没有开始，也没有扣积分。请稍后重新取价。",
    "en": "Couldn't get a quote. Nothing started and nothing was charged. Please requote in a moment.",
}
_CONFIRM_UNSAVED = {
    "zh": "确认没有保存成功，没有开始，也没有扣积分。请重新取价。",
    "en": "Your confirmation wasn't saved. Nothing started and nothing was charged. Please requote.",
}


async def _send_lang(rig, text, lang):
    events = []

    async def emit(ev):
        events.append(ev)

    res = await rig.p.send(TurnRequest(
        chat_id="c", user_text=text, lang=lang, mcp_endpoint="http://x/mcp",
        model="m", goal_text=text), emit, TurnHandle())
    return res, events


def _assert_failure_copy(res, events, sentence, leaked):
    visible = [event for event in events if event.t == "delta" or (event.t == "tool_result" and event.is_error)]
    assert visible
    assert all(event.text == sentence for event in visible)
    for event in visible:
        assert "[error]" not in (event.text or "")
        for word in leaked:
            assert word not in (event.text or "")
    assert (res.error or "").startswith("[error]")
    for word in leaked:
        assert word in (res.error or "")


async def test_quote_and_confirm_failures_show_the_product_sentence(monkeypatch):
    """A failed quote or an unsaved confirmation does not show the exception to the user."""
    from test_agent_budget_391 import calls

    token = BOT_CHAT_ID.set("c")
    try:
        for lang, leaked in (("zh", ("RuntimeError", "logo_c")), ("en", ("RuntimeError", "logo_a"))):
            brand.reset_for_tests()
            rig = await _brand_provider(
                monkeypatch, lambda: (0.03, "quote", "live", "q-fail", "USD"))

            async def boom(_steps, _lang, marker=leaked[1]):
                raise RuntimeError(f"{marker} price lookup failed")

            monkeypatch.setattr(rig.p, "_quote_steps", boom)

            def script(messages, n):
                if n == 0:
                    return calls(("quote_plan", {"steps": _three()}))
                return rig._reply("好")

            rig.script = script
            res, events = await _send_lang(rig, "取价失败", lang)
            _assert_failure_copy(res, events, _QUOTE_FAIL[lang], leaked)
            assert rig.paid_mcp() == []

        for lang in ("zh", "en"):
            brand.reset_for_tests()
            rig = await _brand_provider(
                monkeypatch, lambda: (0.03, "quote", "live", "q-save", "USD"))

            def refuse(*_args, **_kwargs):
                raise brand.BrandGrantPersistError("logo_b was not frozen")

            monkeypatch.setattr(brand, "commit_confirmed_grant", refuse)

            def script(messages, n):
                if n == 0:
                    return calls(("quote_plan", {"steps": _three()}))
                return rig._reply("好")

            rig.script = script
            res, events = await _send_lang(rig, "确认没保存", lang)
            _assert_failure_copy(res, events, _CONFIRM_UNSAVED[lang], ("BrandGrantPersistError", "logo_b"))
            assert rig.paid_mcp() == []
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_answer_requote_rejects_the_old_start_and_prices_open_slots(monkeypatch, bot_client):
    """POST /answer ['requote'] is a real confirm result, not a cancel.

    The new card is the existing quote chain. The old card's Start is refused
    and nothing is dispatched. Open slots only, and the new deadline is 600 seconds.
    """
    import asyncio
    import time as _time

    from ComfyArt.api import chat_store
    from ComfyArt.api.paid_guard import noturn_key
    from ComfyArt.bot import providers
    from conftest import wait_bot_done
    from test_agent_budget_391 import Rig, calls, reply
    from test_brand_identity_1019 import _logos_ready

    token = BOT_CHAT_ID.set(noturn_key("anonymous"))
    try:
        brand.reset_for_tests()
        _logos_ready()
        steps = _three(lambda slot: f"user text {slot}")
        for step in steps:
            step["model"] = brand.QWEN_EDIT
        brand.remember_stage_plan(steps, fresh=True)
        brand.note_brand_submitted(steps[0]["arguments"])
        clock = {"t": _time.time()}
        monkeypatch.setattr(brand, "_clock", lambda: clock["t"])
        rig = Rig(monkeypatch, lambda _m, n: calls(("quote_plan", {"steps": steps})) if n == 0 else reply("好"))

        async def priced(_model, _inputs):
            return (0.03, "estimate", "live", "q-re", "USD")

        monkeypatch.setattr(rig.p, "_price_one", priced)
        monkeypatch.setattr(rig.p, "_models_for", lambda _feature: [])
        monkeypatch.setitem(providers._REGISTRY, rig.p.id, rig.p)
        seen = []
        real_create = bot_asks.create_ask

        def spy(chat_id, message_id, spec):
            ask = real_create(chat_id, message_id, spec)
            seen.append(ask)
            return ask

        monkeypatch.setattr(bot_asks, "create_ask", spy)
        created = await bot_client.post(
            "/comfyart/bot/chats", json={"provider": "local-llm", "project": "local"})
        assert created.status < 300, await created.text()
        chat = (await created.json())["chat"]["id"]
        started = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/send", json={"text": "重新取价", "lang": "zh"})
        assert started.status < 300, await started.text()

        async def wait_ask(n):
            for _ in range(250):
                if len(seen) >= n and seen[n - 1].id in bot_asks.PENDING:
                    return seen[n - 1]
                await asyncio.sleep(0.02)
            tail = [b for m in chat_store.list_messages(chat) for b in (m.get("blocks") or [])]
            raise AssertionError(f"ask {n} missing; seen={len(seen)} tail={tail[-3:]}")

        old = await wait_ask(1)
        clock["t"] += 5
        requote = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/asks/{old.id}/answer", json={"selected": ["requote"]})
        assert requote.status == 202, await requote.text()
        new = await wait_ask(2)
        assert new.spec["expires_at"] - new.spec["created_at"] == pytest.approx(600.0)
        assert new.spec["created_at"] == clock["t"]
        assert [step["arguments"]["brand_slot"] for step in new.spec["brand_steps"]] == ["logo_b", "logo_c"]
        assert [row["id"] for row in new.spec["options"]] == ["requote", "cancel"]
        assert new.spec["prompt"].startswith("预计约 6 积分，实时价暂不可用。")
        assert "确认线" not in new.spec["prompt"]

        class _HttpTurn:
            owner_id = "local"
            project_id = "local"
            chat_id = chat

        assert brand.commit_confirmed_grant(
            steps, old.spec, _HttpTurn(), amount=old.spec.get("amount")) is None
        refused = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/asks/{old.id}/answer", json={"selected": ["start"]})
        assert refused.status == 409
        cancelled = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/asks/{new.id}/answer", json={"selected": ["cancel"]})
        assert cancelled.status == 202, await cancelled.text()
        data = await wait_bot_done(bot_client, chat, timeout=5)
        assert rig.paid_mcp() == []
        cards = [
            (mi, bi, block)
            for mi, message in enumerate(data["messages"])
            for bi, block in enumerate(message.get("blocks") or [])
            if block.get("brand_confirm") is True
        ]
        assert [block["ask_id"] for _mi, _bi, block in cards] == [old.id, new.id]
        assert cards[0][2].get("replaced_by") == new.id
        assert "button" not in cards[0][2]
        assert (cards[1][0], cards[1][1]) > (cards[0][0], cards[0][1])
        assert cards[1][2]["expires_at"] - cards[1][2]["created_at"] == pytest.approx(600.0)
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


class _SameTurn:
    owner_id = "local"
    project_id = "local"
    chat_id = "c"


async def test_requote_shows_a_new_card_and_the_old_confirmation_cannot_pay(monkeypatch):
    """重新取价 stays in the turn: a new card, a new 10-minute deadline, open slots only.

    The old snapshot cannot be committed, and replaying it does not dispatch.
    An estimate card still has no Start.
    """
    from test_agent_budget_391 import calls

    token = BOT_CHAT_ID.set("c")
    try:
        clock = {"t": 1_700_000_000.0}
        monkeypatch.setattr(brand, "_clock", lambda: clock["t"])
        rig = await _brand_provider(
            monkeypatch, lambda: (0.03, "estimate", "live", "q-re", "USD"))
        steps = _three(lambda slot: f"user text {slot}")
        for step in steps:
            step["model"] = brand.QWEN_EDIT
        brand.remember_stage_plan(steps, fresh=True)
        brand.note_brand_submitted(steps[0]["arguments"])
        confirms = []

        async def answer(spec, turn, handle, **_kwargs):
            confirms.append(spec)
            if len(confirms) == 1:
                clock["t"] += 5
                return "requote"
            return "cancel"

        monkeypatch.setattr(rig.p, "_confirm_plan", answer)

        def first(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": steps}))
            return rig._reply("好")

        rig.script = first
        await rig.send("重新取价")
        assert len(confirms) == 2
        old, new = confirms
        assert new["expires_at"] != old["expires_at"]
        assert new["expires_at"] - new["created_at"] == pytest.approx(600.0)
        assert new["created_at"] == clock["t"]
        saved = {
            step["arguments"]["brand_slot"]: step["arguments"]["prompt"]
            for step in new["brand_steps"]
        }
        assert saved == {"logo_b": "user text logo_b", "logo_c": "user text logo_c"}
        assert [row["slot"] for row in new["frozen_slots"]] == ["logo_b", "logo_c"]
        assert [row["id"] for row in new["options"]] == ["requote", "cancel"]
        assert rig.paid_mcp() == []
        assert brand.commit_confirmed_grant(steps, old, _SameTurn(), amount=old["amount"]) is None
        assert brand.grant_still_authorizes(
            steps, _SameTurn(), quote_id=old.get("quote_id")) is False

        async def start_old(spec, turn, handle, **_kwargs):
            return "start"

        monkeypatch.setattr(rig.p, "_confirm_plan", start_old)
        monkeypatch.setattr(brand, "stamp_confirm_spec", lambda *a, **k: old)

        def again(messages, n):
            if n == 0:
                return calls(("generate_image", {
                    "prompt": "user text logo_b", "skill": brand.SKILL, "brand_slot": "logo_b",
                }))
            return rig._reply("好")

        rig.script = again
        rig.n = 0
        await rig.send("旧确认再提交")
        assert rig.paid_mcp() == []
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


def _stored_steps():
    steps = _three(lambda slot: f"user text {slot}")
    for step in steps:
        step["model"] = brand.QWEN_EDIT
    return steps


def _brand_blocks(chat_id):
    from ComfyArt.api import chat_store
    return [
        block
        for message in chat_store.list_messages(chat_id)
        for block in (message.get("blocks") or [])
        if isinstance(block, dict) and block.get("brand_confirm") is True
    ]


def _park_card(chat_id, ask_id, steps, when, *, valid=False):
    from ComfyArt.api import chat_store
    created = when - 610
    block = {
        "type": "ask",
        "ask_id": ask_id,
        "status": "pending",
        "kind": "plan_quote",
        "brand_confirm": True,
        "lang": "zh",
        "prompt": "old",
        "created_at": created,
        "expires_at": when + 600 if valid else when - 1,
        "brand_steps": steps,
        "options": [
            {"id": "start", "label": "开始"},
            {"id": "cancel", "label": "取消"},
        ],
    }
    chat_store.create_message(chat_id=chat_id, role="assistant", blocks=[block], status="done")
    return block


async def _wait_pending(seen, n):
    import asyncio
    for _ in range(250):
        if len(seen) >= n and seen[n - 1].id in bot_asks.PENDING:
            return seen[n - 1]
        await asyncio.sleep(0.02)
    raise AssertionError(f"ask {n} missing; seen={len(seen)}")


def _spy_asks(monkeypatch):
    seen = []
    real = bot_asks.create_ask

    def spy(chat_id, message_id, spec):
        ask = real(chat_id, message_id, spec)
        seen.append(ask)
        return ask

    monkeypatch.setattr(bot_asks, "create_ask", spy)
    return seen


def _install_stored_provider(monkeypatch, priced):
    from ComfyArt.bot import providers
    from test_agent_budget_391 import Rig

    def refuse_model(_messages, _n):
        raise AssertionError("stored re-quote must not call the model")

    rig = Rig(monkeypatch, refuse_model)
    monkeypatch.setattr(rig.p, "_price_one", priced)
    monkeypatch.setattr(rig.p, "_models_for", lambda _feature: [])
    monkeypatch.setitem(providers._REGISTRY, rig.p.id, rig.p)
    return rig


async def test_stored_requote_start_pays_each_open_slot_once(monkeypatch, bot_client):
    """Expired card → /brand-requote → Start pays the unsubmitted slots once.

    The old card's Start is 409 and adds no paid call. The new deadline is 600 seconds.
    """
    import asyncio
    import time as _time

    from ComfyArt.api.paid_guard import noturn_key

    token = BOT_CHAT_ID.set("")
    try:
        assert brand._chat() == noturn_key("anonymous")
        brand.reset_for_tests()
        from test_brand_identity_1019 import _logos_ready
        _logos_ready()
        steps = _stored_steps()
        brand.remember_stage_plan(steps, fresh=True)
        brand.note_brand_submitted(steps[0]["arguments"])
        # Start's expiry check uses the wall clock. The card deadline is this
        # same instant plus 600s, so the difference stays exact.
        clock = {"t": _time.time()}
        monkeypatch.setattr(brand, "_clock", lambda: clock["t"])

        async def priced(_model, _inputs):
            return (0.03, "quote", "live", "q-stored", "USD")

        rig = _install_stored_provider(monkeypatch, priced)
        seen = _spy_asks(monkeypatch)
        created = await bot_client.post(
            "/comfyart/bot/chats", json={"provider": "local-llm", "project": "local"})
        assert created.status < 300, await created.text()
        chat = (await created.json())["chat"]["id"]
        old_id = "expired-stored-start"
        _park_card(chat, old_id, steps, clock["t"])
        requote = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/brand-requote", json={"ask_id": old_id})
        assert requote.status == 202, await requote.text()
        new = await _wait_pending(seen, 1)
        assert new.spec["expires_at"] - new.spec["created_at"] == 600
        assert [step["arguments"]["brand_slot"] for step in new.spec["brand_steps"]] == ["logo_b", "logo_c"]
        assert [row["id"] for row in new.spec["options"]] == ["start", "cancel"]
        started = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/asks/{new.id}/answer", json={"selected": ["start"]})
        assert started.status == 202, await started.text()
        for _ in range(250):
            if len(rig.paid_mcp()) >= 2:
                break
            await asyncio.sleep(0.02)
        paid = [args.get("brand_slot") for _name, args in rig.paid_mcp()]
        assert paid == ["logo_b", "logo_c"]
        assert len(paid) == len(set(paid))
        before = len(rig.paid_mcp())
        refused = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/asks/{old_id}/answer", json={"selected": ["start"]})
        assert refused.status == 409
        await asyncio.sleep(0.05)
        assert len(rig.paid_mcp()) == before
        cards = _brand_blocks(chat)
        old = next(block for block in cards if block.get("ask_id") == old_id)
        assert old.get("replaced_by") == new.id
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_stored_requote_rejects_a_second_card(monkeypatch, bot_client):
    """A second re-quote, a still-valid card, and two concurrent re-quotes make one new card."""
    import asyncio

    from ComfyArt.api.paid_guard import noturn_key

    token = BOT_CHAT_ID.set("")
    try:
        assert brand._chat() == noturn_key("anonymous")
        brand.reset_for_tests()
        from test_brand_identity_1019 import _logos_ready
        _logos_ready()
        steps = _stored_steps()
        brand.remember_stage_plan(steps, fresh=True)
        clock = {"t": 1_700_000_000.0}
        monkeypatch.setattr(brand, "_clock", lambda: clock["t"])
        gate = asyncio.Event()
        gate.set()

        async def priced(_model, _inputs):
            await gate.wait()
            return (0.03, "quote", "live", "q-once", "USD")

        _install_stored_provider(monkeypatch, priced)
        created = await bot_client.post(
            "/comfyart/bot/chats", json={"provider": "local-llm", "project": "local"})
        assert created.status < 300, await created.text()
        chat = (await created.json())["chat"]["id"]
        _park_card(chat, "still-valid", steps, clock["t"], valid=True)
        kept = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/brand-requote", json={"ask_id": "still-valid"})
        assert kept.status == 409, await kept.text()
        assert len(_brand_blocks(chat)) == 1

        _park_card(chat, "expired-once", steps, clock["t"])
        first = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/brand-requote", json={"ask_id": "expired-once"})
        assert first.status == 202, await first.text()
        assert len(_brand_blocks(chat)) == 3
        again = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/brand-requote", json={"ask_id": "expired-once"})
        assert again.status == 409, await again.text()
        assert len(_brand_blocks(chat)) == 3
        held = next(block for block in _brand_blocks(chat) if block.get("ask_id") not in {"still-valid", "expired-once"})
        closed = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/asks/{held['ask_id']}/answer", json={"selected": ["cancel"]})
        assert closed.status == 202, await closed.text()

        other = await bot_client.post(
            "/comfyart/bot/chats", json={"provider": "local-llm", "project": "local"})
        assert other.status < 300, await other.text()
        chat2 = (await other.json())["chat"]["id"]
        _park_card(chat2, "expired-race", steps, clock["t"])
        gate.clear()
        pending = asyncio.gather(
            bot_client.post(f"/comfyart/bot/chats/{chat2}/brand-requote", json={"ask_id": "expired-race"}),
            bot_client.post(f"/comfyart/bot/chats/{chat2}/brand-requote", json={"ask_id": "expired-race"}),
        )
        await asyncio.sleep(0.05)
        gate.set()
        left, right = await pending
        codes = sorted(response.status for response in (left, right))
        assert codes == [202, 409], (codes, await left.text(), await right.text())
        raced = [block for block in _brand_blocks(chat2) if block.get("ask_id") != "expired-race"]
        assert len(raced) == 1
        old = next(block for block in _brand_blocks(chat2) if block.get("ask_id") == "expired-race")
        assert old.get("replaced_by") == raced[0].get("ask_id")
        closed = await bot_client.post(
            f"/comfyart/bot/chats/{chat2}/asks/{raced[0]['ask_id']}/answer", json={"selected": ["cancel"]})
        assert closed.status == 202, await closed.text()
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()


async def test_live_turn_and_stored_requote_share_the_progress_key(monkeypatch, bot_client):
    """A live quote and /brand-requote read one progress key and both can price."""
    import time as _time

    from ComfyArt.api import chat_store
    from ComfyArt.api.paid_guard import noturn_key
    from ComfyArt.bot import providers
    from conftest import wait_bot_done
    from test_agent_budget_391 import Rig, calls, reply
    from test_brand_identity_1019 import _logos_ready

    token = BOT_CHAT_ID.set("")
    try:
        brand.reset_for_tests()
        assert BOT_CHAT_ID.get() == ""
        assert brand._chat() == noturn_key("anonymous")
        _logos_ready()
        steps = _stored_steps()
        brand.remember_stage_plan(steps, fresh=True)
        clock = {"t": _time.time()}
        monkeypatch.setattr(brand, "_clock", lambda: clock["t"])
        seen_keys = []
        phase = {"name": "live"}
        real_chat = brand._chat

        def spy():
            key = real_chat()
            seen_keys.append((phase["name"], key))
            return key

        monkeypatch.setattr(brand, "_chat", spy)
        rig = Rig(monkeypatch, lambda _m, n: calls(("quote_plan", {"steps": steps})) if n == 0 else reply("好"))

        async def priced(_model, _inputs):
            return (0.03, "quote", "live", "q-key", "USD")

        monkeypatch.setattr(rig.p, "_price_one", priced)
        monkeypatch.setattr(rig.p, "_models_for", lambda _feature: [])
        monkeypatch.setitem(providers._REGISTRY, rig.p.id, rig.p)
        seen = _spy_asks(monkeypatch)
        created = await bot_client.post(
            "/comfyart/bot/chats", json={"provider": "local-llm", "project": "local"})
        assert created.status < 300, await created.text()
        chat = (await created.json())["chat"]["id"]
        started = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/send", json={"text": "同一进度", "lang": "zh"})
        assert started.status < 300, await started.text()
        live = await _wait_pending(seen, 1)
        assert live.spec.get("brand_steps")
        cancelled = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/asks/{live.id}/answer", json={"selected": ["cancel"]})
        assert cancelled.status == 202, await cancelled.text()
        await wait_bot_done(bot_client, chat, timeout=5)
        phase["name"] = "stored"
        old_id = "expired-same-key"
        _park_card(chat, old_id, steps, clock["t"])
        requote = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/brand-requote", json={"ask_id": old_id})
        assert requote.status == 202, await requote.text()
        stored = await _wait_pending(seen, 2)
        assert stored.spec.get("brand_steps")
        phases = {name for name, _key in seen_keys}
        assert phases == {"live", "stored"}
        assert {key for _name, key in seen_keys} == {noturn_key("anonymous")}
        closed = await bot_client.post(
            f"/comfyart/bot/chats/{chat}/asks/{stored.id}/answer", json={"selected": ["cancel"]})
        assert closed.status == 202, await closed.text()
        assert chat_store.list_messages(chat)
    finally:
        BOT_CHAT_ID.reset(token)
        brand.reset_for_tests()
