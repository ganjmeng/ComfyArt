"""Real default builder + full real tool schemas, synthetic inputs, zero sockets.

Optional COMFYART_PREFLIGHT_CAPTURE_DIR saves public/synthetic payloads for local
review. No user account/settings/credential is read; no MCP handler is invoked.
"""
import base64
import copy
import io
import hashlib
import inspect
import json
import os
from pathlib import Path

import aiohttp
import pytest
from PIL import Image

from ComfyArt.api import provider_admin
from ComfyArt.api.mcp_tools import TOOLS
from ComfyArt.bot import agent_loop, llm_usd_gate as gate, local_llm
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy
from test_llm_usd_gate import _route


PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOoWHACAAN0AeF2Y/iPAAAAAElFTkSuQmCC"


def source(fn):
    return f"{Path(inspect.getsourcefile(fn)).relative_to(Path(__file__).resolve().parents[1])}:{inspect.getsourcelines(fn)[1]}"


@pytest.mark.parametrize("branch", ["ordinary_first_request", "post_memory_thinking"])
async def test_default_builder_zero_send_preflight(tmp_path, monkeypatch, branch):
    monkeypatch.setenv("COMFYART_LLM_USD_GATE", "1")
    # Preserve a genuinely valid image fixture, not merely a PNG-looking URL.
    png_bytes = base64.b64decode(PNG, validate=True)
    with Image.open(io.BytesIO(png_bytes)) as image:
        assert image.format == "PNG" and image.size == (1, 1)
        image.verify()
    with Image.open(io.BytesIO(png_bytes)) as image:
        image.load()
    for name in list(os.environ):
        if name.endswith("_API_KEY") or name in ("OPENAI_TOKEN", "DEEPSEEK_TOKEN"):
            monkeypatch.delenv(name, raising=False)
    async def forbidden_socket(*args, **kwargs):
        raise AssertionError("No HTTP sockets permitted in capture")
    monkeypatch.setattr(aiohttp.ClientSession, "_request", forbidden_socket)
    p = local_llm.LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")
    monkeypatch.setattr(p, "_api_headers", lambda: {})  # Never load provider secrets.
    monkeypatch.setattr(p, "_run_policy", lambda: resolve_policy(env={}))
    monkeypatch.setattr(p, "_run_store", lambda: None)
    async def no_plan(*args, **kwargs):
        return None
    monkeypatch.setattr("ComfyArt.bot.shot_plan.run_plan_card", no_plan)
    captured, scripts, fake_tools = [], [], []
    # Same real static catalog the MCP tools/list endpoint exposes for a bot
    # turn. The real _mcp_list_tools still applies the default host's core filter.
    catalog = [{"name": name, "description": spec["description"], "inputSchema": copy.deepcopy(spec["inputSchema"])}
               for name, spec in TOOLS.items()]
    async def fake_mcp(_session, _endpoint, name, args):
        assert branch == "post_memory_thinking" and name == "memory"
        fake_tools.append(name)
        return json.dumps({"memory_ids": ["synthetic-memory-id"], "added": "synthetic warm colors"}), []
    monkeypatch.setattr(p, "_mcp_call_tool", fake_mcp)
    sent = []

    async def forbidden_transport(*args, **kwargs):
        # The gate may now send a proven planner-image request. This stand-in is
        # not a socket; aiohttp.ClientSession._request stays forbidden above.
        sent.append(kwargs.get("json_body"))
        return {"choices": [{"message": {"role": "assistant", "content": "source card"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2,
                          "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 1,
                          "prompt_tokens_details": {"cached_tokens": 0}}}
    async def request(session, method, url, *, headers, json_body=None, timeout=120):
        if str(url).endswith("/models"):
            # Synthetic endpoint catalog; default fallback resolver remains real.
            return {"data": [{"id": "deepseek-flash"}]}
        if not str(url).endswith("/chat/completions"):
            assert json_body["method"] == "tools/list"
            return {"result": {"tools": catalog}}
        if branch == "post_memory_thinking" and not scripts:
            scripts.append("synthetic initial model response; not a sent request")
            return {"choices": [{"message": {"role": "assistant", "content": "", "reasoning_content": "",
                    "tool_calls": [{"id": "fixture-memory", "type": "function", "function": {
                        "name": "memory", "arguments": json.dumps({"action": "add", "text": "synthetic warm colors", "category": "taste"})}}]}}]}
        adapted = provider_admin.adapt_llm_body(copy.deepcopy(json_body), url)
        preflight = gate.prepare(copy.deepcopy(adapted), _route(), str(url))
        mode_defaults = copy.deepcopy(adapted)
        output_cap, output_code = gate.apply_output_cap(mode_defaults)
        bound = gate.official_input_bound(adapted, gate.price_snapshot("deepseek-flash"))
        captured.append({"payload": adapted, "preflight": preflight,
                         "secondary_production_bound": {"ok": bound.ok, "code": bound.code, "detail": bound.detail},
                         "output_cap_on_blocked_payload": adapted.get("max_tokens"),
                         "mode_default_if_output_stage_reached": output_cap,
                         "output_cap_code": output_code})
        return await provider_admin.gated_llm_http(
            session, method, url, headers={}, json_body=json_body, timeout=timeout,
            transport=forbidden_transport, ledger_path=str(tmp_path / "never-created.json"))
    monkeypatch.setattr(p, "_request_json", request)
    token = provider_admin._llm_lock.set(_route())
    async def emit(_event):
        pass
    try:
        result = await p.send(TurnRequest(
            chat_id="synthetic-preflight-1004", user_text="Synthetic fixture: inspect this reference image and ask my preferences before changing the canvas.",
            lang="en", goal_text="", model="deepseek-flash", mcp_endpoint="http://fake.invalid/mcp",
            history=[], attachments=[{"media_type": "image/png", "data": PNG}]), emit, TurnHandle())
    finally:
        provider_admin._llm_lock.reset(token)
    assert len(captured) == 1 and not result.error
    item = captured[0]
    assert item["preflight"]["ok"] is True and item["preflight"]["code"] == "ready"
    assert item["preflight"]["input_evidence"]["mode"] == "planner_image_cap"
    assert item["preflight"]["input_evidence"]["image_tokens"] == 1024
    assert item["preflight"]["input_tokens"] == item["preflight"]["text_bytes"] + 1024
    assert item["preflight"]["reserved_nano"] <= gate.SKILL_CALL_CAP_NANO
    assert len(sent) == 1
    body = item["payload"]
    names = [t["function"]["name"] for t in body["tools"]]
    expected_names = [t["name"] for t in catalog if t["name"] in p._host.core_tools]
    assert set(names) == set(expected_names) | {local_llm.QUOTE_TOOL}
    assert {"ask_user", "get_canvas", "memory"} <= set(names)
    image_parts = [part for message in body["messages"] if isinstance(message.get("content"), list)
                   for part in message["content"] if part.get("type") == "image_url"]
    sent_url = image_parts[0]["image_url"]["url"]
    assert sent_url.startswith("data:image/jpeg;base64,")
    sent_raw = base64.b64decode(sent_url.split(",", 1)[1])
    with Image.open(io.BytesIO(sent_raw)) as sent_im:
        assert max(sent_im.size) <= 1568
    assert body["tool_choice"] == "auto" and body["temperature"] == 0.2
    assert body["thinking"] == {"type": "enabled" if branch == "post_memory_thinking" else "disabled"}
    assert item["mode_default_if_output_stage_reached"] == (65536 if scripts else 8192)
    assert fake_tools == (["memory"] if scripts else [])
    output_dir = os.environ.get("COMFYART_PREFLIGHT_CAPTURE_DIR")
    if output_dir:
        directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True)
        # Body contains only repository prompts/schemas and explicitly synthetic
        # text/image/tool-result fixtures. Headers and credentials are absent.
        raw = json.dumps(body, ensure_ascii=False, indent=2).encode()
        (directory / f"1004-default-{branch}-sanitized.json").write_bytes(raw)
        report = {"branch": branch, "fixture_not_real_user_capture": True,
                  "configuration": "source defaults, official Flash route; no saved account settings read",
                  "real_http_calls": 0, "real_mcp_handler_calls": 0, "fake_mcp_calls": fake_tools,
                  "synthetic_initial_model_responses": scripts, "tool_count": len(names), "tool_names": names,
                  "image_count": len(image_parts), "image_fixture": "synthetic 1x1 PNG data URL",
                  "payload_sha256": hashlib.sha256(raw).hexdigest(), "payload_bytes_pretty_json": len(raw),
                  **{k: v for k, v in item.items() if k != "payload"},
                  "sources": {"send_builder": source(p.send), "agent_loop": source(agent_loop.run),
                              "mcp_filter": source(p._mcp_list_tools), "tool_builder": source(p._build_tools),
                              "user_image_builder": source(local_llm._user_content), "adapt": source(provider_admin.adapt_llm_body),
                              "gate": source(provider_admin.gated_llm_http), "preflight": source(gate.prepare),
                              "structural_block": source(gate.structural_block), "input_bound": source(gate.official_input_bound),
                              "output_cap": source(gate.apply_output_cap)},
                  "limits": "Manifest validity never substitutes input proof. Images/MCP were retained. Structural rejection precedes output-cap insertion; absent max_tokens is reported as null, not an on-wire 8192/65536."}
        (directory / f"1004-default-{branch}-preflight-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
