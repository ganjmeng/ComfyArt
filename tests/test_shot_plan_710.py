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
    shots = shot_plan.build_shots(4, 0, "同参考图街景，街道和建筑完整可读，背景保持明亮可读")
    assert len(shots) == 4
    angles = [s.angle for s in shots]
    assert len(angles) == len(set(angles))
    fronts = [s for s in shots if s.angle.startswith("0°")]
    assert len(fronts) <= 1
    # Gold ex-01 is a near-frontal full-length standing frame and may be centered.
    assert fronts and "允许居中" in fronts[0].composition
    poses = " ".join(s.pose for s in shots)
    angles = " ".join(s.angle for s in shots)
    cuts = " ".join(s.cut for s in shots)
    assert "回头" in poses or "回头" in angles
    assert "侧脸" in poses or "正侧面" in angles
    assert "低头" in poses or "低头" in angles
    assert "双脚完整入画" in cuts
    for s in shots:
        line = s.zh()
        for token in ("景别：", "角度：", "机位：", "姿态：", "构图：", "焦段：", "光：", "场景：", "°", "mm"):
            assert token in line, token
        for bare in ("full body", "waist-up", "半身", "全身"):
            assert bare not in line
        assert "软阴影" not in s.light and "顺光软光" not in s.light
        assert "压暗" not in s.scene
        assert "硬" in s.light and "斑驳" in s.light
        assert shot_plan.trace_ok(s.prompt_en, s)
    spec = shot_plan.ask_spec(shots)
    # #971: the plan card is a real question spec (questions[]), not legacy prompt+options.
    assert "prompt" not in spec and "options" not in spec, spec
    question = spec["questions"][0]
    assert question["id"] == shot_plan.QUESTION_ID == "plan"
    assert question["prompt"].count("\n") == 4
    assert question["prompt"].rstrip().endswith("是否生成这 4 张？")
    assert [o["label"] for o in question["options"]] == ["开始生成", "换一组方案"]
    assert question["allow_other"] is True and spec["allow_skip"] is True
    assert spec["page_count"] == 1
    # Validated exactly like ask_user: the stored spec mirrors prompt/options and has questions[].
    canonical = bot_asks.validate_spec(spec)
    assert canonical["questions"][0]["id"] == "plan"
    assert canonical["prompt"] == question["prompt"]
    assert canonical["options"] == question["options"]
    assert canonical["kind"] == "question" and canonical["allow_skip"] is True


def test_regenerate_differs_and_stays_in_the_pool():
    scene = "同参考图场景，街道和建筑完整可读，背景保持明亮可读"
    first = shot_plan.build_shots(4, 0, scene)
    second = shot_plan.build_shots(4, 1, scene)
    assert [s.zh() for s in first] != [s.zh() for s in second]
    assert {s.angle for s in first}.isdisjoint({s.angle for s in second})
    assert sum(1 for s in second if s.angle.startswith("0°")) <= 1


def test_other_text_lands_in_the_new_plan_and_prompt():
    shots = shot_plan.build_shots(4, 1, "同参考图场景，街道和建筑完整可读，背景保持明亮可读", "加一条红围巾")
    assert all("加一条红围巾" in s.zh() and "加一条红围巾" in s.prompt_en for s in shots)


def test_single_image_internal_plan_does_not_raise_and_is_not_frontal():
    shots = shot_plan.touch_internal(1)
    assert len(shots) == 1 and not shots[0].angle.startswith("0°")
    assert "三分" in shots[0].composition


def test_choice_letters_and_skip_is_never_a():
    assert shot_plan.choice_of({"status": "answered", "selected": ["generate"]}) == "A"
    # #971: an empty answer is an explicit skip, not a silent A.
    assert shot_plan.choice_of({"status": "answered", "selected": []}) == "S"
    assert shot_plan.choice_of({"status": "answered"}) == "S"
    assert shot_plan.choice_of({"status": "answered", "selected": ["regenerate"]}) == "B"
    assert shot_plan.choice_of({"status": "answered", "selected": [], "other_text": "更近"}) == "C"


def test_fullapp_answer_payloads_validate_against_the_plan_spec():
    """#971: the three Full App Submit payloads (A / 换一组 / 跳过) pass validate_answer."""
    spec = bot_asks.validate_spec(shot_plan.ask_spec(shot_plan.build_shots(4)))
    qid = spec["questions"][0]["id"]
    bot_asks.validate_answer(spec, [], "", {qid: {"selected": ["generate"]}})
    bot_asks.validate_answer(spec, [], "", {qid: {"selected": ["regenerate"]}})
    bot_asks.validate_answer(spec, [], "", {qid: {"selected": []}})      # 跳过: empty answers
    # A legacy spec without questions[] still refuses answers[]; the route never pretends.
    with pytest.raises(ValueError, match=r"answers require questions\[\]"):
        bot_asks.validate_answer({
            "prompt": "p", "options": [{"id": "a", "label": "A"}], "min_selections": 1,
            "max_selections": 1, "allow_other": True, "allow_skip": True,
        }, [], "", {"plan": {"selected": ["a"]}})


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
    shots = shot_plan.build_shots(4, 0, "同参考图街景，街道和建筑完整可读，背景保持明亮可读")
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
    """#971: 跳过 runs the shown plan but is never recorded as an A answer."""
    h = TurnHandle()
    _live(h)
    rig = Rig(monkeypatch, _script(4), store=store, prices={"generate_image": 0.001})

    async def answer():
        ask = await _wait_ask()
        assert _gens(rig) == []
        assert ask.spec["questions"][0]["id"] == shot_plan.QUESTION_ID
        # The Full App 跳过 payload: answered, one empty per-question answer.
        bot_asks.resolve_ask(ask.id, "answered", selected=[], answers={
            shot_plan.QUESTION_ID: {"selected": []}})

    task = asyncio.create_task(answer())
    res, _ = await rig.send(compose_provider_text("同参考图", skill_name=ZH), goal="", handle=h)
    await task
    assert stop_of(res)["reason"] == "done", stop_of(res)
    shots = shot_plan.build_shots(4, 0, "同参考图场景，街道和建筑完整可读，背景保持明亮可读")
    gens = _gens(rig)
    assert len(gens) == 4
    for shot, call in zip(shots, gens):
        assert shot_plan.trace_ok(call[1]["prompt"], shot)
    seen = "\n".join(str(m.get("content")) for req in rig.requests for m in req)
    assert "skipped the shot plan card" in seen
    assert "confirmed the shot plan" not in seen


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
