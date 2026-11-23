"""Offline gates for a canvas project that is not open in a live browser tab.

The project id is the captured chat project. The image is the existing synthetic
PNG, not the frozen original file. No deployment ledger is opened.
"""
import asyncio
import base64
import copy
import io
import json
import os
from pathlib import Path

import aiohttp
import pytest
from PIL import Image
from server import PromptServer

from ComfyArt.api import mcp_commands, provider_admin
from ComfyArt.api.mcp_tools import TOOLS
from ComfyArt.bot import llm_usd_gate as gate, local_llm
from ComfyArt.bot.guide import CORE_MCP_TOOLS
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy
from test_default_preflight_capture_1004 import PNG
from test_llm_input_envelope_1004 import controlled
from test_llm_usd_gate import URL, _route, _usage


PROJECT = "1005-frozen-original-first-card"
BROWSER_ERROR = (
    "ValueError: project 1005-frozen-original-first-card is not open in any browser tab"
    " — open it in ComfyArt and retry"
)
RECOVERABLE = "ValueError: no shape x"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("COMFYART_LLM_USD_GATE", "1")
    gate.clear_authorized_scope()
    gate._write_fault = None
    saved_pages, saved_sockets = dict(mcp_commands._pages), dict(PromptServer.instance.sockets)
    mcp_commands._pages.clear()
    PromptServer.instance.sockets.clear()
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
    mcp_commands._pages.clear()
    mcp_commands._pages.update(saved_pages)
    PromptServer.instance.sockets.clear()
    PromptServer.instance.sockets.update(saved_sockets)


def _open(project, tab="tab-1"):
    PromptServer.instance.sockets[tab] = object()
    mcp_commands._pages[tab] = project


class _Reply:
    def __init__(self, value):
        self.value, self.status, self.headers = value, 200, {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def text(self):
        return json.dumps(self.value)


def _catalog():
    return [{"name": name, "description": spec["description"], "inputSchema": copy.deepcopy(spec["inputSchema"])}
            for name, spec in TOOLS.items() if name in CORE_MCP_TOOLS]


class PageRig:
    def __init__(self, monkeypatch, tmp_path, *, tool_error=""):
        self.p = LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")
        self.path = controlled(tmp_path)
        self.model_posts = []
        self.tool_error = tool_error
        self.tool_seen = asyncio.Event()
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
            if str(url).endswith("/chat/completions"):
                body = json.loads(kwargs["data"])
                self.model_posts.append(body)
                if len(self.model_posts) == 1 and self.tool_error:
                    message = {"role": "assistant", "content": "我先读取这个技能的具体流程。", "tool_calls": [{
                        "id": "call-skill", "type": "function",
                        "function": {"name": "skill", "arguments": json.dumps({"action": "read", "name": "universal-multi-angle-grid"})},
                    }]}
                    return _Reply({"choices": [{"finish_reason": "tool_calls", "message": message}], **_usage(20, 4)})
                return _Reply({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "Synthetic done"}}], **_usage(8, 2)})
            rpc = kwargs["json"]
            if rpc["method"] == "tools/list":
                return _Reply({"result": {"tools": catalog}})
            self.tool_seen.set()
            if self.tool_error:
                return _Reply({"result": {"isError": True, "content": [{"type": "text", "text": self.tool_error}]}})
            return _Reply({"result": {"content": [{"type": "text", "text": json.dumps({"id": "universal-multi-angle-grid"})}]}})

        monkeypatch.setattr(aiohttp.ClientSession, "request", fake_socket)

    async def run(self, handle, project=PROJECT):
        turn = TurnRequest(
            chat_id="synthetic-browser-1005", user_text="商品详情页，纯白无缝背景", lang="zh", goal_text="",
            model="deepseek-flash", mcp_endpoint="http://fake.invalid/mcp", history=[],
            attachments=[{"media_type": "image/png", "data": PNG}], project_id=project)

        async def emit(_event):
            return None

        return await self.p.send(turn, emit, handle), turn


