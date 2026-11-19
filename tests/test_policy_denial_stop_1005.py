"""Policy denials stop on the first result. Other non-retryable errors stop on the second.

No further model POST happens after the stop. No network.
"""
from __future__ import annotations

import pytest

from ComfyArt.api import chat_store
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy
from test_agent_budget_391 import calls, reply


DENIAL = "PermissionError: controlled first turn: MCP side effects prohibited"
OTHER = "[tool error] ValueError: [non-retryable] this call cannot succeed"


async def _turn(monkeypatch, *, results, script, budget_loop=True):
    chat = chat_store.create_chat(user="default", project="mock-policy", provider="local-llm")
    provider = LocalLlmProvider(base_url=lambda: "http://mock-no-network/v1")
    posts, trace = [], []

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if (json_body or {}).get("method") == "tools/list":
            return {"result": {"tools": [{"name": "get_canvas", "inputSchema": {"type": "object", "properties": {}}}]}}
        if not str(url).endswith("/chat/completions"):
            return {"data": [{"id": "mock-policy", "context_length": 32000}]}
        posts.append(json_body["messages"])
        return script[len(posts) - 1]

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
        chat_id=chat["id"], user_text="Look at the canvas.", goal_text="Look at the canvas.",
        lang="en", mcp_endpoint="http://mock-no-network/mcp", model="mock-policy"), emit, TurnHandle())
    return result, posts, trace


@pytest.mark.asyncio
@pytest.mark.parametrize("budget_loop", [True, False])
async def test_policy_denial_stops_on_the_first_result(monkeypatch, budget_loop):
    result, posts, trace = await _turn(
        monkeypatch, budget_loop=budget_loop,
        results=[DENIAL, DENIAL],
        script=[calls(("get_canvas", {})), calls(("get_canvas", {})), reply("must not be requested")])
    assert trace == ["get_canvas"]
    assert len(posts) == 1
    if budget_loop:
        assert result.run["stop"]["code"] == "stuck:non_retryable"
    else:
        assert result.run is None or result.run["stop"]["code"] == "stuck:non_retryable"


@pytest.mark.asyncio
async def test_other_non_retryable_stops_on_the_second_result(monkeypatch):
    result, posts, trace = await _turn(
        monkeypatch,
        results=[OTHER, OTHER, "must not run"],
        script=[calls(("get_canvas", {})), calls(("get_canvas", {})), reply("must not be requested")])
    assert trace == ["get_canvas", "get_canvas"]
    assert len(posts) == 2
    assert OTHER in str(posts[1])
    assert result.run["stop"]["code"] == "stuck:non_retryable"


@pytest.mark.asyncio
async def test_ordinary_tool_errors_do_not_end_the_turn(monkeypatch):
    result, posts, trace = await _turn(
        monkeypatch,
        results=["ValueError: temporary", "ValueError: temporary again"],
        script=[calls(("get_canvas", {})), calls(("get_canvas", {})), reply("finished after ordinary errors")])
    assert trace == ["get_canvas", "get_canvas"]
    assert len(posts) == 3
    assert result.run["stop"]["reason"] == "done"
