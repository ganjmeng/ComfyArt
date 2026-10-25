"""#238: external agents pick up the P1 context rules that apply to them.

Claude Code, Codex, Qwen Code and DeepSeek Harness. Mocks only: no CLI binary,
no LLM and no WaveSpeed call. The built-in agent keeps its own loop.
"""
from __future__ import annotations

import json

from conftest import write_settings

from ComfyArt.api import chat_store, mcp, paid_guard
from ComfyArt.api.mcp import INTERNAL_HEADER, INTERNAL_TOKEN
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.external_context import (
    SCREENSHOT_OMITTED,
    apply_cold_start,
    clip_image_blocks,
)
from ComfyArt.bot.guide import AGENT_GUIDE
from ComfyArt.bot.local_llm import count_tokens, input_token_budget
from ComfyArt.bot.providers import TurnHandle, TurnRequest, TurnResult


def _rpc(name, arguments=None, rid=1):
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}}}


def test_mcp_instructions_use_the_p1_system_prompt():
    from ComfyArt.api.mcp import INSTRUCTIONS, _initialize

    assert "WaveSpeed" in INSTRUCTIONS
    assert "ComfyUI is only the host app" in INSTRUCTIONS
    assert "Call get_canvas first" in INSTRUCTIONS
    assert "running on this ComfyUI" not in INSTRUCTIONS
    assert "local ComfyUI" not in INSTRUCTIONS
    assert _initialize({})["instructions"] == INSTRUCTIONS


def test_claude_codex_and_qwen_already_load_the_guide(monkeypatch, tmp_path):
    from ComfyArt.bot import claude_code, codex
    from ComfyArt.bot.codex import CodexCodeProvider, write_agent_instructions
    from ComfyArt.bot.qwen_code import write_project_settings

    monkeypatch.setattr(claude_code, "resolve_claude_command", lambda: ["claude"])
    argv = claude_code.ClaudeCodeProvider(home_dir=".")._build_argv(TurnRequest(
        chat_id="c", user_text="hi", mcp_endpoint="http://127.0.0.1/mcp"))
    guide = argv[argv.index("--append-system-prompt") + 1]
    assert guide == AGENT_GUIDE
    assert "WaveSpeed, and ComfyUI is only the host app" in guide

    text = write_agent_instructions(str(tmp_path)).read_text(encoding="utf-8")
    assert AGENT_GUIDE in text
    write_project_settings(str(tmp_path / "qwen"), "http://127.0.0.1/mcp")
    assert (tmp_path / "qwen" / "QWEN.md").read_text(encoding="utf-8").strip() == AGENT_GUIDE
    # Codex's writer is what the provider uses; importing the provider keeps the reference live.
    assert CodexCodeProvider.id == "codex"


def test_cold_start_fits_history_and_leaves_attachments():
    early = [{"role": "user", "text": "E" + "x" * 20_000} for _ in range(8)]
    early[0] = {"role": "user", "text": "GOAL_KEEP paint a poster. 数量 4 张 " + "x" * 20_000}
    recent = [{"role": "user", "text": f"RECENT{i}"} for i in range(6)]
    attachments = [{"data": "QUJD", "media_type": "image/png"}]
    turn = apply_cold_start(TurnRequest(
        chat_id="c", user_text="now brighter", history=early + recent, attachments=attachments,
    ))
    assert turn.attachments == attachments
    assert "QUJD" not in turn.user_text
    assert turn.user_text.endswith("now brighter")
    assert "You are ComfyArt Agent" not in turn.user_text  # the CLI loads the guide itself
    preamble, _, current = turn.user_text.rpartition("\n\n")
    assert current == "now brighter"
    assert "Earlier conversation summary:" in preamble
    assert "GOAL_KEEP" in preamble
    assert "x" * 1000 not in preamble
    for i in range(6):
        assert f"User: RECENT{i}" in preamble
    summary = preamble.split("\n\nUser: RECENT0", 1)[0]
    assert count_tokens(summary) <= 2000
    assert count_tokens(AGENT_GUIDE) + count_tokens(turn.user_text) <= input_token_budget(32_000)


