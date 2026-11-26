"""Default-brand plan protocol on the hint the turn actually loads.

This is a scripted LocalLlmProvider loop. It is not a live model.

Replacements, all in-process:
- chat completions are a fixed tool script, not a model
- generate_image's MCP handler returns ids and does not call WaveSpeed
- wait_generation places the holders recorded by those submits
- ask_user is the real tool; the test resolves the pending card with A
- quote confirmation returns start (the human confirm this script stands in for)
- the run-progress budget loop is off, so a stall tracker cannot end the turn
- each scripted tool call has its own id, so the run's resume key does not
  treat a later slot as a replay of an earlier call

Left on the real path: default_hint via run_hint/compose_provider_text, brand
cards, per-stage quote and grant, reserve_brand_dispatch, and paid_guard.
Nothing here clears used counts or raises the cap. The guard's text is the
typed sentence, which names no image count, so the cap stays 4.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from ComfyArt.api import brand_identity as brand
from ComfyArt.api import chat_store, mcp, paid_guard
from ComfyArt.api.bot_turns import ACTIVE_TURNS, _TurnState
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy
from test_agent_budget_391 import Rig, reply

TYPED = "做一套品牌视觉"
LOGO_SLOTS = ("logo_a", "logo_b", "logo_c")
FINAL_SLOTS = ("spec", "cup", "bag", "storefront")
ALL_SLOTS = ("moodboard",) + LOGO_SLOTS + FINAL_SLOTS

_CARD1 = {"questions": [
    {"id": "bi_delivery", "prompt": "交付哪些物料？", "options": [{"id": "A", "label": "核心"}, {"id": "B", "label": "扩展"}]},
    {"id": "bi_color", "prompt": "色彩方向？", "options": [{"id": "A", "label": "暖"}, {"id": "B", "label": "冷"}]},
    {"id": "bi_mark", "prompt": "标志构成？", "options": [{"id": "A", "label": "符号"}, {"id": "B", "label": "字标"}]},
    {"id": "bi_source", "prompt": "素材怎么处理？", "options": [{"id": "A", "label": "生成"}, {"id": "B", "label": "沿用"}]},
], "page_count": 4, "allow_skip": True}
_CARD2 = {"questions": [{
    "id": "bi_moodboard", "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
    "options": [{"id": "A", "label": "就这版，通过"}, {"id": "B", "label": "重做"}],
}]}
_CARD3 = {"questions": [{
    "id": "bi_direction", "prompt": "选定哪个 Logo 方向作为最终标识？",
    "options": [{"id": "A", "label": "方向A"}, {"id": "B", "label": "方向B"}, {"id": "C", "label": "方向C"}],
}]}


def setup_function():
    global _CALL
    _CALL = 0
    brand.reset_for_tests()
    paid_guard.TURNS.clear()


def teardown_function():
    brand.reset_for_tests()
    paid_guard.TURNS.clear()
    ACTIVE_TURNS.clear()


def test_default_entry_payload_requires_three_stable_plan_items():
    """The hint attached to the user message, not the paged skill read, carries the protocol."""
    from ComfyArt.api.bot_send import compose_provider_text
    from ComfyArt.bot.skill_output import run_hint

    hint = run_hint(brand.SKILL, "")
    payload = compose_provider_text(TYPED, skill_name=brand.SKILL)
    assert hint == brand.default_hint()
    assert hint in payload
    assert "Before any image, call update_plan with exactly these three items" in payload
    assert "Call update_plan again whenever the active stage changes" in payload
    assert "Do not rename an item, add an item, or drop an item." in payload
    assert "Quote each stage once, before it runs" in payload
    assert brand.PLAN_ITEMS == ("情绪板", "Logo 方向", "交付物")
    for name in brand.PLAN_ITEMS:
        assert f'"{name}"' in payload
    assert payload.index(f'"{brand.PLAN_MOODBOARD}"') < payload.index(f'"{brand.PLAN_LOGOS}"')
    assert payload.index(f'"{brand.PLAN_LOGOS}"') < payload.index(f'"{brand.PLAN_DELIVERABLES}"')
    for old in ('"Moodboard"', '"Logo directions"', '"Deliverables"'):
        assert old not in payload, old
    # A selected industry template keeps its own output lock and is not this protocol.
    templated = run_hint(brand.SKILL, "", preset_id="geometric")
    assert "call update_plan with exactly these three items" not in templated


_CALL = 0


def _message(*items: tuple[str, dict]) -> dict:
    """One assistant step. Tool-call ids are unique for the whole script.

    The run dedupes a paid call by step plus tool-call id. Reusing t0/t1 on
    every step would treat a later slot as a replay of an earlier one.
    """
    global _CALL
    tool_calls = []
    for name, args in items:
        tool_calls.append({
            "id": f"c{_CALL}",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        })
        _CALL += 1
    return {"choices": [{"message": {"content": "", "tool_calls": tool_calls}}]}


def _plan(active: int | None, done_through: int) -> dict:
    steps = []
    for index, name in enumerate(brand.PLAN_ITEMS):
        if index < done_through:
            status = "done"
        elif index == active:
            status = "active"
        else:
            status = "pending"
        steps.append({"text": name, "status": status})
    return {"steps": steps}


def _generate(slot: str) -> tuple[str, dict]:
    return ("generate_image", {"prompt": slot, "skill": brand.SKILL, "brand_slot": slot})


def _quote(slots: tuple[str, ...]) -> tuple[str, dict]:
    return ("quote_plan", {"steps": [
        {"text": slot, "tool": "generate_image",
         "arguments": {"prompt": slot, "skill": brand.SKILL, "brand_slot": slot}}
        for slot in slots
    ]})


def _answers_for(spec: dict) -> dict:
    ids = [str(q.get("id") or "") for q in (spec.get("questions") or []) if isinstance(q, dict)]
    if "bi_direction" in ids:
        return {"bi_direction": {"selected": ["A"]}}
    if "bi_moodboard" in ids:
        return {"bi_moodboard": {"selected": ["A"]}}
    return {
        "bi_delivery": {"selected": ["A"]},
        "bi_color": {"selected": ["A"]},
        "bi_mark": {"selected": ["A"]},
        "bi_source": {"selected": ["A"]},
    }


def _positive_script(messages, n):
    stages = [
        _message(("update_plan", _plan(0, 0)), ("ask_user", _CARD1)),
        _message(_quote(("moodboard",)), _generate("moodboard")),
        _message(("wait_generation", {"ids": ["pending"]})),
        _message(("update_plan", _plan(1, 1)), ("ask_user", _CARD2)),
        _message(_quote(LOGO_SLOTS), *(_generate(slot) for slot in LOGO_SLOTS)),
        _message(("wait_generation", {"ids": ["pending"]})),
        _message(("update_plan", _plan(2, 2)), ("ask_user", _CARD3)),
        _message(_quote(FINAL_SLOTS), *(_generate(slot) for slot in FINAL_SLOTS)),
        _message(("wait_generation", {"ids": ["pending"]})),
        _message(("update_plan", _plan(None, 3)), _generate("moodboard")),
        reply("交付完成"),
    ]
    return stages[n] if n < len(stages) else reply("done")


def _no_switch_script(messages, n):
    """Same eight-slot attempt with no update_plan, so every image shares the empty plan item."""
    stages = [
        _message(("ask_user", _CARD1)),
        _message(_quote(("moodboard",)), _generate("moodboard")),
        _message(("wait_generation", {"ids": ["pending"]})),
        _message(("ask_user", _CARD2)),
        _message(_quote(LOGO_SLOTS), *(_generate(slot) for slot in LOGO_SLOTS)),
        _message(("wait_generation", {"ids": ["pending"]})),
        _message(("ask_user", _CARD3)),
        _message(_quote(FINAL_SLOTS), *(_generate(slot) for slot in FINAL_SLOTS)),
        reply("停在这里"),
    ]
    return stages[n] if n < len(stages) else reply("done")


async def _run(monkeypatch, script):
    from ComfyArt.api import bot_asks, wavespeed
    from ComfyArt.api.bot_send import compose_provider_text

    submits: list = []

    async def explode(*_args, **_kwargs):
        submits.append(1)
        raise AssertionError("wavespeed.submit must not run")

    monkeypatch.setattr(wavespeed, "submit", explode)
    chat = chat_store.create_chat(user="local", project="local", provider="local")
    message = chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=[], status="streaming")
    ACTIVE_TURNS[chat["id"]] = _TurnState(TurnHandle(), chat["id"], message["id"])
    paid: list[dict] = []
    order: list[tuple] = []

    async def generate(args):
        slot = str(args.get("brand_slot") or "")
        order.append(("generate", slot))
        gid = f"g{len(paid) + 1}"
        payload = {"ids": [gid]}
        brand.record_submitted(args, payload)
        paid.append({"slot": slot, "id": gid})
        return payload

    async def wait(_args):
        progress = brand._progress()
        holders = dict(progress.get("holders") or {})
        placed = progress.get("shapes") or {}
        results = []
        for gid, slot in holders.items():
            if slot in placed:
                continue
            results.append({
                "id": gid, "status": "done",
                "shapes": [f"shape:{slot}"], "urls": [f"/{slot}.png"],
            })
        payload = {"status": "done", "results": results}
        brand.record_wait(payload)
        return payload

    monkeypatch.setitem(mcp.TOOLS, "generate_image", {
        **mcp.TOOLS["generate_image"], "handler": generate,
    })
    monkeypatch.setitem(mcp.TOOLS, "wait_generation", {
        **mcp.TOOLS["wait_generation"], "handler": wait,
    })

    rig = Rig(monkeypatch, script)
    rig.p.unloads_lms_during_waits = False
    monkeypatch.setattr(rig.p, "_run_policy", lambda: resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"}))

    async def price(_model, _inputs):
        return (0.03, "quote", "stage-plan")

    async def confirm(spec, turn, handle, *, run=None, messages=None, retire_previous: bool = False):
        frozen = spec.get("frozen") if isinstance(spec, dict) else None
        stage = int((frozen or {}).get("stage") or 0) if isinstance(frozen, dict) else 0
        order.append(("confirm", stage))
        rig.confirms.append(spec)
        return "start"

    monkeypatch.setattr(rig.p, "_price_one", price)
    monkeypatch.setattr(rig.p, "_models_for", lambda _feature: [])
    monkeypatch.setattr(rig.p, "_threshold", lambda: 0.0)
    monkeypatch.setattr(rig.p, "_confirm_plan", confirm)

    async def mcp_call(_session, _endpoint, name, arguments):
        if name == "ask_user":
            task = asyncio.create_task(mcp._tools_call({"name": name, "arguments": arguments}))
            for _ in range(30):
                await asyncio.sleep(0)
                pending = [
                    ask for ask in list(bot_asks.PENDING.values())
                    if ask.chat_id == chat["id"] and (ask._future is None or not ask._future.done())
                ]
                if pending:
                    spec = pending[-1].spec
                    bot_asks.resolve_ask(
                        pending[-1].id, "answered",
                        selected=["A"], answers=_answers_for(spec))
                    break
            out = await task
        else:
            out = await mcp._tools_call({"name": name, "arguments": arguments})
        text = out["content"][0]["text"]
        if out.get("isError"):
            text = "[tool error] " + text
        return text, []

    monkeypatch.setattr(rig.p, "_mcp_call_tool", mcp_call)
    payload = compose_provider_text(TYPED, skill_name=brand.SKILL)
    events: list[BotEvent] = []

    async def emit(event):
        events.append(event)

    token = BOT_CHAT_ID.set(chat["id"])
    scope = brand.brand_progress_scope(chat["id"])
    paid_guard.begin_turn(chat["id"], text=TYPED, provider_text=payload, lang="zh")
    try:
        progress = brand._progress()
        assert progress["phase"] == "need_card1"
        assert progress["shapes"] == {}
        assert brand._grant_of(1) is None and brand._grant_of(2) is None and brand._grant_of(3) is None
        result = await rig.p.send(
            TurnRequest(chat_id=chat["id"], user_text=payload, lang="zh",
                        mcp_endpoint="http://x/mcp", model="m", goal_text=TYPED),
            emit, TurnHandle())
        guard = paid_guard.TURNS[chat["id"]]
        progress = brand._progress()
        snapshot = {"phase": progress["phase"], "shapes": dict(progress.get("shapes") or {})}
    finally:
        brand.reset_brand_progress_scope(scope)
        paid_guard.end_turn(chat["id"])
        BOT_CHAT_ID.reset(token)
        ACTIVE_TURNS.pop(chat["id"], None)
    return {
        "result": result,
        "events": events,
        "paid": paid,
        "submits": submits,
        "confirms": rig.confirms,
        "requests": rig.requests,
        "guard": guard,
        "payload": payload,
        "phase": snapshot["phase"],
        "shapes": snapshot["shapes"],
        "order": order,
    }


def _user_text(requests) -> str:
    for messages in requests:
        for message in messages:
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                if "brand-identity-director" in message["content"]:
                    return message["content"]
    return ""


@pytest.mark.asyncio
async def test_each_confirmed_stage_dispatches_its_images_immediately(monkeypatch):
    """Start dispatches that stage before another quote is asked.

    Moodboard, the three logos, and the four deliverables each go out in the
    same confirmation. No second card is inserted in front of them.
    """
    out = await _run(monkeypatch, _positive_script)
    assert out["order"] == [
        ("confirm", 1),
        ("generate", "moodboard"),
        ("confirm", 2),
        ("generate", "logo_a"),
        ("generate", "logo_b"),
        ("generate", "logo_c"),
        ("confirm", 3),
        ("generate", "spec"),
        ("generate", "cup"),
        ("generate", "bag"),
        ("generate", "storefront"),
    ]
    assert [stage for kind, stage in out["order"] if kind == "confirm"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_stage_plan_updates_submit_all_eight_and_a_repeat_does_not(monkeypatch):
    out = await _run(monkeypatch, _positive_script)
    seen = _user_text(out["requests"])
    assert out["payload"] in seen
    assert "call update_plan with exactly these three items" in seen
    slots = [row["slot"] for row in out["paid"]]
    assert slots == list(ALL_SLOTS)
    assert out["submits"] == []
    assert len(out["confirms"]) == 3
    assert all(spec.get("brand_confirm") is True for spec in out["confirms"])
    assert set(out["shapes"]) == set(ALL_SLOTS)
    assert out["phase"] == "done"
    guard = out["guard"]
    assert guard.cap == 4 and guard.user_count == 0
    assert guard.used == {
        brand.PLAN_MOODBOARD: 1,
        brand.PLAN_LOGOS: 3,
        brand.PLAN_DELIVERABLES: 4,
    }
    repeat = [event.text for event in out["events"]
              if event.t == "tool_result" and event.name == "generate_image" and event.is_error]
    assert repeat and all("已经提交过了" in text for text in repeat)
    assert not out["result"].error


@pytest.mark.asyncio
async def test_without_a_stage_switch_the_fifth_image_stops(monkeypatch):
    out = await _run(monkeypatch, _no_switch_script)
    slots = [row["slot"] for row in out["paid"]]
    assert slots == ["moodboard", "logo_a", "logo_b", "logo_c"]
    assert out["submits"] == []
    assert len(out["confirms"]) == 3
    guard = out["guard"]
    assert guard.cap == 4 and guard.user_count == 0
    assert guard.plan_item == ""
    assert guard.used == {"": 4}
    assert guard.stopped
    stopped = [event.text for event in out["events"]
               if event.t == "tool_result" and event.name == "generate_image" and "已生成 4 张" in event.text]
    assert stopped
    assert "spec" not in out["shapes"]
    assert set(out["shapes"]) == {"moodboard", "logo_a", "logo_b", "logo_c"}
