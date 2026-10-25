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
    async def _run(self, monkeypatch, steps, user_text="做一张海报", lang=""):
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
            TurnRequest(chat_id="c", user_text=user_text, lang=lang,
                        mcp_endpoint="http://x/mcp", model="m1"),
            _collect(events), TurnHandle())
        return result, events, llm_calls, mcp_calls

    async def test_identical_call_three_times_stops(self, monkeypatch):
        gen = ("generate_image", {"prompt": "cat"})
        result, events, llm, mcp = await self._run(
            monkeypatch, [("skill", {"action": "list"}), gen, gen, gen, gen])
        assert len(llm) == 4  # no further LLM spend after the stop
        assert [c[0] for c in mcp] == ["skill", "generate_image",
                                       "generate_image"]
        # stop text goes out as the turn error -> red error notice in the panel
        assert result.error == ("任务卡在重复步骤，已停止，未继续扣费。"
                                "已完成：技能、生成图像 ×2。")
        assert not any(e.t == "delta" for e in events)

    async def test_stop_message_follows_ui_language_en(self, monkeypatch):
        gen = ("generate_image", {"prompt": "cat"})
        read = ("skill", {"action": "read", "name": "poster-design"})
        # UI language wins over the message text
        result, events, llm, mcp = await self._run(
            monkeypatch, [read, gen, gen, gen], user_text="做海报", lang="en")
        assert result.error == (
            "The task got stuck repeating a step and was stopped; no further "
            "charges. Done so far: Read skill: poster-design, "
            "Generate image ×2.")
        assert result.error.startswith(
            "The task got stuck repeating a step and was stopped; no further "
            "charges.")

    async def test_stop_message_follows_ui_language_zh(self, monkeypatch):
        gen = ("generate_image", {"prompt": "cat"})
        read = ("skill", {"action": "read", "name": "海报设计"})
        result, events, llm, mcp = await self._run(
            monkeypatch, [read, gen, gen, gen], user_text="poster", lang="zh")
        assert result.error == ("任务卡在重复步骤，已停止，未继续扣费。"
                                "已完成：读取技能：海报设计、生成图像 ×2。")

    async def test_no_ui_language_falls_back_to_message_text(self, monkeypatch):
        gen = ("generate_image", {"prompt": "cat"})
        result, *_ = await self._run(monkeypatch, [gen, gen, gen],
                                     user_text="make a poster")
        assert result.error.startswith("The task got stuck")

    async def test_ab_alternating_skill_reads_stop_at_third_cache_hit(
            self, monkeypatch):
        a = ("skill", {"action": "read", "name": "poster"})
        b = ("skill", {"action": "read", "name": "social"})
        result, events, llm, mcp = await self._run(monkeypatch, [a, b] * 40)
        # A, B run; A, B are cache hits 1-2; A (3rd hit) stops. Far below 80.
        assert len(llm) == 5
        assert [x[1]["name"] for x in mcp] == ["poster", "social"]
        assert [e.t for e in events].count("tool_use") == 4
        # done list: only reads that actually ran, cached ones not counted
        assert result.error.endswith("已完成：读取技能：poster、读取技能：social。")

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


class TestStepLabels:
    def test_every_core_tool_has_readable_label(self):
        from bot.guide import CORE_MCP_TOOLS
        from bot.local_llm import _STEP_LABELS
        assert set(CORE_MCP_TOOLS) <= set(_STEP_LABELS)

    def test_labels_and_fallback(self):
        from bot.local_llm import _step_label
        assert _step_label("generate_image", {}, "zh") == "生成图像"
        assert _step_label("mcp__comfyart__generate_video", {}, "en") == \
            "Generate video"
        assert _step_label("skill", {"action": "list"}, "zh") == "技能"
        assert _step_label("nodes", {}, "zh") == "其他步骤"
        assert _step_label("nodes", {}, "en") == "Other step"

    def test_reply_lang(self):
        from bot.local_llm import _reply_lang
        assert _reply_lang("做一张海报") == "zh"
        assert _reply_lang("make a poster") == "en"
        hint = ("Use the ComfyArt skill '海报' for this task: first call the "
                "comfyart MCP tool skill with action='read' and name='海报', "
                "then follow those instructions.\n\nmake a poster")
        assert _reply_lang(hint) == "en"

    def test_empty_summary(self):
        from bot.local_llm import _stop_summary
        assert _stop_summary([], "zh").endswith("已完成：无。")
        assert _stop_summary([], "en").endswith("Done so far: nothing.")


