"""#419 stop during generation ($0: scripted LLM + MCP, nothing leaves the process).
Product ruling: stop skips unsubmitted steps (no charge, no new placeholder); already-submitted jobs finish,
fill their placeholders and are charged; no stop label; the charge note shows only when a paid request was sent."""
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
    assert card(ev)["submitted"] == 0 and not r.paid_mcp()   # no label, no charge note


async def test_submitted_only_on_plain_user_stop(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("add_text", {"text": "x"})), {"choices": [{"message": {"content": "ok"}}]}],
            store=store)
    res, ev = await r.send("加字")
    assert stop_of(res)["reason"] == "done" and "submitted" not in card(ev)


async def test_stop_in_race_window_counts_sent_request(monkeypatch, store):
    """The stop lands while the paid request is in flight and the call fails/aborts unacknowledged:
    the request was sent (may be charged), so it still counts and the charge note shows."""
    h = TurnHandle()

    def mcp(name, a, i):
        if name == "generate_image":
            h.stop_requested = True
            raise ConnectionError("stopped before the job id came back")
        return json.dumps({"ok": True})
    r = Rig(monkeypatch, lambda m, n: calls(_gen(n)), store=store, mcp=mcp, prices={"generate_image": 0.01})
    res, ev = await r.send("画一张猫", handle=h)
    assert stop_of(res)["reason"] == "user_stop" and res.aborted
    assert card(ev)["submitted"] == 1


def test_panel_stop_ui_has_no_label_or_tooltip_and_fades():
    """Final ruling: no 已停止/已终止 label, no tooltip on the stop chip; partial output greys ~1.5s then returns."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    panel = (root / "src/ui/AgentPanel.tsx").read_text()
    assert "agentPanel.stopped" not in panel and "stopTooltip" not in panel
    assert "ca-chat__bot--stopping" in panel and "STOP_FADE_MS = 1500" in panel
    assert "stoppedSubmitted(m) > 0" in panel                     # charge note only when submitted > 0
    for loc in ("en", "zh"):
        text = (root / f"src/locales/{loc}.json").read_text()
        assert "agentPanel.stopTooltip" not in text and "chatMessage.stoppedStep" not in text
        assert "chatMessage.stoppedSubmittedNote" in text
