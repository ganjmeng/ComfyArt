"""A repeated policy denial ends the turn before another model POST. No network."""
from __future__ import annotations

import pytest

from ComfyArt.api import chat_store
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy
from test_agent_budget_391 import calls, reply


DENIAL = "PermissionError: controlled first turn: MCP side effects prohibited"


async def _turn(monkeypatch, *, results, script, budget_loop=True):
    chat = chat_store.create_chat(user="default", project="mock-policy", provider="local-llm")
    cid = chat["id"]
    provider = LocalLlmProvider(base_url=lambda: "http://mock-no-network/v1")
    seen, trace = [], []

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if (json_body or {}).get("method") == "tools/list":
            return {"result": {"tools": [{"name": "get_canvas", "inputSchema": {"type": "object", "properties": {}}}]}}
        if not str(url).endswith("/chat/completions"):
            return {"data": [{"id": "mock-policy", "context_length": 32000}]}
        seen.append(json_body["messages"])
        return script[len(seen) - 1]

    async def mcp_call(session, endpoint, name, arguments):
        trace.append(name)
        return results[len(trace) - 1], []

    async def window(*_a):
        return 32000

    async def no_price(*_a, **_k):
        return None

    async def no_models(*_a):
        return []

    env = {} if budget_loop else {"COMFYART_AGENT_BUDGET_LOOP": "0"}
    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", mcp_call)
    monkeypatch.setattr(provider, "_context_window", window)
    monkeypatch.setattr(provider, "_price_call", no_price)
    monkeypatch.setattr(provider, "_price_one", no_price)
    monkeypatch.setattr(provider, "_models_for", no_models)
    monkeypatch.setattr(provider, "_run_store", lambda: None)
    monkeypatch.setattr(provider, "_run_policy", lambda: resolve_policy(env=env))

    async def emit(_event):
        return None

    result = await provider.send(TurnRequest(
        chat_id=cid, user_text="Look at the canvas.", goal_text="Look at the canvas.",
        lang="en", mcp_endpoint="http://mock-no-network/mcp", model="mock-policy"), emit, TurnHandle())
    return result, seen, trace


@pytest.mark.asyncio
@pytest.mark.parametrize("budget_loop", [True, False])
async def test_two_policy_denials_make_one_extra_post_then_stop(monkeypatch, budget_loop):
    result, seen, trace = await _turn(
        monkeypatch, budget_loop=budget_loop,
        results=[DENIAL, DENIAL, "should not run"],
        script=[calls(("get_canvas", {})), calls(("get_canvas", {})), reply("should not be requested")])
    assert trace == ["get_canvas", "get_canvas"]
    assert len(seen) == 2
    assert DENIAL in str(seen[1])
    if budget_loop:
        assert result.run["stop"]["code"] == "blocked:policy_denied_repeat"
    else:
        assert "policy denial happened twice" in result.error
        assert result.run is None or (result.run or {}).get("stop", {}).get("code") != "done"


@pytest.mark.asyncio
async def test_ordinary_tool_errors_do_not_end_the_turn(monkeypatch):
    result, seen, trace = await _turn(
        monkeypatch,
        results=["ValueError: temporary", "ValueError: temporary again"],
        script=[calls(("get_canvas", {})), calls(("get_canvas", {})), reply("finished after ordinary errors")])
    assert trace == ["get_canvas", "get_canvas"]
    assert len(seen) == 3
    assert result.run["stop"]["reason"] == "done"
    assert result.run["stop"]["code"] != "blocked:policy_denied_repeat"
