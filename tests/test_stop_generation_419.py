"""#419 stop during generation ($0: scripted LLM + MCP, nothing leaves the process).
Product ruling: stop skips unsubmitted steps (no charge, no new placeholder); already-submitted jobs finish,
fill their placeholders and are charged; the 「已停止」 row's charge note shows only when jobs were submitted."""
from __future__ import annotations

import json

from ComfyArt.bot.providers import TurnHandle

from test_agent_budget_391 import Rig, calls, card, stop_of, store  # noqa: F401  (fixture)


def _gen(n):
    return ("generate_image", {"prompt": f"p{n}", "model": "m"})


async def test_stop_after_submit_counts_submitted_and_skips_rest(monkeypatch, store):
    h = TurnHandle()

    def mcp(name, a, i):
        if name == "generate_image":
            h.stop_requested = True  # the user stops while the first job is being submitted
            return json.dumps({"ids": [f"shape:g{i}"], "note": "call wait_generation with these ids"})
        return json.dumps({"ok": True})
    r = Rig(monkeypatch, lambda m, n: calls(_gen(n)), store=store, mcp=mcp, prices={"generate_image": 0.01})
    res, ev = await r.send("画两张猫", handle=h)
    assert stop_of(res)["reason"] == "user_stop" and res.aborted
    assert len(r.paid_mcp()) == 1                    # the second step was never submitted
    assert card(ev)["submitted"] == 1                # -> charge note shows


async def test_stop_skips_unsubmitted_paid_calls_in_same_step(monkeypatch, store):
    h = TurnHandle()

    def mcp(name, a, i):
        if name == "generate_image":
            h.stop_requested = True
            return json.dumps({"ids": [f"shape:g{i}"]})
        return json.dumps({"ok": True})
    r = Rig(monkeypatch, lambda m, n: calls(_gen(0), _gen(1), _gen(2)), store=store, mcp=mcp)
    res, ev = await r.send("画三张猫", handle=h)
    assert stop_of(res)["reason"] == "user_stop"
    assert len(r.paid_mcp()) == 1                    # no placeholder / job for t1, t2
    used = [e.id for e in ev if e.t == "tool_use" and e.name == "generate_image"]
    assert used == ["t0"]                            # skipped steps emit no row and charge nothing
    assert card(ev)["submitted"] == 1


async def test_stop_without_submitted_jobs(monkeypatch, store):
    h = TurnHandle()

    def mcp(name, a, i):
        h.stop_requested = True
        return json.dumps({"id": f"s{i}"})
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), store=store, mcp=mcp)
    res, ev = await r.send("加字", handle=h)
    assert stop_of(res)["reason"] == "user_stop"
    assert card(ev)["submitted"] == 0 and not r.paid_mcp()   # row shows, no charge note


async def test_submitted_only_on_plain_user_stop(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("add_text", {"text": "x"})), {"choices": [{"message": {"content": "ok"}}]}],
            store=store)
    res, ev = await r.send("加字")
    assert stop_of(res)["reason"] == "done" and "submitted" not in card(ev)
