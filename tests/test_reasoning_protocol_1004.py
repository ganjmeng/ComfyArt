"""#1004 protocol integration: fake HTTP only; real tool dispatch and SQLite.

These tests deliberately use a test-only bound. They prove no production billing
contract and must not activate a real authorization scope.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import time

import pytest

from ComfyArt.api import db, provider_admin
from ComfyArt.api.run_store_sqlite import SqliteRunStore
from ComfyArt.bot import agent_loop, llm_usd_gate, local_llm
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy
from test_llm_usd_gate import _route


class RestartNow(BaseException):
    """Bypass ordinary exception handlers after a committed step checkpoint."""


def response(cid=None, name=None, args=None, reasoning=None):
    message = {"role": "assistant", "content": "" if cid else "All done."}
    if cid:
        message["tool_calls"] = [{"id": cid, "type": "function", "function": {
            "name": name, "arguments": json.dumps(args or {}),
        }}]
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return {"choices": [{"message": message}]}


@pytest.fixture
def protocol_db(tmp_path, monkeypatch):
    monkeypatch.setenv("COMFYART_LLM_USD_GATE", "1")
    # A distinct physical database, not the shared application data.db.
    path = str(tmp_path / "protocol.sqlite")
    monkeypatch.setattr(db, "app_path", lambda _name: path)
    for key in list(os.environ):
        if key.endswith("_API_KEY") or key in ("OPENAI_TOKEN", "DEEPSEEK_TOKEN"):
            monkeypatch.delenv(key, raising=False)
    yield path
    engine = db._engines.pop(path, None)
    if engine is not None:
        engine.dispose()


class ProtocolRig:
    def __init__(self, monkeypatch, tmp_path, script, *, store, legacy=False):
        self.p = LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")
        self.bodies = []
        self.tools = []
        self.events = []
        self.script = iter(script)
        self.ledger = str(tmp_path / "protocol-ledger.json")
        # Temporary test artifact only; no process-global scope binding.
        if not os.path.exists(self.ledger):
            llm_usd_gate.open_authorized_scope(self.ledger, llm_usd_gate.TWO_DOLLAR_CEILING_NANO)
        policy = resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0" if legacy else "1"})
        monkeypatch.setattr(self.p, "_run_policy", lambda: policy)
        monkeypatch.setattr(self.p, "_run_store", lambda: store)
        monkeypatch.setattr(local_llm, "_RETRY_BACKOFF_S", (0.0, 0.0))

        async def window(*_args):
            return 128_000

        async def no_plan(*_args):
            return None

        monkeypatch.setattr(self.p, "_context_window", window)
        monkeypatch.setattr("ComfyArt.bot.shot_plan.run_plan_card", no_plan)

        async def mcp(_session, _endpoint, name, arguments):
            self.tools.append((name, dict(arguments)))
            if name == "memory":
                assert arguments["action"] == "add"
                return json.dumps({"memory_ids": ["memory-1004"], "added": arguments["text"]}), []
            if name == "add_text":
                return json.dumps({"id": "shape:1004"}), []
            assert name == "get_canvas"
            return json.dumps({"shapes": []}), []

        monkeypatch.setattr(self.p, "_mcp_call_tool", mcp)

        async def transport(_session, _method, url, *, headers, json_body=None, timeout=120):
            assert str(url).endswith("/chat/completions"), url
            body = copy.deepcopy(json_body)
            self.bodies.append(body)
            assert body["model"] == "deepseek-flash"
            assert isinstance(body["max_tokens"], int) and body["max_tokens"] > 0
            # Validate every canonical field from every previous tool round,
            # including exact whitespace and empty canonical values.
            for message in body["messages"]:
                for call in message.get("tool_calls") or []:
                    cid = call["id"]
                    expected = {"memory-call": "", "canvas-call": "  exact canvas thought\n", "text-call": "exact text thought"}
                    if cid in expected:
                        assert message.get("reasoning_content") == expected[cid]
            item = next(self.script)
            if isinstance(item, BaseException):
                raise item
            return copy.deepcopy(item)

        async def request(session, method, url, *, headers, json_body=None, timeout=120):
            if not str(url).endswith("/chat/completions"):
                return {"result": {"tools": [{"name": name} for name in ("memory", "get_canvas", "add_text")]}}
            return await provider_admin.gated_llm_http(
                session, method, url, headers=headers, json_body=json_body, timeout=timeout,
                transport=transport, ledger_path=self.ledger,
                bound_fn=lambda _body, _snapshot: llm_usd_gate.Bound(True, 0, "", "test-only protocol bound"),
            )

        monkeypatch.setattr(self.p, "_request_json", request)
        if legacy:
            # Legacy has no memory boost. Explicitly configure thinking at its
            # request-fit seam; retain the real request-fit/retry/gate machinery.
            # This is thinking-active compatibility, NOT default legacy behavior.
            original_fit = self.p._llm_request_fit

            async def thinking_fit(session, url, body, *args, **kwargs):
                return await original_fit(session, url, {**body, "thinking": {"type": "enabled"}}, *args, **kwargs)

            monkeypatch.setattr(self.p, "_llm_request_fit", thinking_fit)

    async def send(self, *, resume=None):
        async def emit(event):
            self.events.append(event)

        token = provider_admin._llm_lock.set(_route())
        try:
            return await self.p.send(TurnRequest(
                chat_id="protocol-1004", user_text="" if resume else "Remember I like warm colors, inspect canvas, then add a label.",
                lang="en", goal_text="", model="deepseek-flash", mcp_endpoint="http://fake.invalid/mcp",
                resume_run_id=resume,
            ), emit, TurnHandle())
        finally:
            provider_admin._llm_lock.reset(token)


@pytest.mark.parametrize("restart_kind", ["sqlite_reopen", "subprocess"])
async def test_actual_memory_boost_two_tool_rounds_sqlite_restart(protocol_db, tmp_path, monkeypatch, restart_kind):
    store = SqliteRunStore()
    first = ProtocolRig(monkeypatch, tmp_path, [
        response("memory-call", "memory", {"action": "add", "text": "warm colors", "category": "taste"}, ""),
        response("canvas-call", "get_canvas", reasoning="  exact canvas thought\n"),
        RestartNow(),
    ], store=store)
    with pytest.raises(RestartNow):
        await first.send()
    assert [name for name, _args in first.tools] == ["memory", "get_canvas"]
    assert first.bodies[0]["thinking"] == {"type": "disabled"}
    # Actual memory tool success -> recorded blocks -> wrote_memory -> boost.
    assert first.bodies[1]["thinking"] == {"type": "enabled"}
    assert first.bodies[1]["reasoning_effort"] == "low"
    assert first.bodies[1]["max_tokens"] == llm_usd_gate.THINKING_DEFAULT
    (run,) = store.list_runs(chat_id="protocol-1004")
    compact = run["state"]["messages_compact"]
    thoughts = [m.get("reasoning_content") for m in compact if m.get("tool_calls")]
    assert thoughts == ["", "  exact canvas thought\n"]
    assert {m["tool_call_id"] for m in compact if m["role"] == "tool"} == {"memory-call", "canvas-call"}

    # Dispose the connection pool and create a new provider/store over disk.
    # This is a real SQLite reopen, not an interpreter/process-kill test.
    db._engines.pop(protocol_db).dispose()
    if restart_kind == "sqlite_reopen":
        restarted = SqliteRunStore(clock=lambda: time.time() + 3600)
        restarted.mark_interrupted()
        second = ProtocolRig(monkeypatch, tmp_path, [
            response("text-call", "add_text", {"text": "Warm colors"}, "exact text thought"),
            response(),
        ], store=restarted)
        result = await second.send(resume=run["id"])
        error, stop = result.error, result.run["stop"]
    else:
        # A fresh Python interpreter imports this checkout using the same safe
        # Comfy stubs as pytest. No inherited provider/store objects or engines.
        output = tmp_path / "resume-result.json"
        program = """
