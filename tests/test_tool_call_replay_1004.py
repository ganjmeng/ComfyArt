"""Persisted tool-call index is sequence metadata, not a supplier-replay field.

The tool call below is the sanitized messages_compact row from the first live
continuation failure. It is not a raw provider response: that body was not
retained. Skill text, the inquiry arguments, and the terminal reply are
synthetic. No provider key, network, or paid generation is used.
"""
import copy
import json
import os
from pathlib import Path

import aiohttp
import pytest

from ComfyArt.api import provider_admin
from ComfyArt.api.mcp_tools import TOOLS
from ComfyArt.bot import llm_input_envelope as envelope
from ComfyArt.bot import llm_usd_gate as gate
from ComfyArt.bot import local_llm
from ComfyArt.bot.assistant_history import assistant_history_message, replay_tool_calls
from ComfyArt.bot.guide import CORE_MCP_TOOLS
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy
from test_default_preflight_capture_1004 import PNG
from test_llm_input_envelope_1004 import controlled
from test_llm_usd_gate import URL, _route, _usage


# Captured persisted shape. Key order matches the stored row. Not a raw provider body.
PERSISTED_ID = "call_00_B9Ofgb0DQeOKnbkBnWqP0126"
PERSISTED_ARGUMENTS = '{"action": "read", "name": "universal-multi-angle-grid"}'
PERSISTED_CALL = {
    "index": 0,
    "id": PERSISTED_ID,
    "type": "function",
    "function": {"name": "skill", "arguments": PERSISTED_ARGUMENTS},
}
REASONING = "  exact persisted-boundary thought\n"
# Synthetic inquiry. Not a captured Lovart card.
INQUIRY = {
    "prompt": "Synthetic setup question",
    "options": [{"id": "square", "label": "1:1"}, {"id": "portrait", "label": "4:5"}],
    "allow_skip": True,
}
USER_TEXT = (
    "Use the ComfyArt skill 'universal-multi-angle-grid' for this task. "
    "Synthetic fixture: read the skill, then ask the setup question."
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("COMFYART_LLM_USD_GATE", "1")
    gate.clear_authorized_scope()
    gate._write_fault = None
    for name in list(os.environ):
        if name.endswith("_API_KEY") or name in ("OPENAI_TOKEN", "DEEPSEEK_TOKEN"):
            monkeypatch.delenv(name, raising=False)

    async def no_socket(*args, **kwargs):
        raise AssertionError("No real HTTP permitted")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", no_socket)
    token = provider_admin._llm_lock.set(_route())
    yield
    provider_admin._llm_lock.reset(token)
    gate._write_fault = None
    gate.clear_authorized_scope()


def _persisted_call():
    return copy.deepcopy(PERSISTED_CALL)


def _history_row(call, reasoning=None):
    message = {"role": "assistant", "content": None, "tool_calls": [call]}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return assistant_history_message(message, "", [call])


def test_persisted_index_zero_is_omitted_and_input_is_not_mutated():
    call = _persisted_call()
    original_arguments = call["function"]["arguments"]
    row = _history_row(call, REASONING)
    replay = row["tool_calls"][0]
    assert replay == {
        "id": PERSISTED_ID,
        "type": "function",
        "function": {"name": "skill", "arguments": PERSISTED_ARGUMENTS},
    }
    assert replay["function"]["arguments"] is original_arguments
    assert row["reasoning_content"] is REASONING
    assert row["content"] is None
    assert call["index"] == 0
    assert call["function"]["arguments"] is original_arguments
    assert "index" not in replay


def test_canonical_call_without_index_keeps_the_same_objects():
    call = {"id": "fixture", "type": "function", "function": {"name": "skill", "arguments": "{}"}}
    calls = [call]
    assert replay_tool_calls(calls) is calls
    row = assistant_history_message({"role": "assistant", "content": None}, "", calls)
    assert row["tool_calls"] is calls


def test_later_arguments_rewrite_does_not_replace_the_replayed_string():
    call = _persisted_call()
    row = _history_row(call)
    call["function"]["arguments"] = "{\"action\": \"save\"}"
    assert row["tool_calls"][0]["function"]["arguments"] == PERSISTED_ARGUMENTS


@pytest.mark.parametrize("index", ["0", 0.0, True, False, None, -1, 1])
def test_invalid_index_type_or_range_stays_on_the_same_call(index):
    call = _persisted_call()
    call["index"] = index
    calls = [call]
    assert replay_tool_calls(calls) is calls
    assert calls[0] is call
    assert call["index"] == index


def test_second_slot_accepts_only_its_own_position():
    first = _persisted_call()
    second = {"index": 1, "id": "call-b", "type": "function", "function": {"name": "ask_user", "arguments": "{}"}}
    swapped = {"index": 0, "id": "call-b", "type": "function", "function": {"name": "ask_user", "arguments": "{}"}}
    replayed = replay_tool_calls([first, second])
    assert "index" not in replayed[0] and "index" not in replayed[1]
    assert replay_tool_calls([first, swapped])[1] is swapped


def test_unknown_field_is_not_removed():
    call = _persisted_call()
    call["trace"] = "synthetic-unknown"
    replay = replay_tool_calls([call])[0]
    assert replay is not call
    assert "index" not in replay and replay["trace"] == "synthetic-unknown"
    assert call["index"] == 0 and call["trace"] == "synthetic-unknown"
    function = dict(call["function"], extra="synthetic")
    indexed = _persisted_call()
    indexed["function"] = function
    kept = replay_tool_calls([indexed])[0]["function"]
    assert kept["extra"] == "synthetic" and kept["arguments"] is PERSISTED_ARGUMENTS
    assert "extra" in function


def _continuation_body(assistant):
    return {
        "model": "deepseek-flash",
        "thinking": {"type": "disabled"},
        "max_tokens": 8192,
        "tools": [{"type": "function", "function": {"name": "skill", "description": "skill", "parameters": {"type": "object"}}}],
        "messages": [
            {"role": "system", "content": "synthetic"},
            {"role": "user", "content": "synthetic"},
            assistant,
            {"role": "tool", "tool_call_id": PERSISTED_ID, "content": "synthetic tool result"},
        ],
    }


@pytest.mark.parametrize("mutation", ["persisted-index", "bad-type", "unknown-field", "unknown-function-field"])
async def test_envelope_rejects_unreplayed_shape_without_a_post(tmp_path, mutation):
    path = controlled(tmp_path)
    call = _persisted_call()
    if mutation == "bad-type":
        call["index"] = "0"
    elif mutation == "unknown-field":
        call["trace"] = "synthetic-unknown"
    elif mutation == "unknown-function-field":
        call["function"] = {**call["function"], "extra": "synthetic"}
    assistant = {"role": "assistant", "content": None, "tool_calls": [call]}
    if mutation != "persisted-index":
        # The history boundary leaves these in place; the validator must still reject them.
        assistant = _history_row(call)
        assistant["content"] = None
    before = Path(path).read_bytes()

    async def no_send(*args, **kwargs):
        pytest.fail("Rejected replay must not reach the socket")

    with pytest.raises(gate.LlmBudgetBlocked) as denied:
        await provider_admin.gated_llm_http(
            None, "POST", URL, headers={}, json_body=_continuation_body(assistant),
            transport=no_send, ledger_path=path, context_contract=True)
    assert denied.value.code == "invalid_request_envelope"
    assert denied.value.detail == "messages[2].tool_calls"
    assert Path(path).read_bytes() == before
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 0


async def test_replayed_persisted_call_passes_the_unchanged_validator(tmp_path):
    path = controlled(tmp_path)
    call = _persisted_call()
    sent = []

    async def fake(*args, json_body, **kwargs):
        sent.append(json_body.as_dict())
        return {"choices": [{"message": {"role": "assistant", "content": "synthetic"}, "finish_reason": "stop"}], **_usage(20, 3)}

    row = _history_row(call, REASONING)
    await provider_admin.gated_llm_http(
        None, "POST", URL, headers={}, json_body=_continuation_body(row),
        transport=fake, ledger_path=path, context_contract=True)
    replay = sent[0]["messages"][2]
    assert replay["tool_calls"] == [{
        "id": PERSISTED_ID, "type": "function",
        "function": {"name": "skill", "arguments": PERSISTED_ARGUMENTS},
    }]
    assert replay["reasoning_content"] == REASONING
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 1
    # The strict key set is unchanged: a direct persisted row still fails here.
    with pytest.raises(envelope.EnvelopeInvalid) as raw:
        envelope.validate_envelope(_continuation_body(
            {"role": "assistant", "content": None, "tool_calls": [_persisted_call()], "reasoning_content": REASONING}))
    assert raw.value.field == "messages[2].tool_calls"


class _Reply:
    def __init__(self, value, status=200):
        self.value, self.status, self.headers = value, status, {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def text(self):
        return json.dumps(self.value) if not isinstance(self.value, str) else self.value


def _catalog():
    return [
        {"name": name, "description": spec["description"], "inputSchema": copy.deepcopy(spec["inputSchema"])}
        for name, spec in TOOLS.items() if name in CORE_MCP_TOOLS
    ]


class ContinuationRig:
    """Real default builder and MCP helpers. Only ClientSession.request is fake."""

    def __init__(self, monkeypatch, tmp_path, first_call):
        self.p = LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")
        self.path = controlled(tmp_path)
        self.model_posts = []
        self.rpc = []
        self.events = []
        self.first_call = first_call
        monkeypatch.setattr(self.p, "_api_headers", lambda: {})
        monkeypatch.setattr(self.p, "_run_policy", lambda: resolve_policy(env={}))
        monkeypatch.setattr(self.p, "_run_store", lambda: None)
        monkeypatch.setattr(self.p, "_mcp_headers", lambda: {})

        async def no_plan(*args, **kwargs):
            return None

        monkeypatch.setattr("ComfyArt.bot.shot_plan.run_plan_card", no_plan)
        raw = LocalLlmProvider._request_json.__get__(self.p)

        async def gated(session, method, url, *, headers, json_body=None, timeout=120):
            if str(url).endswith("/chat/completions"):
                return await provider_admin.gated_llm_http(
                    session, method, url, headers=headers, json_body=json_body, timeout=timeout,
                    transport=raw, ledger_path=self.path, context_contract=True)
            return await raw(session, method, url, headers=headers, json_body=json_body, timeout=timeout)

        monkeypatch.setattr(self.p, "_request_json", gated)
        catalog = _catalog()

        def fake_socket(session, method, url, **kwargs):
            if str(url).endswith("/models"):
                return _Reply({"data": [{"id": "deepseek-flash"}]})
            assert kwargs.get("allow_redirects") is False or not str(url).endswith("/chat/completions")
            if str(url).endswith("/chat/completions"):
                body = json.loads(kwargs["data"])
                self.model_posts.append(body)
                n = len(self.model_posts)
                if n == 1:
                    message = {"role": "assistant", "content": None, "tool_calls": [copy.deepcopy(self.first_call)]}
                    return _Reply({"choices": [{"finish_reason": "tool_calls", "message": message}], **_usage(30, 12)})
                if n == 2:
                    message = {"role": "assistant", "content": None, "tool_calls": [{
                        "id": "call-inquiry-synthetic", "type": "function",
                        "function": {"name": "ask_user", "arguments": json.dumps(INQUIRY)},
                    }]}
                    return _Reply({"choices": [{"finish_reason": "tool_calls", "message": message}], **_usage(40, 16)})
                return _Reply({"choices": [{"finish_reason": "stop", "message": {
                    "role": "assistant", "content": "Synthetic terminal reply"}}], **_usage(12, 4)})
            assert method == "POST" and str(url).endswith("/mcp")
            rpc = kwargs["json"]
            self.rpc.append(rpc)
            if rpc["method"] == "tools/list":
                return _Reply({"result": {"tools": catalog}})
            assert rpc["method"] == "tools/call"
            name = rpc["params"]["name"]
            if name == "skill":
                # Synthetic page. The live tool result was a deployment permission error.
                return _Reply({"result": {"content": [{"type": "text", "text": json.dumps({
                    "id": "universal-multi-angle-grid", "name": "universal-multi-angle-grid",
                    "instructions": "Synthetic skill page. Ask the setup question.",
                })}]}})
            assert name == "ask_user"
            return _Reply({"result": {"content": [{"type": "text", "text": json.dumps({
                "status": "answered", "selected": ["square"], "note": "synthetic answer"})}]}})

        monkeypatch.setattr(aiohttp.ClientSession, "request", fake_socket)

    async def run(self):
        async def emit(event):
            self.events.append(event)

        return await self.p.send(TurnRequest(
            chat_id="synthetic-replay-1004", user_text=USER_TEXT, lang="en", goal_text="",
            model="deepseek-flash", mcp_endpoint="http://fake.invalid/mcp", history=[],
            attachments=[{"media_type": "image/png", "data": PNG}]), emit, TurnHandle())


def _assert_default_request(body):
    assert len(CORE_MCP_TOOLS) + 1 == 52
    assert len(body["tools"]) == 52
    assert {tool["function"]["name"] for tool in body["tools"]} == set(CORE_MCP_TOOLS) | {local_llm.QUOTE_TOOL}
    assert body["thinking"] == {"type": "disabled"}
    assert body["max_tokens"] == 8192
    sent_url = body["messages"][1]["content"][1]["image_url"]["url"]
    assert sent_url.startswith("data:image/jpeg;base64,")


async def test_default_continuation_replays_persisted_skill_read_then_asks(monkeypatch, tmp_path):
    rig = ContinuationRig(monkeypatch, tmp_path, _persisted_call())
    result = await rig.run()
    assert result.error == ""
    assert [post["messages"][0]["role"] for post in rig.model_posts] == ["system", "system", "system"]
    assert len(rig.model_posts) == 3
    for body in rig.model_posts:
        _assert_default_request(body)
    replay = next(message for message in rig.model_posts[1]["messages"] if message.get("tool_calls"))
    assert replay["tool_calls"] == [{
        "id": PERSISTED_ID, "type": "function",
        "function": {"name": "skill", "arguments": PERSISTED_ARGUMENTS},
    }]
    assert replay["content"] is None
    assert "reasoning_content" not in replay
    skill, ask = [rpc for rpc in rig.rpc if rpc["method"] == "tools/call"]
    assert skill["params"] == {"name": "skill", "arguments": {"action": "read", "name": "universal-multi-angle-grid"}}
    assert ask["params"]["name"] == "ask_user"
    assert ask["params"]["arguments"]["prompt"] == INQUIRY["prompt"]
    assert [event.name for event in rig.events if event.t == "tool_use"] == ["skill", "ask_user"]
    assert gate.ledger_state(rig.path)["control_state"]["attempts_total"] == 3
    assert gate.ledger_state(rig.path)["inflight"] == 0


@pytest.mark.parametrize("mutation", ["bad-type", "unknown-field"])
async def test_rejected_continuation_does_not_increment_the_post_count(monkeypatch, tmp_path, mutation):
    call = _persisted_call()
    if mutation == "bad-type":
        call["index"] = "0"
    else:
        call["trace"] = "synthetic-unknown"
    rig = ContinuationRig(monkeypatch, tmp_path, call)
    result = await rig.run()
    from ComfyArt.bot.llm_usd_gate import user_notice
    assert result.error == user_notice("invalid_request_envelope", "en")
    assert "invalid_request_envelope" not in result.error
    assert "tool_calls" not in result.error
    assert len(rig.model_posts) == 1
    _assert_default_request(rig.model_posts[0])
    assert [rpc["params"]["name"] for rpc in rig.rpc if rpc["method"] == "tools/call"] == ["skill"]
    state = gate.ledger_state(rig.path)
    assert state["control_state"]["attempts_total"] == 1
    assert state["inflight"] == 0
    assert state["control_state"]["circuit_open"] is False
