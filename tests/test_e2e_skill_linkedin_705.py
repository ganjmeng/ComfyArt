"""#705 e2e — linkedin-banner chain through the real budget agent loop (bot/agent_loop.py) with a scripted LLM and
mocked MCP / WaveSpeed (no paid call). Covers the happy chain and the #705 repro (6 skill loads -> empty id)."""
from __future__ import annotations

import json

import pytest

from ComfyArt.api.bot_send import compose_provider_text
from tests.test_agent_budget_391 import Rig, _known_low_price, calls, card, reply, stop_of, store  # noqa: F401

SKILL = "LinkedIn Banner"
READ = ("skill", {"action": "read", "name": SKILL})
EMPTY_ERR = "[error] ValueError: [non-retryable] skill read needs a non-empty id or name (e.g. id=\"linkedin-banner\")"


def _mcp(name, args, i):
    if name == "skill":
        if not (args.get("id") or args.get("name")):
            return EMPTY_ERR
        return json.dumps({"id": "linkedin-banner", "name": SKILL, "instructions": "Ship 1584x396 banners."})
    if name == "generate_image":
        return json.dumps({"id": f"shape:{i}", "job": f"job{i}"})
    return json.dumps({"id": f"shape:{i}"})


def test_prompt_names_the_skill_for_the_read() -> None:
    text = compose_provider_text("Banner for a data engineer", skill_name=SKILL)
    assert "action='read'" in text and f"name={SKILL!r}" in text


async def test_linkedin_banner_chain_happy_path(monkeypatch, store):  # noqa: F811
    script = [calls(READ), calls(("generate_image", {"prompt": "1584x396 LinkedIn banner", "width": 1584, "height": 396})),
              calls(("wait_generation", {"ids": ["job2"]})), reply("Done")]
    r = Rig(monkeypatch, script, store=store, mcp=_mcp)
    res, _ = await r.send(compose_provider_text("Banner for a data engineer", skill_name=SKILL))
    assert stop_of(res)["reason"] == "done", stop_of(res)
    assert [c[0] for c in r.mcp] == ["skill", "generate_image", "wait_generation"]
    assert r.mcp[0][1] == {"action": "read", "name": SKILL}


async def test_linkedin_banner_705_repro_stops_on_empty_id(monkeypatch, store):  # noqa: F811
    """#705: the model re-reads the skill, gets nudged, then drops the name. Before: retried in a loop.
    After: the first empty read is a hard, non-retryable stop."""
    def script(m, n):
        return calls(READ) if n < 3 else calls(("skill", {"action": "read", "id": ""}))
    r = Rig(monkeypatch, script, store=store, mcp=_mcp)
    res, events = await r.send(compose_provider_text("Banner", skill_name=SKILL))
    s = stop_of(res)
    assert (s["reason"], s["sub"]) == ("stuck", "non_retryable"), s
    empties = [c for c in r.mcp if c[0] == "skill" and not (c[1].get("id") or c[1].get("name"))]
    assert len(empties) == 1                       # never retried
    assert not [c for c in r.mcp if c[0] == "generate_image"]  # nothing paid


async def test_same_tool_guard_stops_varied_generate_without_progress(monkeypatch, store):  # noqa: F811
    """P1: same tool >3 steps in a row with no new artifact -> hard stop (no nudge)."""
    r = Rig(monkeypatch, lambda m, n: calls(("generate_image", {"prompt": f"v{n}"})), store=store,
            mcp=lambda name, a, i: f"queued attempt {i}")
    res, _ = await r.send("Banner")
    s = stop_of(res)
    assert s["sub"] == "same_tool", s
    assert len(r.paid_mcp()) == 4
