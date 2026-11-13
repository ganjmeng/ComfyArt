"""#944 HOLD (comment 6840583182): agent-loop acceptance on a mocked WaveSpeed job.

A 933s generation plus earlier conversation must not hit the 15-minute run cap.
Past 30 minutes with the job still running, the still-generating copy is shown
(not the stuck card, no 「继续生成」). $0 — no real WaveSpeed submit.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.api.mcp_tools.canvas import WAIT_MAX_S
from ComfyArt.bot.local_llm import _MAX_WAIT_SLICES
from ComfyArt.bot.run_budget import BudgetLimits, ProgressTracker, RunBudget

from test_agent_budget_391 import Clock, Rig, calls, card, reply, stop_of


ZH_STILL = "图片还在生成，生成好后会自动出现在画布上，不会重复扣费。"
EN_STILL = "The image is still generating. It will appear on the canvas when it's ready, with no extra charge."


def test_wait_generation_timing_covers_30_min():
    """One MCP wait_generation blocks up to 170s; poll count and stage cap cover 30 min."""
    assert WAIT_MAX_S == 170
    assert _MAX_WAIT_SLICES == 12
    # 12 slices × 170s = 2040s ≈ 34 min, so _wait_stage_done must also cap at wait_max_s.
    assert _MAX_WAIT_SLICES * WAIT_MAX_S > ProgressTracker.wait_max_s
    assert ProgressTracker.wait_max_s == 30 * 60
    # wait_max_polls counts model-level observations after a stage returns, not inner 170s slices.
    # 120 such polls would cover well past 30 min even at 170s each; the 30 min clock fires first.
    assert ProgressTracker.wait_max_polls * WAIT_MAX_S >= ProgressTracker.wait_max_s
    assert ProgressTracker.wait_max_polls == 120
    assert ProgressTracker.readonly_max == 8


def test_pause_wall_freezes_the_run_clock():
    clk = Clock()
    b = RunBudget(BudgetLimits(tokens=10000, credits=5, wall_s=900, hard_steps=300), clock=clk)
    clk.t += 180
    b.tick()
    assert b.used.wall_s == pytest.approx(180)
    b.pause_wall()
    clk.t += 933
    b.tick()
    assert b.used.wall_s == pytest.approx(180)
    assert b.exhausted() is None
    b.resume_wall()
    clk.t += 10
    b.tick()
    assert b.used.wall_s == pytest.approx(190)
    snap = b.snapshot()
    assert snap["wall_paused"] is False
    b.pause_wall()
    assert RunBudget.restore(b.snapshot(), clock=clk)._paused is True


@pytest.fixture
def store():
    from test_agent_budget_391 import store as _store
    # The imported fixture is a pytest fixture object; use the same store setup inline.
    from ComfyArt.api.run_store_sqlite import SqliteRunStore
    from ComfyArt.bot.run_store import set_run_store
    s = SqliteRunStore()
    set_run_store(s)
    yield s
    set_run_store(None)


async def test_933s_job_delivers_once_and_does_not_hit_time_cap(monkeypatch, store):
    """3 min of chat + 933s wait on a charged job: image lands, one submit, no 时长上限."""
    r = None

    def script(m, n):
        if n == 0:
            r.clock.t += 180
            return calls(("generate_image", {"prompt": "banner", "model": "m"}))
        if n == 1:
            return calls(("wait_generation", {"ids": ["holder1"]}))
        return reply("好了")

    def mcp(name, a, i):
        if name == "generate_image":
            return json.dumps({"ids": ["holder1"], "note": "call wait_generation"})
        if name == "wait_generation":
            r.clock.t += 933
            return json.dumps({
                "status": "done",
                "results": [{
                    "id": "holder1", "status": "done", "placed": True,
                    "generation_succeeded": True, "delivered": 1,
                    "urls": ["http://x/out.png"], "shapes": ["shape:1"],
                }],
            })
        return json.dumps({})

    r = Rig(monkeypatch, script, store=store, prices={"generate_image": 0.09}, mcp=mcp)
    res, ev = await r.send("画一张banner", goal="")
    s = stop_of(res)
    assert s["reason"] == "done", s
    assert s.get("sub") not in {"time", "timeout", "readonly_limit"}
    assert len(r.paid_mcp()) == 1
    # Conversation time counts; the 933s wait must not.
    wall = res.run["log"]["wall_s"]
    assert wall < 900, res.run["log"]
    assert wall == pytest.approx(180, abs=5)
    text = json.dumps(card(ev), ensure_ascii=False) if any(e.t == "run_stop" for e in ev) else json.dumps(s, ensure_ascii=False)
    assert "达到单次时长上限" not in text
    assert "任务卡住了" not in text
    assert res.error in (None, "")


async def test_past_30_min_still_generating_card_not_stuck(monkeypatch, store):
    """A job still running after 30 min shows the HOLD copy, no stuck card, no 继续生成."""
    r = None

    def script(m, n):
        if n == 0:
            return calls(("generate_image", {"prompt": "banner", "model": "m"}))
        if n == 1:
            return calls(("wait_generation", {"ids": ["holder1"]}))
        return reply("好了")

    def mcp(name, a, i):
        if name == "generate_image":
            return json.dumps({"ids": ["holder1"]})
        if name == "wait_generation":
            r.clock.t += 1801
            return json.dumps({
                "status": "running",
                "results": [{"id": "holder1", "status": "running"}],
            })
        return json.dumps({})

    r = Rig(monkeypatch, script, store=store, prices={"generate_image": 0.09}, mcp=mcp)
    res, ev = await r.send("画一张banner", goal="")
    s = stop_of(res)
    assert (s["reason"], s.get("sub")) == ("stuck", "timeout"), s
    assert len(r.paid_mcp()) == 1
    assert res.error in (None, "")
    c = card(ev)
    assert c["copy"]["key"] == "stuck:timeout"
    assert c["copy"]["zh"]["title"] == ZH_STILL
    assert c["copy"]["en"]["title"] == EN_STILL
    assert c["copy"]["zh"]["primary"] is None
    assert c["copy"]["en"]["primary"] is None
    assert c["copy"]["zh"]["body"] in (None, "")
    assert c.get("can_continue") is False
    blob = json.dumps(c, ensure_ascii=False)
    assert "继续生成" not in blob
    assert "任务卡住了" not in blob
    assert "已停止" not in blob
    assert "Continue generating" not in blob
