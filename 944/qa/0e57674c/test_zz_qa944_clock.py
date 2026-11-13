"""QA #944 @0e57674c: independent Rig repros of the a407cb19 HOLD + extra clock cases ($0)."""
from __future__ import annotations
import json
import pytest
from test_agent_budget_391 import Rig, calls, reply, stop_of
from test_agent_loop_943_hold import store  # noqa: F401

RUN = json.dumps({"status": "running", "results": [{"id": "holder1", "status": "running"}]})
DONE = json.dumps({"status": "done", "results": [{"id": "holder1", "status": "done", "placed": True,
                   "generation_succeeded": True, "delivered": 1, "urls": ["http://x/o.png"], "shapes": ["shape:1"]}]})


async def test_A_wait_running_then_6x400_add_text_hits_budget_time(monkeypatch, store):
    r = None
    def script(m, n):
        if n == 0: return calls(("generate_image", {"prompt": "b", "model": "m"}))
        if n == 1: return calls(("wait_generation", {"ids": ["holder1"]}))
        if n <= 7: return calls(("add_text", {"text": f"t{n}"}))
        return reply("done")
    def mcp(name, a, i):
        if name == "generate_image": return json.dumps({"ids": ["holder1"]})
        if name == "wait_generation": r.clock.t += 10; return RUN
        if name == "add_text": r.clock.t += 400
        return json.dumps({})
    r = Rig(monkeypatch, script, store=store, prices={"generate_image": 0.09}, mcp=mcp)
    res, _ = await r.send("draw", goal="")
    s = stop_of(res); w = res.run["log"]["wall_s"]
    print("A", s, w)
    assert (s["reason"], s.get("dimension")) == ("budget", "time"), s
    assert w == pytest.approx(1200, abs=5)
    assert len(r.paid_mcp()) == 1


async def test_B_mixed_wait_add_text_5x400_counts_full(monkeypatch, store):
    r = None
    def script(m, n):
        if n == 0: return calls(("generate_image", {"prompt": "b", "model": "m"}))
        if n <= 5: return calls(("wait_generation", {"ids": ["holder1"]}), ("add_text", {"text": f"t{n}"}))
        return reply("done")
    def mcp(name, a, i):
        if name == "generate_image": return json.dumps({"ids": ["holder1"]})
        if name == "wait_generation": return RUN
        if name == "add_text": r.clock.t += 400
        return json.dumps({})
    r = Rig(monkeypatch, script, store=store, prices={"generate_image": 0.09}, mcp=mcp)
    res, _ = await r.send("draw", goal="")
    s = stop_of(res); w = res.run["log"]["wall_s"]
    print("B", s, w)
    assert w >= 1200, w
    assert (s["reason"], s.get("dimension")) == ("budget", "time"), s
    assert len(r.paid_mcp()) == 1


async def test_C_pure_waits_excluded_933s_plus_3min_done(monkeypatch, store):
    r = None
    waits = [0]
    def script(m, n):
        r.clock.t += 60        # each LLM request: 60s of conversation (3 requests -> 180s)
        if n == 0: return calls(("generate_image", {"prompt": "b", "model": "m"}))
        if waits[0] < 4: return calls(("wait_generation", {"ids": ["holder1"]}))
        return reply("好了")
    def mcp(name, a, i):
        if name == "generate_image": return json.dumps({"ids": ["holder1"]})
        if name == "wait_generation":
            waits[0] += 1
            r.clock.t += 170 if waits[0] < 4 else 933 - 510
            return RUN if waits[0] < 4 else DONE
        return json.dumps({})
    r = Rig(monkeypatch, script, store=store, prices={"generate_image": 0.09}, mcp=mcp)
    res, _ = await r.send("draw", goal="")
    s = stop_of(res); w = res.run["log"]["wall_s"]
    print("C", s, w, waits)
    assert s["reason"] == "done", s
    assert w == pytest.approx(180, abs=5), w
    assert len(r.paid_mcp()) == 1 and waits[0] == 4


async def test_D_exception_inside_wait_resumes_clock(monkeypatch, store):
    r = None
    def script(m, n):
        if n == 0: return calls(("generate_image", {"prompt": "b", "model": "m"}))
        if n == 1: return calls(("wait_generation", {"ids": ["holder1"]}))
        if n <= 4: return calls(("add_text", {"text": f"t{n}"}))
        return reply("done")
    def mcp(name, a, i):
        if name == "generate_image": return json.dumps({"ids": ["holder1"]})
        if name == "wait_generation":
            r.clock.t += 100
            return RuntimeError("boom inside wait")
        if name == "add_text": r.clock.t += 400
        return json.dumps({})
    r = Rig(monkeypatch, script, store=store, prices={"generate_image": 0.09}, mcp=mcp)
    res, _ = await r.send("draw", goal="")
    s = stop_of(res); w = res.run["log"]["wall_s"]
    print("D", s, w)
    assert w >= 1200 and w < 1300, w          # 100s wait excluded, 3x400 add_text counted
    assert (s["reason"], s.get("dimension")) == ("budget", "time"), s


async def test_E_exception_propagating_from_dispatch_resumes(monkeypatch, store):
    """A BaseException-free hard error raised by _dispatch_tools itself must still leave the clock running."""
    from ComfyArt.bot.run_budget import RunBudget
    seen = {}
    orig_resume = RunBudget.resume_wall
    def spy(self):
        if self._paused: seen["resumed"] = seen.get("resumed", 0) + 1
        return orig_resume(self)
    monkeypatch.setattr(RunBudget, "resume_wall", spy)
    r = None
    def script(m, n):
        if n == 0: return calls(("generate_image", {"prompt": "b", "model": "m"}))
        if n == 1: return calls(("wait_generation", {"ids": ["holder1"]}))
        return reply("done")
    r = Rig(monkeypatch, script, store=store, prices={"generate_image": 0.09},
            mcp=lambda n, a, i: json.dumps({"ids": ["holder1"]}) if n == "generate_image" else RUN)
    async def boom(*a, **k):
        if any("wait_generation" in json.dumps(tc) for tc in (a[0] if a else k.get("tool_calls", []))):
            raise ValueError("dispatch blew up")
        return await orig(*a, **k)
    orig = r.p._dispatch_tools
    monkeypatch.setattr(r.p, "_dispatch_tools", boom)
    try:
        res, _ = await r.send("draw", goal="")
        print("E", stop_of(res) if res.run else res.error)
    except ValueError:
        pass
    assert seen.get("resumed", 0) >= 1, seen