import asyncio, json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import conftest
from pytest import MonkeyPatch
from test_reasoning_protocol_1004 import ProtocolRig, response
from ComfyArt.api import db
from ComfyArt.api.run_store_sqlite import SqliteRunStore
with MonkeyPatch.context() as mon:
    mon.setattr(db, 'app_path', lambda _name: sys.argv[2])
    store = SqliteRunStore(clock=lambda: time.time() + 3600)
    store.mark_interrupted()
    rig = ProtocolRig(mon, Path(sys.argv[3]), [
        response('text-call', 'add_text', {'text': 'Warm colors'}, 'exact text thought'), response(),
    ], store=store)
    result = asyncio.run(rig.send(resume=sys.argv[4]))
    Path(sys.argv[5]).write_text(json.dumps({
        'error': result.error, 'run': result.run, 'bodies': rig.bodies, 'tools': rig.tools,
    }))
"""
        proc = subprocess.run([
            sys.executable, "-c", program, str(Path(__file__).resolve().parent),
            protocol_db, str(tmp_path), run["id"], str(output),
        ], text=True, capture_output=True, timeout=30)
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        loaded = json.loads(output.read_text())
        second = SimpleNamespace(bodies=loaded["bodies"], tools=loaded["tools"])
        error, stop = loaded["error"], loaded["run"]["stop"]
    assert error == ""
    assert stop["reason"] == "done"
    assert [name for name, _args in second.tools] == ["add_text"]
    assert [name for name, _args in first.tools + second.tools] == ["memory", "get_canvas", "add_text"]
    # Two tool rounds after memory: get_canvas before restart, add_text after.
    replayed = second.bodies[0]["messages"]
    assert [m.get("reasoning_content") for m in replayed if m.get("tool_calls")] == thoughts
    final_history = second.bodies[1]["messages"]
    assert [m.get("reasoning_content") for m in final_history if m.get("tool_calls")] == thoughts + ["exact text thought"]

    # Rolling summary uses actual protocol history. Older groups may be folded
    # away, but the retained assistant/tool group must keep canonical fields.
    enlarged = copy.deepcopy(final_history)
    for message in enlarged:
        if message["role"] == "tool":
            message["content"] += " long tool result" * 2000
    policy = resolve_policy(user={"verbatim_steps": 1}, env={})
    compressed, did = agent_loop.compress(enlarged, window=4000, policy=policy)
    assert did
    kept = [m for m in compressed if m.get("tool_calls")]
    assert kept and kept[-1]["reasoning_content"] == "exact text thought"
    assert any(m["role"] == "tool" and m["tool_call_id"] == "text-call" for m in compressed)
    assert any(agent_loop._SUMMARY_HEAD in str(m.get("content", "")) for m in compressed)

    # Check the compressor's actual output at the HTTP transport boundary too;
    # this isolated compression subcheck is not a claim the small test run hit
    # automatic model-window compression on its own.
    summary_sent = []

    async def compressed_transport(_session, _method, _url, *, headers, json_body, timeout):
        summary_sent.append(copy.deepcopy(json_body))
        kept_at_http = [m for m in json_body["messages"] if m.get("tool_calls")]
        assert kept_at_http[-1]["reasoning_content"] == "exact text thought"
        return response()

    token = provider_admin._llm_lock.set(_route())
    try:
        await provider_admin.gated_llm_http(
            None, "POST", "https://api.deepseek.com/chat/completions", headers={},
            json_body={"model": "deepseek-flash", "messages": compressed, "thinking": {"type": "enabled"}},
            transport=compressed_transport, ledger_path=first.ledger,
            bound_fn=lambda _body, _snapshot: llm_usd_gate.Bound(True, 0, "", "test-only compressed history"),
        )
    finally:
        provider_admin._llm_lock.reset(token)
    assert len(summary_sent) == 1


async def test_legacy_explicit_thinking_roundtrip_retains_canonical(protocol_db, tmp_path, monkeypatch):
    rig = ProtocolRig(monkeypatch, tmp_path, [
        response("canvas-call", "get_canvas", reasoning="  exact canvas thought\n"), response(),
    ], store=None, legacy=True)
    result = await rig.send()
    assert result.error == ""
    assert len(rig.bodies) == 2
    assert all(body["thinking"] == {"type": "enabled"} for body in rig.bodies)
    assert [name for name, _args in rig.tools] == ["get_canvas"]
    history = [m for m in rig.bodies[1]["messages"] if m.get("tool_calls")]
    assert history[-1]["reasoning_content"] == "  exact canvas thought\n"
