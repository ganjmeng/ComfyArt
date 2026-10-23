from __future__ import annotations

import json

from ComfyArt.bot import lms
from ComfyArt.bot.guide import CORE_MCP_TOOLS
from ComfyArt.bot.local_llm import LocalLlmProvider, _user_content
from ComfyArt.bot.providers import BotEvent, TurnHandle, TurnRequest


class TestConfig:
    async def test_probe_without_url(self):
        provider = LocalLlmProvider(base_url=lambda: "")
        st = await provider.probe()
        assert st.available is False
        assert "Settings" in st.detail

    async def test_send_without_url(self):
        provider = LocalLlmProvider(base_url=lambda: "")
        result = await provider.send(
            TurnRequest(chat_id="c", user_text="hi",
                        mcp_endpoint="http://x/mcp"),
            _collect([]), TurnHandle())
        assert "endpoint" in result.error

    def test_stateless_caps(self):
        caps = LocalLlmProvider(base_url=lambda: "http://x/v1").capabilities()
        assert caps.stateful is False
        assert caps.attachments is True

    def test_api_key_from_env_only(self, monkeypatch):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        assert "Authorization" not in provider._api_headers()
        monkeypatch.setenv("COMFYART_LOCAL_LLM_API_KEY", "local")
        assert provider._api_headers()["Authorization"] == "Bearer local"


class TestUserContent:
    def test_plain_string_without_attachments(self):
        assert _user_content("hi", None) == "hi"
        assert _user_content("hi", [{"media_type": "image/jpeg"}]) == "hi"

    def test_multimodal_parts_with_attachments(self):
        content = _user_content("what is this?", [
            {"data": "QUJD", "media_type": "image/jpeg"},
            {"data": "REVG"},
        ])
        assert content[0] == {"type": "text", "text": "what is this?"}
        assert content[1]["image_url"]["url"] == "data:image/jpeg;base64,QUJD"
        assert content[2]["image_url"]["url"] == "data:image/jpeg;base64,REVG"


class TestHistory:
    def test_roles_and_order(self):
        history = [
            {"role": "user", "text": "q1"},
            {"role": "assistant", "text": "a1"},
            {"role": "tool", "text": "ignored"},
            {"role": "user", "text": ""},
        ]
        msgs = LocalLlmProvider._history_messages(history)
        assert msgs == [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]

    def test_char_cap_keeps_recent(self):
        history = [{"role": "user", "text": f"m{i}" + "x" * 9000}
                   for i in range(4)]
        msgs = LocalLlmProvider._history_messages(history)
        assert len(msgs) == 1
        assert msgs[0]["content"].startswith("m3")

    def test_none_history(self):
        assert LocalLlmProvider._history_messages(None) == []


class TestToolPlumbing:
    def test_build_tools_shape(self):
        tools = LocalLlmProvider._build_tools([
            {"name": "get_canvas", "description": " d ",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "bare"},
        ])
        assert tools[0]["function"]["name"] == "get_canvas"
        assert tools[0]["function"]["description"] == "d"
        assert tools[1]["function"]["parameters"] == {
            "type": "object", "properties": {}}

    async def test_list_tools_filters_to_core(self, monkeypatch):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")

        async def fake_request(session, method, url, *, headers,
                               json_body=None, timeout=120):
            return {"result": {"tools": [
                {"name": "get_canvas"}, {"name": "generate_image"},
                {"name": "not_a_registered_tool"}, {"name": "update_shapes"},
            ]}}

        monkeypatch.setattr(provider, "_request_json", fake_request)
        tools = await provider._mcp_list_tools(None, "http://x/mcp")
        assert [t["name"] for t in tools] == [
            "get_canvas", "generate_image", "update_shapes"]
        assert all(t["name"] in CORE_MCP_TOOLS for t in tools)


