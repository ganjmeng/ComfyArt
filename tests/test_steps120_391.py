"""#391 tester: a 120-step task must not be cut at step 80 (main stopped at the legacy 80-step cap).
Uses only the provider API that exists on main too, so the same file is red on main and green here."""
from __future__ import annotations

import json

from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest

N = 120


async def test_120_step_task_is_not_cut_at_80(monkeypatch):
    p = LocalLlmProvider(base_url=lambda: "http://x/v1")
    n = {"llm": 0}
    done = []

    async def fake_request(session, method, url, *, headers=None, json_body=None, timeout=None):
        if json_body and "messages" in json_body:
            i = n["llm"]
            n["llm"] += 1
            if i < N:
                tc = {"id": f"c{i}", "function": {"name": "add_text", "arguments": json.dumps({"text": f"line {i}"})}}
                return {"choices": [{"message": {"content": "", "tool_calls": [tc]}}]}
            return {"choices": [{"message": {"content": "好了", "tool_calls": []}}]}
        return {"result": {"tools": [{"name": "add_text"}]}}
    monkeypatch.setattr(p, "_request_json", fake_request)

    async def fake_call(session, endpoint, name, arguments):
        done.append(arguments["text"])
        return json.dumps({"id": f"shape:{len(done)}"}), []
    monkeypatch.setattr(p, "_mcp_call_tool", fake_call)
    if hasattr(p, "_context_window"):
        async def window(*a, **k):
            return 128_000
        monkeypatch.setattr(p, "_context_window", window)

    async def emit(ev: BotEvent):
        pass
    res = await p.send(TurnRequest(chat_id="c120", user_text="逐行加 120 行字", lang="zh",
                                   mcp_endpoint="http://x/mcp", model="m"), emit, TurnHandle())
    assert len(done) == N, f"stopped after {len(done)} steps: {res.error}"
