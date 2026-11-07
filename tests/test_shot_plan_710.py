"""#710 plan card (module + scripted agent, $0). Angle pool #708. No WaveSpeed / LLM spend.

F.1–F.8 and F.11 run through the real budget loop with a live ask. F.12's abort is the same loop.
"""
from __future__ import annotations

import asyncio

import pytest

from ComfyArt.api import bot_asks
from ComfyArt.api.bot_send import compose_provider_text
from ComfyArt.api.bot_turns import ACTIVE_TURNS, _TurnState
from ComfyArt.bot import shot_plan
from ComfyArt.bot.providers import TurnHandle
from test_agent_budget_391 import Rig, calls, reply, stop_of, store  # noqa: F401

ZH = "电商同场景角色姿势裂变"
EN = "Same-Scene Pose Fission"


def setup_function():
    shot_plan.internal_calls = 0
    ACTIVE_TURNS.clear()
    bot_asks.PENDING.clear()


def teardown_function():
    ACTIVE_TURNS.clear()
    bot_asks.PENDING.clear()


def test_default_batch_fields_and_angle_pool():
    shots = shot_plan.build_shots(4, 0, "同参考图街景，背景压暗")
    assert len(shots) == 4
    angles = [s.angle for s in shots]
    assert len(angles) == len(set(angles))
    fronts = [s for s in shots if s.angle.startswith("0°")]
    assert len(fronts) <= 1
    assert fronts and "三分" in fronts[0].composition and "不居中" in fronts[0].composition
    for s in shots:
        line = s.zh()
        for token in ("景别：", "角度：", "机位：", "姿态：", "构图：", "焦段：", "光：", "场景：", "°", "mm", "三分", "不居中"):
            assert token in line, token
        for bare in ("full body", "waist-up", "半身", "全身"):
            assert bare not in line
        assert shot_plan.trace_ok(s.prompt_en, s)
    spec = shot_plan.ask_spec(shots)
    assert spec["prompt"].count("\n") == 4
    assert spec["prompt"].rstrip().endswith("是否生成这 4 张？")
    assert [o["label"] for o in spec["options"]] == ["开始生成", "换一组方案"]
    assert spec["allow_other"] is True and spec["allow_skip"] is True


def test_regenerate_differs_and_stays_in_the_pool():
    scene = "同参考图场景，背景压暗"
    first = shot_plan.build_shots(4, 0, scene)
    second = shot_plan.build_shots(4, 1, scene)
    assert [s.zh() for s in first] != [s.zh() for s in second]
    assert {s.angle for s in first}.isdisjoint({s.angle for s in second})
    assert all(not s.angle.startswith("0°") or ("三分" in s.composition and "不居中" in s.composition) for s in second)


def test_other_text_lands_in_the_new_plan_and_prompt():
    shots = shot_plan.build_shots(4, 1, "同参考图场景，背景压暗", "加一条红围巾")
    assert all("加一条红围巾" in s.zh() and "加一条红围巾" in s.prompt_en for s in shots)


def test_single_image_internal_plan_does_not_raise_and_is_not_frontal():
    shots = shot_plan.touch_internal(1)
    assert len(shots) == 1 and not shots[0].angle.startswith("0°")
    assert "三分" in shots[0].composition


def test_choice_skip_is_a_and_letters():
    assert shot_plan.choice_of({"status": "answered", "selected": ["generate"]}) == "A"
    assert shot_plan.choice_of({"status": "answered", "selected": []}) == "A"
    assert shot_plan.choice_of({"status": "answered", "selected": ["regenerate"]}) == "B"
    assert shot_plan.choice_of({"status": "answered", "selected": [], "other_text": "更近"}) == "C"


def _live(handle: TurnHandle):
    ACTIVE_TURNS["c"] = _TurnState(handle, "c", "m-plan")