def test_cold_start_keeps_the_latest_two_screenshot_urls():
    urls = [f"data:image/png;base64,{'ABCD' * 8}{letter}" for letter in "ABC"]
    turn = apply_cold_start(TurnRequest(
        chat_id="c", user_text="go",
        history=[{"role": "user", "text": url} for url in urls],
    ))
    assert urls[0] not in turn.user_text
    assert urls[1] in turn.user_text and urls[2] in turn.user_text
    assert turn.user_text.count(SCREENSHOT_OMITTED) == 1


def test_resume_does_not_rewrite_the_prompt():
    history = [{"role": "user", "text": "EARLIER_GOAL"}]
    turn = TurnRequest(chat_id="c", user_text="go", history=history, resume_token="sid")
    assert apply_cold_start(turn).user_text == "go"
    assert apply_cold_start(turn, prepend_guide=True).user_text == "go"
    guided = apply_cold_start(TurnRequest(
        chat_id="c", user_text="go", history=history), prepend_guide=True)
    assert guided.user_text.startswith(AGENT_GUIDE)
    assert "EARLIER_GOAL" in guided.user_text and guided.user_text.endswith("go")


def test_one_response_keeps_its_latest_images():
    blocks = [{"type": "text", "text": "{}"}] + [
        {"type": "image", "data": letter, "mimeType": "image/png"} for letter in "ABC"
    ]
    clipped, sent = clip_image_blocks(blocks, already_sent=0)
    assert sent == 2
    assert [b.get("data") for b in clipped if b["type"] == "image"] == ["B", "C"]
    assert clipped[1] == {"type": "text", "text": SCREENSHOT_OMITTED}
    again, sent = clip_image_blocks(
        [{"type": "image", "data": "D", "mimeType": "image/png"}], already_sent=sent)
    assert sent == 2 and again == [{"type": "text", "text": SCREENSHOT_OMITTED}]


def test_external_step_limit_prefers_the_env(monkeypatch):
    monkeypatch.setattr("ComfyArt.api.settings.get_setting", lambda key: 15)
    monkeypatch.delenv("COMFYART_AGENT_MAX_STEPS", raising=False)
    assert paid_guard.external_step_limit() == 15
    monkeypatch.setenv("COMFYART_AGENT_MAX_STEPS", "9")
    assert paid_guard.external_step_limit() == 9


async def _server_info(monkeypatch):
    calls = []

    async def handler(_args):
        calls.append(1)
        return {"ok": True}

    monkeypatch.setitem(mcp.TOOLS, "server_info", {
        "description": "", "inputSchema": {}, "handler": handler})
    return calls


async def test_external_step_limit_stops_before_the_tool(monkeypatch):
    monkeypatch.setattr(paid_guard, "external_step_limit", lambda: 2)
    calls = await _server_info(monkeypatch)
    paid_guard.begin_turn("c238", text="检查所有页面", provider_text="检查所有页面", lang="zh")
    stopped = []
    paid_guard.TURNS["c238"].on_stop = lambda: stopped.append(1)
    token = BOT_CHAT_ID.set("c238")
    try:
        for _ in range(2):
            out = await mcp._tools_call({"name": "server_info", "arguments": {}}, external=True)
            assert out["isError"] is False
        blocked = await mcp._tools_call({"name": "server_info", "arguments": {}}, external=True)
        assert blocked["isError"] is True
        text = blocked["content"][0]["text"]
        assert "已达到 2 步上限" in text and "查看状态 ×2" in text
        assert calls == [1, 1]
        assert stopped == [1]
        again = await mcp._tools_call({"name": "server_info", "arguments": {}}, external=True)
        assert again["isError"] is True and calls == [1, 1] and stopped == [1]
    finally:
        BOT_CHAT_ID.reset(token)
        paid_guard.end_turn("c238")