class TestRetry232:
    """#232: LLM timeout / 429 / 5xx retried twice with a retry row; tool calls (paid) never retried."""

    async def _run(self, monkeypatch, faults, lang="zh", env_steps=None):
        from ComfyArt.bot import local_llm
        from ComfyArt.bot.local_llm import LlmHttpError
        monkeypatch.setattr(local_llm, "_RETRY_BACKOFF_S", (0.0, 0.0))
        monkeypatch.setattr(local_llm, "_RATE_LIMIT_WAIT_S", (0.0, 0.0))
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        script = [{"choices": [{"message": {"content": "", "tool_calls": [_tc(0, "generate_image", {"prompt": "cat"})]}}]},
                  *faults, {"choices": [{"message": {"content": "ok", "tool_calls": []}}]}]
        llm, paid = [], []

        async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                llm.append(1)
                step = script.pop(0)
                if isinstance(step, BaseException):
                    raise step
                return step
            return {"result": {"tools": [{"name": "generate_image"}]}}

        async def fake_call(session, endpoint, name, arguments):
            paid.append(name)
            return "{}", []

        monkeypatch.setattr(provider, "_request_json", fake_request)
        monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
        events: list[BotEvent] = []
        result = await provider.send(TurnRequest(chat_id="c", user_text="画猫", lang=lang,
                                                 mcp_endpoint="http://x/mcp", model="m"),
                                     _collect(events), TurnHandle())
        return result, events, llm, paid, LlmHttpError

    async def test_429_retry_after_and_rows(self, monkeypatch):
        from ComfyArt.bot.local_llm import LlmHttpError
        result, events, llm, paid, _ = await self._run(
            monkeypatch, [LlmHttpError(429, "slow down", 0.0), LlmHttpError(503, "busy")])
        assert result.error == "" and len(llm) == 4 and paid == ["generate_image"]
        rows = [e for e in events if e.t == "retry"]
        assert [(e.name, e.input["attempt"], e.input["max"]) for e in rows] == [("429", 1, 2), ("5xx", 2, 2)]

    async def test_exhausted_is_bilingual_with_done_steps(self, monkeypatch):
        import asyncio
        for lang, want in (("zh", "模型响应超时，已重试 2 次仍失败，已停止，请稍后再试。已完成：生成图像"),
                           ("en", "The model timed out; still failing after 2 retries, so the task stopped. "
                                  "Please try again later. Done so far: Generate image.")):
            result, _, llm, paid, _ = await self._run(
                monkeypatch, [asyncio.TimeoutError()] * 3, lang=lang)
            assert result.error == want and len(llm) == 4 and paid == ["generate_image"]

    async def test_4xx_not_retried(self, monkeypatch):
        from ComfyArt.bot.local_llm import LlmHttpError
        result, events, llm, _, _ = await self._run(monkeypatch, [LlmHttpError(401, "bad key")])
        assert len(llm) == 2 and "HTTP 401" in result.error
        assert not any(e.t == "retry" for e in events)

    async def test_cancel_text_marks_step_cancelled(self, monkeypatch):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        script = [{"choices": [{"message": {"content": "", "tool_calls": [_tc(0, "generate_image", {"prompt": "c"})]}}]},
                  {"choices": [{"message": {"content": "ok", "tool_calls": []}}]}]

        async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
            return script.pop(0) if url.endswith("/chat/completions") else {"result": {"tools": [{"name": "generate_image"}]}}

        async def fake_call(session, endpoint, name, arguments):
            return "[tool error] 已取消该生成，未扣费。", []

        monkeypatch.setattr(provider, "_request_json", fake_request)
        monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
        events: list[BotEvent] = []
        await provider.send(TurnRequest(chat_id="c", user_text="画", mcp_endpoint="http://x/mcp", model="m"),
                            _collect(events), TurnHandle())
        (res,) = [e for e in events if e.t == "tool_result"]
        assert res.detail == "cancelled"