def _assert_full_request(body):
    assert len(body["tools"]) == 52
    assert {tool["function"]["name"] for tool in body["tools"]} == set(CORE_MCP_TOOLS) | {local_llm.QUOTE_TOOL}
    sent_url = body["messages"][1]["content"][1]["image_url"]["url"]
    assert sent_url.startswith("data:image/jpeg;base64,")
    with Image.open(io.BytesIO(base64.b64decode(sent_url.split(",", 1)[1]))) as sent:
        assert max(sent.size) <= 1568
    assert body["thinking"] == {"type": "disabled"} and body["max_tokens"] == 8192


@pytest.mark.parametrize("setup", ["absent", "stale", "mismatched"])
async def test_closed_project_stops_before_the_first_reserve(monkeypatch, tmp_path, setup):
    if setup == "stale":
        mcp_commands._pages["gone"] = PROJECT
    elif setup == "mismatched":
        _open("other-project")
    rig = PageRig(monkeypatch, tmp_path)
    before = Path(rig.path).read_bytes()
    handle = TurnHandle()
    result, turn = await rig.run(handle)
    assert PROJECT in result.error and "open it in ComfyArt" in result.error
    assert turn.project_id == PROJECT
    assert rig.model_posts == []
    assert Path(rig.path).read_bytes() == before
    assert gate.ledger_state(rig.path)["control_state"]["attempts_total"] == 0


async def test_open_matching_tab_keeps_tools_image_and_project(monkeypatch, tmp_path):
    _open(PROJECT)
    rig = PageRig(monkeypatch, tmp_path)
    result, turn = await rig.run(TurnHandle())
    assert result.error == ""
    assert turn.attachments[0]["data"] == PNG
    assert turn.project_id == PROJECT
    assert len(rig.model_posts) == 1
    _assert_full_request(rig.model_posts[0])
    assert gate.ledger_state(rig.path)["control_state"]["attempts_total"] == 1


async def test_browser_tool_failure_blocks_the_next_post_before_the_poller(monkeypatch, tmp_path):
    _open(PROJECT)
    rig = PageRig(monkeypatch, tmp_path, tool_error=BROWSER_ERROR)
    handle = TurnHandle()
    release = asyncio.Event()

    async def poller():
        await rig.tool_seen.wait()
        await release.wait()
        handle.stop_requested = True

    watcher = asyncio.create_task(poller())
    task = asyncio.create_task(rig.run(handle))
    await rig.tool_seen.wait()
    for _ in range(8):
        await asyncio.sleep(0)
    assert len(rig.model_posts) == 1
    assert handle.stop_requested is False
    release.set()
    result, _turn = await task
    await watcher
    assert len(rig.model_posts) == 1
    _assert_full_request(rig.model_posts[0])
    assert "is not open in any browser tab" in result.error
    state = gate.ledger_state(rig.path)
    assert state["control_state"]["attempts_total"] == 1
    assert state["control_state"]["circuit_open"] is False
    assert state["inflight"] == 0


async def test_recoverable_tool_error_still_reaches_the_next_post(monkeypatch, tmp_path):
    _open(PROJECT)
    rig = PageRig(monkeypatch, tmp_path, tool_error=RECOVERABLE)
    result, _turn = await rig.run(TurnHandle())
    assert result.error == ""
    assert len(rig.model_posts) == 2
    assert gate.ledger_state(rig.path)["control_state"]["attempts_total"] == 2


def test_timeout_text_is_not_a_mandatory_stop():
    assert mcp_commands.mandatory_browser_stop(BROWSER_ERROR)
    assert mcp_commands.mandatory_browser_stop("no ComfyArt project is open in a browser tab — open one and retry")
    assert not mcp_commands.mandatory_browser_stop(
        "the ComfyArt page did not finish 'skill' within 20s; it may still complete — check get_canvas before retrying")
    assert not mcp_commands.mandatory_browser_stop(RECOVERABLE)


async def test_blocked_summary_does_not_reserve(monkeypatch, tmp_path):
    rig = PageRig(monkeypatch, tmp_path)
    before = Path(rig.path).read_bytes()
    rig.p._model_blocked = BROWSER_ERROR
    with pytest.raises(gate.LlmBudgetBlocked, match="browser_tab_required"):
        await rig.p._summarize_llm(None, "https://api.deepseek.com", "deepseek-flash", "", "Synthetic turns")
    assert rig.model_posts == []
    assert Path(rig.path).read_bytes() == before