async def test_external_step_limit_follows_ui_language(monkeypatch):
    monkeypatch.setattr(paid_guard, "external_step_limit", lambda: 1)
    await _server_info(monkeypatch)
    paid_guard.begin_turn("c238en", text="check", provider_text="check", lang="en")
    token = BOT_CHAT_ID.set("c238en")
    try:
        assert (await mcp._tools_call({"name": "server_info", "arguments": {}}, external=True))["isError"] is False
        blocked = await mcp._tools_call({"name": "server_info", "arguments": {}}, external=True)
        text = blocked["content"][0]["text"]
        assert "Reached the 1-step limit" in text and "Check status" in text
    finally:
        BOT_CHAT_ID.reset(token)
        paid_guard.end_turn("c238en")


async def test_builtin_calls_are_not_step_capped_here(monkeypatch):
    monkeypatch.setattr(paid_guard, "external_step_limit", lambda: 1)
    calls = await _server_info(monkeypatch)
    paid_guard.begin_turn("c238in", text="check", provider_text="check", lang="en")
    token = BOT_CHAT_ID.set("c238in")
    try:
        for _ in range(3):
            out = await mcp._tools_call({"name": "server_info", "arguments": {}}, external=False)
            assert out["isError"] is False
        assert calls == [1, 1, 1]
    finally:
        BOT_CHAT_ID.reset(token)
        paid_guard.end_turn("c238in")


def _shot(data):
    return {"data": data, "mime": "image/png"}


async def test_external_mcp_keeps_two_screenshots_per_turn(bot_client, monkeypatch):
    shots = []

    async def handler(args):
        shots.append(args["mark"])
        return {"mark": args["mark"], "_images": [_shot(item) for item in args["images"]]}

    monkeypatch.setitem(mcp.TOOLS, "server_info", {
        "description": "", "inputSchema": {}, "handler": handler})
    chat = chat_store.create_chat(user="default", project="p", provider="codex")
    paid_guard.begin_turn(chat["id"], text="look", provider_text="look", lang="en")
    url = f"/comfyart/mcp?bot_chat={chat['id']}"

    async def call(mark, images, *, internal=False, rid=1):
        headers = {INTERNAL_HEADER: INTERNAL_TOKEN} if internal else {}
        resp = await bot_client.post(url, json=_rpc("server_info", {"mark": mark, "images": images}, rid),
                                     headers=headers)
        assert resp.status == 200, await resp.text()
        return (await resp.json())["result"]["content"]

    def image_data(content):
        return [block["data"] for block in content if block.get("type") == "image"]

    try:
        # No images dropped inside the response that fills the budget: the latest two stay.
        first = await call("batch", ["A", "B", "C"], rid=1)
        assert image_data(first) == ["B", "C"]
        assert any(block.get("text") == SCREENSHOT_OMITTED for block in first)
        # The built-in agent's internal calls are not part of this cap.
        internal = await call("internal", ["D"], internal=True, rid=2)
        assert image_data(internal) == ["D"]
        # A later external screenshot is the placeholder; two images were already returned.
        later = await call("later", ["E"], rid=3)
        assert image_data(later) == []
        assert any(block.get("text") == SCREENSHOT_OMITTED for block in later)
        assert shots == ["batch", "internal", "later"]
    finally:
        paid_guard.end_turn(chat["id"])


async def test_screenshot_cap_is_off_without_a_bot_turn(bot_client, monkeypatch):
    async def handler(_args):
        return {"_images": [_shot(letter) for letter in "ABC"]}

    monkeypatch.setitem(mcp.TOOLS, "server_info", {
        "description": "", "inputSchema": {}, "handler": handler})
    resp = await bot_client.post("/comfyart/mcp", json=_rpc("server_info"))
    content = (await resp.json())["result"]["content"]
    assert [block["data"] for block in content if block.get("type") == "image"] == ["A", "B", "C"]


async def _capture_send(monkeypatch, module, provider, turn):
    captured = {}

    async def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["stdin"] = kwargs.get("stdin_payload")
        return TurnResult()

    monkeypatch.setattr(module, "run_cli_turn", fake_run)

    async def emit(_ev):
        return None

    await provider.send(turn, emit, TurnHandle())
    return captured