async def _wait_ask(timeout=5.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        pending = [a for a in bot_asks.PENDING.values() if a.chat_id == "c"]
        if pending:
            return pending[0]
        await asyncio.sleep(0.02)
    raise AssertionError("plan card did not open")


def _gens(rig: Rig):
    return [c for c in rig.mcp if c[0] == "generate_image"]


def _script(n):
    def script(messages, i):
        if i < n:
            return calls(("generate_image", {"prompt": "placeholder"}))
        return reply("好了")
    return script


async def _run(monkeypatch, store, text, *, goal, skill=ZH, script_n=4, handle=None):
    h = handle or TurnHandle()
    _live(h)
    rig = Rig(monkeypatch, _script(script_n), store=store, prices={"generate_image": 0.001})
    res, events = await rig.send(compose_provider_text(text, skill_name=skill), goal=goal, handle=h)
    return rig, res, events, h


async def test_confirm_a_binds_n_prompts_and_never_generates_early(monkeypatch, store):  # noqa: F811
    h = TurnHandle()
    _live(h)
    rig = Rig(monkeypatch, _script(4), store=store, prices={"generate_image": 0.001})

    async def answer():
        ask = await _wait_ask()
        assert _gens(rig) == []  # card is up: generate_image still 0
        lines = [ln for ln in ask.spec["prompt"].splitlines() if ln.startswith("1.") or ln[:2].rstrip(".").isdigit() or ln[0].isdigit()]
        plan = [ln for ln in ask.spec["prompt"].splitlines() if not ln.startswith("是否生成")]
        assert len(plan) == 4 and ask.spec["prompt"].rstrip().endswith("是否生成这 4 张？")
        bot_asks.resolve_ask(ask.id, "answered", selected=["generate"])

    task = asyncio.create_task(answer())
    res, _ = await rig.send(compose_provider_text("同参考图街景", skill_name=ZH), goal="", handle=h)
    await task
    assert stop_of(res)["reason"] == "done", stop_of(res)
    gens = _gens(rig)
    assert len(gens) == 4
    shots = shot_plan.build_shots(4, 0, "同参考图街景，背景压暗")
    for shot, call in zip(shots, gens):
        assert shot_plan.trace_ok(call[1]["prompt"], shot), call[1]["prompt"]
        assert call[1]["skill"] == "pose-fission"


async def test_b_refreshes_plans_without_images_then_a_generates(monkeypatch, store):  # noqa: F811
    h = TurnHandle()
    _live(h)
    rig = Rig(monkeypatch, _script(4), store=store, prices={"generate_image": 0.001})
    seen = []

    async def answer():
        first = await _wait_ask()
        seen.append(first.spec["prompt"])
        assert _gens(rig) == []
        bot_asks.resolve_ask(first.id, "answered", selected=["regenerate"])
        second = await _wait_ask()
        seen.append(second.spec["prompt"])
        assert _gens(rig) == []
        assert seen[0] != seen[1]
        bot_asks.resolve_ask(second.id, "answered", selected=["generate"])

    task = asyncio.create_task(answer())
    res, _ = await rig.send(compose_provider_text("棚拍", skill_name=ZH), goal="", handle=h)
    await task
    assert stop_of(res)["reason"] == "done", stop_of(res)
    assert len(_gens(rig)) == 4
    # variant 1 has no shared angle with variant 0
    a = {ln.split("角度：", 1)[1].split("；", 1)[0] for ln in seen[0].splitlines() if "角度：" in ln}
    b = {ln.split("角度：", 1)[1].split("；", 1)[0] for ln in seen[1].splitlines() if "角度：" in ln}
    assert a.isdisjoint(b) and len(a) == 4 and len(b) == 4


async def test_c_other_text_is_in_the_next_plan_not_an_image(monkeypatch, store):  # noqa: F811
    h = TurnHandle()
    _live(h)
    rig = Rig(monkeypatch, _script(4), store=store, prices={"generate_image": 0.001})

    async def answer():
        first = await _wait_ask()
        bot_asks.resolve_ask(first.id, "answered", selected=[], other_text="加一条红围巾")
        second = await _wait_ask()
        assert "加一条红围巾" in second.spec["prompt"]
        assert _gens(rig) == []
        bot_asks.resolve_ask(second.id, "answered", selected=["generate"])

    task = asyncio.create_task(answer())
    res, _ = await rig.send(compose_provider_text("同参考图", skill_name=EN), goal="", handle=h)
    await task
    assert stop_of(res)["reason"] == "done", stop_of(res)
    assert len(_gens(rig)) == 4
    assert all("加一条红围巾" in c[1]["prompt"] for c in _gens(rig))


async def test_skip_generates_the_current_plan(monkeypatch, store):  # noqa: F811
    h = TurnHandle()
    _live(h)
    rig = Rig(monkeypatch, _script(4), store=store, prices={"generate_image": 0.001})

    async def answer():
        ask = await _wait_ask()
        assert _gens(rig) == []
        bot_asks.resolve_ask(ask.id, "answered", selected=[])

    task = asyncio.create_task(answer())
    res, _ = await rig.send(compose_provider_text("同参考图", skill_name=ZH), goal="", handle=h)
    await task
    assert stop_of(res)["reason"] == "done", stop_of(res)
    shots = shot_plan.build_shots(4, 0, "同参考图场景，背景压暗")
    gens = _gens(rig)
    assert len(gens) == 4
    for shot, call in zip(shots, gens):
        assert shot_plan.trace_ok(call[1]["prompt"], shot)


async def test_single_image_skill_has_no_card_and_internal_plan(monkeypatch, store):  # noqa: F811
    h = TurnHandle()
    _live(h)
    before = shot_plan.internal_calls
    rig = Rig(monkeypatch, _script(1), store=store, prices={"generate_image": 0.001})
    res, _ = await rig.send(compose_provider_text("Banner for a data engineer", skill_name="LinkedIn Banner"), goal="一张横幅", handle=h)
    assert stop_of(res)["reason"] == "done", stop_of(res)
    assert not bot_asks.PENDING
    assert shot_plan.internal_calls == before + 1
    assert len(_gens(rig)) == 1
    # one named image on a plan skill also skips the card
    h2 = TurnHandle()
    _live(h2)
    rig2 = Rig(monkeypatch, _script(1), store=store, prices={"generate_image": 0.001})
    res2, _ = await rig2.send(compose_provider_text("只要 1 张", skill_name=ZH), goal="只要 1 张", handle=h2)
    assert stop_of(res2)["reason"] == "done", stop_of(res2)
    assert len(_gens(rig2)) == 1


async def test_stop_while_the_card_is_open_generates_nothing(monkeypatch, store):  # noqa: F811
    h = TurnHandle()
    _live(h)
    rig = Rig(monkeypatch, _script(4), store=store, prices={"generate_image": 0.001})

    async def stop():
        await _wait_ask()
        assert _gens(rig) == []
        h.stop_requested = True

    task = asyncio.create_task(stop())
    res, _ = await rig.send(compose_provider_text("同参考图", skill_name=ZH), goal="", handle=h)
    await task
    assert res.aborted and stop_of(res)["reason"] == "user_stop"
    assert _gens(rig) == []


async def test_stop_while_running_aborts(monkeypatch, store):  # noqa: F811
    h = TurnHandle()
    _live(h)

    async def answer():
        ask = await _wait_ask()
        bot_asks.resolve_ask(ask.id, "answered", selected=["generate"])

    def mcp(name, args, i):
        if name == "generate_image":
            h.stop_requested = True
        return '{"id": "shape:1"}'

    task = asyncio.create_task(answer())
    rig = Rig(monkeypatch, _script(4), store=store, prices={"generate_image": 0.001}, mcp=mcp)
    res, _ = await rig.send(compose_provider_text("同参考图", skill_name=ZH), goal="", handle=h)
    await task
    assert res.aborted and stop_of(res)["reason"] == "user_stop"
    assert len(_gens(rig)) == 1


def test_ungated_generate_is_refused():
    run = type("R", (), {})()
    run.plan_gate_active = True
    run.shot_confirmed = False
    run.shots = []
    run.shot_cursor = 0
    _args, refuse = shot_plan.bind_generate(run, {"prompt": "early"}, consume=True)
    assert refuse and "generate_image" in refuse
    assert shot_plan.internal_calls >= 0