class TestStepLimit232:
    def test_max_steps_clamped(self, monkeypatch):
        from ComfyArt.bot.local_llm import max_steps_from
        assert max_steps_from("30") == 30 and max_steps_from(0) == 80 and max_steps_from("x") == 80
        assert max_steps_from(9999) == 500
        monkeypatch.setenv("COMFYART_AGENT_MAX_STEPS", "5")
        assert LocalLlmProvider(base_url=lambda: "")._max_steps() == 5

    async def test_limit_message_lists_done_steps(self, monkeypatch):
        monkeypatch.setenv("COMFYART_AGENT_MAX_STEPS", "3")
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        n = iter(range(100))

        async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
            if url.endswith("/chat/completions"):
                return {"choices": [{"message": {"content": "", "tool_calls": [_tc(next(n), "get_canvas", {"p": next(n)})]}}]}
            return {"result": {"tools": [{"name": "get_canvas"}]}}

        async def fake_call(session, endpoint, name, arguments):
            return "{}", []

        monkeypatch.setattr(provider, "_request_json", fake_request)
        monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
        result = await provider.send(TurnRequest(chat_id="c", user_text="x", lang="en", mcp_endpoint="http://x/mcp",
                                                 model="m"), _collect([]), TurnHandle())
        assert result.error == "Reached the 3-step limit and stopped; no further charges. Done so far: View canvas ×3."


def test_system_prompt_says_wavespeed_not_local():
    from ComfyArt.bot.guide import AGENT_GUIDE
    assert "WaveSpeed, and ComfyUI is only the host app" in AGENT_GUIDE
    assert "local ComfyUI" not in AGENT_GUIDE


class TestPruneScreenshots233:
    """#233: only the latest 2 tool screenshots per round reach the LLM; older ones become a text line."""

    @staticmethod
    def _shot(name, *urls):
        return {"role": "user", "content": [{"type": "text", "text": f"Images returned by {name}:"},
                                            *({"type": "image_url", "image_url": {"url": u}} for u in urls)]}

    def test_keeps_latest_two_and_placeholders_older(self):
        from ComfyArt.bot.local_llm import _prune_screenshots
        user = {"role": "user", "content": [{"type": "text", "text": "hi"},
                                            {"type": "image_url", "image_url": {"url": "data:att"}}]}
        msgs = [{"role": "system", "content": "s"}, user,
                self._shot("a", "u1"), {"role": "tool", "content": "r"},
                self._shot("b", "u2", "u3"), self._shot("c", "u4")]
        out = _prune_screenshots(msgs)
        urls = [p["image_url"]["url"] for m in out if isinstance(m.get("content"), list)
                for p in m["content"] if p.get("type") == "image_url"]
        assert urls == ["data:att", "u3", "u4"]
        texts = [p["text"] for m in out[2:] if isinstance(m.get("content"), list)
                 for p in m["content"] if p.get("type") == "text"]
        assert texts.count("[older screenshot omitted]") == 2
        # the stored history is not mutated
        assert msgs[2]["content"][1]["image_url"]["url"] == "u1"
        assert len(out) == len(msgs) and out[3] is msgs[3]

    def test_noop_with_two_or_fewer(self):
        from ComfyArt.bot.local_llm import _prune_screenshots
        msgs = [self._shot("a", "u1"), self._shot("b", "u2")]
        assert _prune_screenshots(msgs) == msgs