async def test_claude_codex_qwen_cold_start_and_resume(monkeypatch, tmp_path):
    from ComfyArt.bot import claude_code, codex, qwen_code
    from ComfyArt.bot.claude_code import ClaudeCodeProvider
    from ComfyArt.bot.codex import CodexCodeProvider
    from ComfyArt.bot.qwen_code import QwenCodeProvider

    monkeypatch.setattr(claude_code, "resolve_claude_command", lambda: ["claude"])
    monkeypatch.setattr(codex, "resolve_codex_command", lambda: ["codex"])
    monkeypatch.setattr(qwen_code, "resolve_qwen_command", lambda: ["qwen"])
    history = [{"role": "user", "text": "EARLIER_GOAL paint a poster"}]
    cold = TurnRequest(chat_id="c", user_text="now brighter", history=history,
                       mcp_endpoint="http://127.0.0.1/mcp")
    resumed = TurnRequest(chat_id="c", user_text="now brighter", history=history,
                          resume_token="sid", mcp_endpoint="http://127.0.0.1/mcp")

    claude = await _capture_send(monkeypatch, claude_code, ClaudeCodeProvider(home_dir=str(tmp_path / "c")), cold)
    prompt = claude["argv"][claude["argv"].index("-p") + 1]
    assert "EARLIER_GOAL" in prompt and prompt.endswith("now brighter")
    assert "You are ComfyArt Agent" not in prompt
    assert AGENT_GUIDE == claude["argv"][claude["argv"].index("--append-system-prompt") + 1]
    resumed_claude = await _capture_send(
        monkeypatch, claude_code, ClaudeCodeProvider(home_dir=str(tmp_path / "c2")), resumed)
    assert resumed_claude["argv"][resumed_claude["argv"].index("-p") + 1] == "now brighter"

    attached = TurnRequest(
        chat_id="c", user_text="look", history=history,
        attachments=[{"data": "QUJD", "media_type": "image/png"}],
        mcp_endpoint="http://127.0.0.1/mcp")
    streamed = await _capture_send(
        monkeypatch, claude_code, ClaudeCodeProvider(home_dir=str(tmp_path / "c3")), attached)
    envelope = json.loads(streamed["stdin"])
    content = envelope["message"]["content"]
    assert content[0]["source"]["data"] == "QUJD"
    assert content[-1]["text"].endswith("look") and "EARLIER_GOAL" in content[-1]["text"]

    codex_home = tmp_path / "codex"
    codex_run = await _capture_send(
        monkeypatch, codex, CodexCodeProvider(home_dir=str(codex_home)), cold)
    assert "EARLIER_GOAL" in codex_run["argv"][-1] and codex_run["argv"][-1].endswith("now brighter")
    assert AGENT_GUIDE in (codex_home / "AGENTS.md").read_text(encoding="utf-8")
    codex_back = await _capture_send(
        monkeypatch, codex, CodexCodeProvider(home_dir=str(codex_home)), resumed)
    assert codex_back["argv"][-1] == "now brighter"

    qwen_home = tmp_path / "qwen"
    qwen_run = await _capture_send(
        monkeypatch, qwen_code, QwenCodeProvider(home_dir=str(qwen_home)), cold)
    qwen_text = qwen_run["argv"][qwen_run["argv"].index("-p") + 1]
    assert "EARLIER_GOAL" in qwen_text and qwen_text.endswith("now brighter")
    assert (qwen_home / "QWEN.md").read_text(encoding="utf-8").strip() == AGENT_GUIDE
    qwen_back = await _capture_send(
        monkeypatch, qwen_code, QwenCodeProvider(home_dir=str(qwen_home)), resumed)
    assert qwen_back["argv"][qwen_back["argv"].index("-p") + 1] == "now brighter"


def test_external_step_limit_reads_bot_max_steps(monkeypatch):
    monkeypatch.delenv("COMFYART_AGENT_MAX_STEPS", raising=False)
    write_settings(**{"bot-max-steps": 80})
    assert paid_guard.external_step_limit() == 80