class TestWaitLoop:
    async def test_slices_until_done(self, monkeypatch):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        calls = []

        async def fake_call(session, endpoint, name, arguments):
            assert name == "wait_generation"
            calls.append(dict(arguments))
            if len(calls) < 3:
                return json.dumps({"status": "running"}), []
            return json.dumps({"status": "done", "results": []}), []

        monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
        monkeypatch.setattr(lms, "lms_bin", lambda: "")
        raw = await provider._wait_stage_done(
            None, "http://x/mcp", {"ids": ["shape:a"]}, "m", TurnHandle())
        assert json.loads(raw)["status"] == "done"
        assert len(calls) == 3
        assert calls[0]["timeout_s"] == 170


class TestAgentLoop:
    async def test_tool_call_then_answer(self, monkeypatch):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        chat_responses = [
            {"choices": [{"message": {
                "content": "",
                "tool_calls": [{"id": "t1", "function": {
                    "name": "server_info", "arguments": "{}"}}],
            }}]},
            {"choices": [{"message": {"content": "all good",
                                      "tool_calls": []}}]},
        ]

        async def fake_request(session, method, url, *, headers,
                               json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                return chat_responses.pop(0)
            return {"result": {"tools": [{"name": "server_info"}]}}

        async def fake_call(session, endpoint, name, arguments):
            return '{"comfyart_version": "1.9.0"}', []

        monkeypatch.setattr(provider, "_request_json", fake_request)
        monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
        events: list[BotEvent] = []
        result = await provider.send(
            TurnRequest(chat_id="c", user_text="check the server",
                        mcp_endpoint="http://x/mcp", model="m1"),
            _collect(events), TurnHandle())
        assert result.error == ""
        assert [e.t for e in events] == ["tool_use", "tool_result", "delta"]
        assert events[0].name == "server_info"
        assert events[1].text == '{"comfyart_version": "1.9.0"}'
        assert events[-1].text == "all good"

    async def test_reasoning_streams_as_thinking(self, monkeypatch):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        chat_responses = [
            {"choices": [{"message": {"content": "", "reasoning_content": "check first",
                                      "tool_calls": [{"id": "t1", "function": {"name": "server_info", "arguments": "{}"}}]}}]},
            {"choices": [{"message": {"content": "<think>looks fine</think>all good", "tool_calls": []}}]},
        ]

        async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                return chat_responses.pop(0)
            return {"result": {"tools": [{"name": "server_info"}]}}

        async def fake_call(session, endpoint, name, arguments):
            return "{}", []

        monkeypatch.setattr(provider, "_request_json", fake_request)
        monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
        events: list[BotEvent] = []
        await provider.send(TurnRequest(chat_id="c", user_text="hi", mcp_endpoint="http://x/mcp", model="m1"),
                            _collect(events), TurnHandle())
        assert [(e.t, e.text) for e in events if e.t in ("thinking", "delta")] == [
            ("thinking", "check first"), ("thinking", "looks fine"), ("delta", "all good")]

    async def test_usage_accumulates_and_tool_ids_flow(self, monkeypatch):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        chat_responses = [
            {"choices": [{"message": {
                "content": "",
                "tool_calls": [{"id": "t1", "function": {
                    "name": "server_info", "arguments": "{}"}}],
            }}],
             "usage": {"prompt_tokens": 100, "completion_tokens": 5}},
            {"choices": [{"message": {"content": "all good",
                                      "tool_calls": []}}],
             "usage": {"prompt_tokens": 120, "completion_tokens": 8}},
        ]

        async def fake_request(session, method, url, *, headers,
                               json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                return chat_responses.pop(0)
            return {"result": {"tools": [{"name": "server_info"}]}}

        async def fake_call(session, endpoint, name, arguments):
            raise RuntimeError("mcp down")

        monkeypatch.setattr(provider, "_request_json", fake_request)
        monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
        events: list[BotEvent] = []
        result = await provider.send(
            TurnRequest(chat_id="c", user_text="check",
                        mcp_endpoint="http://x/mcp", model="m1"),
            _collect(events), TurnHandle())
        assert result.usage == {"input_tokens": 220, "output_tokens": 13}
        tool_use = next(e for e in events if e.t == "tool_use")
        tool_result = next(e for e in events if e.t == "tool_result")
        assert tool_use.id == "t1"
        assert tool_result.id == "t1"
        assert tool_result.is_error is True
        assert "[error]" in tool_result.text

    async def test_stop_aborts(self, monkeypatch):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        handle = TurnHandle()

        async def fake_request(session, method, url, *, headers,
                               json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                handle.stop_requested = True
                return {"choices": [{"message": {
                    "content": "",
                    "tool_calls": [{"id": "t1", "function": {
                        "name": "get_canvas", "arguments": "{}"}}],
                }}]}
            return {"result": {"tools": [{"name": "get_canvas"}]}}

        monkeypatch.setattr(provider, "_request_json", fake_request)
        result = await provider.send(
            TurnRequest(chat_id="c", user_text="look",
                        mcp_endpoint="http://x/mcp", model="m1"),
            _collect([]), handle)
        assert result.aborted is True


def _collect(events: list[BotEvent]):
    async def emit(ev: BotEvent) -> None:
        events.append(ev)
    return emit


def _tc(i, name, args):
    return {"id": f"t{i}", "function": {"name": name,
                                         "arguments": json.dumps(args)}}


class TestLoopGuard:
    async def _run(self, monkeypatch, steps):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        responses = [{"choices": [{"message": {"content": "", "tool_calls": [
            _tc(i, n, a)]}}]} for i, (n, a) in enumerate(steps)]
        responses.append({"choices": [{"message": {"content": "done",
                                                   "tool_calls": []}}]})
        llm_calls: list[int] = []
        mcp_calls: list[tuple] = []

        async def fake_request(session, method, url, *, headers,
                               json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                llm_calls.append(1)
                return responses.pop(0)
            return {"result": {"tools": [{"name": "skill"},
                                         {"name": "generate_image"}]}}

        async def fake_call(session, endpoint, name, arguments):
            mcp_calls.append((name, dict(arguments)))
            return f"ok {name}", []

        monkeypatch.setattr(provider, "_request_json", fake_request)
        monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
        events: list[BotEvent] = []
        result = await provider.send(
            TurnRequest(chat_id="c", user_text="go",
                        mcp_endpoint="http://x/mcp", model="m1"),
            _collect(events), TurnHandle())
        return result, events, llm_calls, mcp_calls

    async def test_identical_call_three_times_stops(self, monkeypatch):
        gen = ("generate_image", {"prompt": "cat"})
        result, events, llm, mcp = await self._run(
            monkeypatch, [("skill", {"action": "list"}), gen, gen, gen, gen])
        assert result.error == ""
        assert len(llm) == 4  # no further LLM spend after the stop
        assert [c[0] for c in mcp] == ["skill", "generate_image",
                                       "generate_image"]
        stop = events[-1]
        assert stop.t == "delta"
        assert stop.text.startswith("任务卡在重复步骤，已停止，未继续扣费")
        assert "- skill ×1" in stop.text and "- generate_image ×2" in stop.text

    async def test_different_args_do_not_stop(self, monkeypatch):
        result, events, llm, mcp = await self._run(monkeypatch, [
            ("generate_image", {"prompt": p}) for p in "abc"])
        assert result.error == "" and len(mcp) == 3
        assert events[-1].text == "done"

    async def test_skill_read_once_per_turn(self, monkeypatch):
        read = ("skill", {"action": "read", "name": "poster"})
        result, events, llm, mcp = await self._run(monkeypatch, [
            read, ("generate_image", {"prompt": "x"}),
            ("skill", {"action": "read", "name": "Poster"}),
            ("skill", {"action": "read", "name": "social"})])
        assert result.error == ""
        reads = [a["name"] for n, a in mcp if n == "skill"]
        assert reads == ["poster", "social"]
        results = [e.text for e in events if e.t == "tool_result"]
        assert results[2] == "ok skill"  # cached result reused
        assert events[-1].text == "done"
