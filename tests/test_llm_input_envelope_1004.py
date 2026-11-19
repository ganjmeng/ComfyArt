"""Explicit unactivated context-contract profile. All HTTP/MCP are fakes."""
import asyncio
import base64
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import aiohttp
import pytest
from PIL import Image

from ComfyArt.api import provider_admin
from ComfyArt.api.mcp_tools import TOOLS
from ComfyArt.bot import llm_usd_gate as gate, llm_input_envelope as envelope, local_llm
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from ComfyArt.bot.run_budget import resolve_policy
from test_default_preflight_capture_1004 import PNG
from test_llm_usd_gate import _route, _usage, URL


@pytest.fixture(autouse=True)
def offline(monkeypatch):
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


def body():
    return {"model": "deepseek-flash", "thinking": {"type": "disabled"}, "max_tokens": 8192,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Synthetic fixture"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + PNG}}]}]}


def response():
    return {"choices": [{"message": {"role": "assistant", "content": "Synthetic done"}, "finish_reason": "stop"}],
            **_usage(20, 3)}


def controlled(tmp_path, max_posts=6, amount=gate.TWO_DOLLAR_CEILING_NANO):
    path = str(tmp_path / "context.json")
    gate.open_authorized_scope(path, amount, max_posts=max_posts)
    return path


async def through_gate(path, payload, transport, **kwargs):
    return await provider_admin.gated_llm_http(None, "POST", URL, headers={}, json_body=payload,
        transport=transport, ledger_path=path, context_contract=True, **kwargs)


@pytest.mark.parametrize("thinking,output,reserved", [(False, 8192, 324403200), (True, 65536, 393216000)])
def test_context_reserves_full_context_plus_output_not_images_twice(thinking, output, reserved):
    b = body(); b.pop("max_tokens"); b["thinking"] = {"type": "enabled" if thinking else "disabled"}
    pre = gate.prepare(b, _route(), URL, context_contract=True)
    assert pre["ok"] and pre["input_tokens"] == 1048576 and pre["max_output_tokens"] == output
    assert pre["reserved_nano"] == reserved
    assert pre["input_evidence"]["image_tokens_upper"] == 1024
    assert pre["input_evidence"]["strictly_proven"] is False
    assert pre["input_evidence"]["charged_error_contract_proven"] is False
    assert json.loads(pre["body_bytes"])["max_tokens"] == output
    # Merely preparing a profile does not activate/bind a scope or change strict mode.
    assert not gate.prepare(body(), _route(), URL)["ok"]


@pytest.mark.parametrize("mutation", ["bad_base64", "bad_crc", "assistant_image", "remote_not_frozen", "bad_url", "animated", "too_wide", "orphan_tool", "unknown_role", "reasoning_type", "unknown_part", "output_max", "stream_options", "bad_thinking", "unknown_key", "surrogate"])
async def test_invalid_request_never_counts_or_sends(tmp_path, mutation):
    path = controlled(tmp_path); b = body(); part = b["messages"][0]["content"][1]
    if mutation == "bad_base64": part["image_url"]["url"] = "data:image/png;base64,@@@"
    elif mutation == "bad_crc": part["image_url"]["url"] = "data:image/png;base64," + base64.b64encode(base64.b64decode(PNG)[:-5]).decode()
    elif mutation == "assistant_image": b["messages"][0]["role"] = "assistant"
    elif mutation == "remote_not_frozen": part["image_url"]["url"] = "https://example.invalid/image.png"
    elif mutation == "bad_url": part["image_url"]["url"] = "file:///etc/passwd"
    elif mutation in ("animated", "too_wide"):
        out = io.BytesIO()
        if mutation == "animated":
            Image.new("RGB", (2, 2), "red").save(out, format="GIF", save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")], duration=10)
            mime = "image/gif"
        else:
            Image.new("RGB", (4097, 1)).save(out, format="PNG"); mime = "image/png"
        part["image_url"]["url"] = f"data:{mime};base64," + base64.b64encode(out.getvalue()).decode()
    elif mutation == "orphan_tool": b["messages"] = [{"role": "tool", "tool_call_id": "missing", "content": "x"}]
    elif mutation == "unknown_role": b["messages"][0]["role"] = "alien"
    elif mutation == "reasoning_type": b["messages"] = [{"role": "assistant", "content": "x", "reasoning_content": 2}]
    elif mutation == "unknown_part": part["extra"] = True
    elif mutation == "output_max": b["max_tokens"] = 131072
    elif mutation == "stream_options": b["stream_options"] = {"include_usage": True}
    elif mutation == "bad_thinking": b["thinking"] = {"type": "maybe"}
    elif mutation == "unknown_key": b["external_web"] = True
    else: b["messages"][0]["content"][0]["text"] = "\ud800"
    before = Path(path).read_bytes()
    async def forbidden(*args, **kwargs): pytest.fail("No physical POST for invalid input")
    with pytest.raises(gate.LlmBudgetBlocked): await through_gate(path, b, forbidden)
    assert Path(path).read_bytes() == before
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 0


async def test_remote_url_only_uses_verified_frozen_bytes_and_never_fetches(tmp_path):
    path = controlled(tmp_path); b = body(); url = "http://example.invalid/image.png"
    b["messages"][0]["content"][1]["image_url"] = {"url": url, "detail": "original"}
    async def fake(*args, json_body, **kwargs):
        assert isinstance(json_body, envelope.FrozenJsonBody)
        sent = json_body.as_dict()
        assert sent["messages"][0]["content"][1]["image_url"] == {"url": "data:image/png;base64," + PNG, "detail": "original"}
        return response()
    await through_gate(path, b, fake, frozen_images={url: base64.b64decode(PNG)})
    assert b["messages"][0]["content"][1]["image_url"]["url"] == url


class DefaultRig:
    """Real source-default builder; full real catalog, no stored user configuration."""
    def __init__(self, monkeypatch, tmp_path, thinking):
        self.p = local_llm.LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")
        self.path = controlled(tmp_path); self.sent = []; self.mcp = []; self.thinking = thinking
        monkeypatch.setattr(self.p, "_api_headers", lambda: {})
        monkeypatch.setattr(self.p, "_run_policy", lambda: resolve_policy(env={}))
        monkeypatch.setattr(self.p, "_run_store", lambda: None)
        async def no_plan(*args, **kwargs): return None
        monkeypatch.setattr("ComfyArt.bot.shot_plan.run_plan_card", no_plan)
        async def fake_mcp(_session, _endpoint, name, args):
            assert name == "memory" and args["action"] == "add"
            self.mcp.append(name)
            return json.dumps({"memory_ids": ["fixture-memory"], "added": "warm colors"}), []
        monkeypatch.setattr(self.p, "_mcp_call_tool", fake_mcp)
        self.catalog = [{"name": name, "description": spec["description"], "inputSchema": copy.deepcopy(spec["inputSchema"])} for name, spec in TOOLS.items()]
        async def fake_http(*args, json_body, **kwargs):
            assert isinstance(json_body, envelope.FrozenJsonBody)
            self.sent.append(json_body.as_dict())
            state = gate.ledger_state(self.path)
            assert state["inflight"] == 1 and state["control_state"]["attempts_total"] == len(self.sent)
            result = response()
            if self.thinking and len(self.sent) == 1:
                result["choices"][0] = {"finish_reason": "tool_calls", "message": {"role": "assistant", "content": "", "reasoning_content": "",
                    "tool_calls": [{"id": "fixture-memory-call", "type": "function", "function": {"name": "memory", "arguments": json.dumps({"action": "add", "text": "warm colors", "category": "taste"})}}]}}
            return result
        async def request(session, method, url, *, headers, json_body=None, timeout=120):
            if str(url).endswith("/models"): return {"data": [{"id": "deepseek-flash"}]}
            if not str(url).endswith("/chat/completions"):
                assert json_body["method"] == "tools/list"
                return {"result": {"tools": self.catalog}}
            return await provider_admin.gated_llm_http(session, method, url, headers={}, json_body=json_body, timeout=timeout,
                transport=fake_http, ledger_path=self.path, context_contract=True)
        monkeypatch.setattr(self.p, "_request_json", request)

    async def run(self):
        async def emit(_event): pass
        return await self.p.send(TurnRequest(chat_id="synthetic-envelope-1004", user_text="Synthetic fixture: remember warm colors, inspect this image, and ask my preferences.",
            lang="en", goal_text="", model="deepseek-flash", mcp_endpoint="http://fake.invalid/mcp", history=[],
            attachments=[{"media_type": "image/png", "data": PNG}]), emit, TurnHandle())


@pytest.mark.parametrize("thinking", [False, True])
async def test_real_default_builder_full_tools_images_and_actual_memory_boost(monkeypatch, tmp_path, thinking):
    rig = DefaultRig(monkeypatch, tmp_path, thinking)
    result = await rig.run()
    assert not result.error
    assert len(rig.sent) == (2 if thinking else 1)
    expected = {t["name"] for t in rig.catalog if t["name"] in rig.p._host.core_tools} | {local_llm.QUOTE_TOOL}
    for b in rig.sent:
        assert {t["function"]["name"] for t in b["tools"]} == expected
        assert {"ask_user", "get_canvas", "memory", "generate_image"} <= expected
        assert b["messages"][1]["content"][1]["image_url"]["url"] == "data:image/png;base64," + PNG
    assert rig.sent[0]["thinking"] == {"type": "disabled"} and rig.sent[0]["max_tokens"] == 8192
    if thinking:
        assert rig.mcp == ["memory"]
        assert rig.sent[1]["thinking"] == {"type": "enabled"} and rig.sent[1]["reasoning_effort"] == "low"
        assert rig.sent[1]["max_tokens"] == 65536
        assert next(m for m in rig.sent[1]["messages"] if m.get("tool_calls"))["reasoning_content"] == ""
    rows = json.loads(Path(rig.path).read_text())["reservations"]
    assert len(rows) == len(rig.sent)
    for row in rows.values():
        assert row["input_bound"] == 1048576 and row["input_evidence"]["strictly_proven"] is False
        assert row["reserved_nano"] == 1048576 * 300 + row["max_output_tokens"] * 1200
        assert row["body_sha256"] in [hashlib.sha256(json.dumps(b, allow_nan=False).encode()).hexdigest() for b in rig.sent]
    output = os.environ.get("COMFYART_ENVELOPE_CAPTURE_DIR")
    if output:
        Path(output).mkdir(parents=True, exist_ok=True)
        Path(output, f"1004-envelope-{'thinking' if thinking else 'ordinary'}-fixture.json").write_text(json.dumps({
            "synthetic_input_real_default_builder": True, "real_http": 0, "real_mcp_handlers": 0,
            "fake_http_posts": len(rig.sent), "fake_mcp_calls": rig.mcp, "payloads": rig.sent,
            "reservations": rows}, ensure_ascii=False, indent=2))


async def test_context_policy_requires_existing_controlled_two_dollar_authority(tmp_path):
    path = controlled(tmp_path, amount=gate.CEILING_NANO)
    async def no_send(*args, **kwargs): pytest.fail("No automatic authority increase")
    with pytest.raises(gate.LlmBudgetBlocked) as stopped: await through_gate(path, body(), no_send)
    assert stopped.value.code == "controlled_scope_required"
    assert gate.ledger_state(path)["ceiling_nano"] == gate.CEILING_NANO
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 0


@pytest.mark.parametrize("failure", ["timeout", "aborted", "insufficient_system_resource", "unknown_usage"])
async def test_first_unknown_or_failed_context_result_stops_retry_restart(tmp_path, failure):
    path = controlled(tmp_path); calls = []
    async def fake(*args, **kwargs):
        calls.append(1)
        if failure == "timeout": raise TimeoutError("synthetic")
        result = response()
        if failure == "unknown_usage": result.pop("usage")
        else: result["choices"][0]["finish_reason"] = failure
        return result
    with pytest.raises(gate.LlmScopeStopped): await through_gate(path, body(), fake)
    before = Path(path).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked): await through_gate(path, body(), fake)
    assert len(calls) == 1 and Path(path).read_bytes() == before
    state = gate.ledger_state(path)
    assert state["control_state"]["circuit_open"] and state["accounted_nano"] == 324403200


@pytest.mark.parametrize("method,url,route", [("GET", URL, _route()), ("POST", "https://other.invalid/chat/completions", None), ("POST", URL, {**_route(), "passthrough": True})])
async def test_explicit_profile_never_falls_through_to_ungated_route(method, url, route):
    token = provider_admin._llm_lock.set(route)
    async def forbidden(*args, **kwargs): pytest.fail("Explicit context profile cannot bypass gate")
    try:
        with pytest.raises(gate.LlmBudgetBlocked) as stopped:
            await provider_admin.gated_llm_http(None, method, url, headers={}, json_body=body(), transport=forbidden, context_contract=True)
        assert stopped.value.code == "route_mismatch"
    finally:
        provider_admin._llm_lock.reset(token)


class FakeSocketResponse:
    def __init__(self, status):
        self.status = status
        self.headers = {"Location": "https://must-not-follow.invalid/redirect"} if 300 <= status < 400 else {}
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def text(self):
        return "context_length_exceeded maximum context length is 100000" if self.status == 400 else json.dumps(response())


class FakeSocketSession:
    """Only the actual aiohttp session.request boundary is fake; raw sender retained."""
    def __init__(self, path, status=200):
        self.path, self.status, self.requests = path, status, []
    def request(self, method, url, **kwargs):
        assert method == "POST" and url == URL
        assert kwargs["allow_redirects"] is False
        assert "json" not in kwargs and type(kwargs["data"]) is bytes
        assert kwargs["headers"]["Content-Type"] == "application/json"
        ledger = json.loads(Path(self.path).read_text())
        row = list(ledger["reservations"].values())[-1]
        assert row["status"] == "reserved"
        assert row["body_sha256"] == hashlib.sha256(kwargs["data"]).hexdigest()
        assert row["input_evidence"]["body_bytes"] == len(kwargs["data"])
        self.requests.append((method, url, kwargs))
        return FakeSocketResponse(self.status)


def raw_provider(monkeypatch, path):
    p = local_llm.LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")
    # This bound entry executes LocalLlmProvider._request_json unchanged. Do not
    # replace it with a fake transport: only session.request is the fake socket.
    raw_request_json = p._request_json
    async def gated(session, method, url, *, headers, json_body=None, timeout=120):
        return await provider_admin.gated_llm_http(session, method, url, headers=headers,
            json_body=json_body, timeout=timeout, transport=raw_request_json,
            ledger_path=path, context_contract=True)
    monkeypatch.setattr(p, "_request_json", gated)
    monkeypatch.setattr(p, "_api_headers", lambda: {})
    return p


async def test_actual_raw_sender_sends_exact_reserved_bytes_despite_caller_mutation(tmp_path, monkeypatch):
    path = controlled(tmp_path); payload = body()
    expected = gate.prepare(copy.deepcopy(payload), _route(), URL, context_contract=True)["body_bytes"]
    session = FakeSocketSession(path)
    p = raw_provider(monkeypatch, path)
    def mutate(stage):
        if stage == "before_replace":
            payload["model"] = "must-not-send"
            payload["messages"][0]["content"][1]["image_url"]["url"] = "https://must-not-fetch.invalid"
    gate._write_fault = mutate
    result = await p._request_json(session, "POST", URL, headers={"content-type": "incorrect"}, json_body=payload)
    assert result["choices"] and len(session.requests) == 1
    assert session.requests[0][2]["data"] == expected
    assert payload["model"] == "must-not-send"
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 1


@pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 429, 500])
async def test_raw_entry_no_redirect_or_automatic_retry_after_first_failure(tmp_path, monkeypatch, status):
    path = controlled(tmp_path); p = raw_provider(monkeypatch, path)
    session = FakeSocketSession(path, status)
    async def emit(_event): pass
    with pytest.raises(gate.LlmScopeStopped) as stopped:
        await p._llm_request(session, URL, body(), emit, TurnHandle())
    assert isinstance(stopped.value.__cause__, local_llm.LlmHttpError)
    assert stopped.value.__cause__.status == status
    assert len(session.requests) == 1
    assert gate.ledger_state(path)["accounted_nano"] == 324403200
    assert gate.ledger_state(path)["control_state"]["circuit_open"]
    # Even an upper layer's later retry re-enters the real gate and is denied.
    with pytest.raises(gate.LlmBudgetBlocked):
        await p._llm_request(session, URL, body(), emit, TurnHandle())
    assert len(session.requests) == 1
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 1


async def test_context_profile_missing_scope_does_not_initialize_default_funds(tmp_path):
    path = str(tmp_path / "missing.json")
    async def forbidden(*args, **kwargs): pytest.fail("No creation or send from a profile parameter")
    with pytest.raises(gate.LlmBudgetBlocked): await through_gate(path, body(), forbidden)
    assert not Path(path).exists() and not Path(path + ".activated").exists()


@pytest.mark.parametrize("thinking,accepted,code", [(False, 6, "scope_posts_exhausted"), (True, 5, "over_budget")])
async def test_profile_count_and_amount_limits_remain_independent(tmp_path, thinking, accepted, code):
    path = controlled(tmp_path); calls = []
    payload = body(); payload["thinking"] = {"type": "enabled" if thinking else "disabled"}
    payload["max_tokens"] = 65536 if thinking else 8192
    async def fake(*args, **kwargs):
        calls.append(1)
        return {"choices": [{"message": {"role": "assistant", "content": "fixture"}, "finish_reason": "stop"}],
                **_usage(1048576, payload["max_tokens"])}
    for _ in range(accepted): await through_gate(path, payload, fake)
    before = Path(path).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked) as blocked: await through_gate(path, payload, fake)
    assert blocked.value.code == code and Path(path).read_bytes() == before
    assert len(calls) == accepted
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == accepted
    assert gate.price_snapshot("deepseek-flash")["context_length"] == 1048576


async def test_context_profile_one_inflight_has_no_second_physical_post(tmp_path):
    path = controlled(tmp_path); entered, release = asyncio.Event(), asyncio.Event(); calls = []
    async def fake(*args, **kwargs):
        calls.append(1); entered.set(); await release.wait(); return response()
    first = asyncio.create_task(through_gate(path, body(), fake))
    await entered.wait()
    try:
        with pytest.raises(gate.LlmBudgetBlocked) as stopped: await through_gate(path, body(), fake)
        assert stopped.value.code == "scope_inflight"
        assert len(calls) == 1 and gate.ledger_state(path)["control_state"]["attempts_total"] == 1
    finally:
        release.set(); await first


async def test_real_summary_builder_has_separate_physical_post_and_count(tmp_path, monkeypatch):
    path = controlled(tmp_path, max_posts=2); p = raw_provider(monkeypatch, path); session = FakeSocketSession(path)
    await p._request_json(session, "POST", URL, headers={}, json_body=body())
    assert await p._summarize_llm(session, "https://api.deepseek.com", "deepseek-flash", "", "Synthetic history")
    assert len(session.requests) == 2
    summary = json.loads(session.requests[1][2]["data"])
    assert summary["temperature"] == 0.1 and summary["max_tokens"] == 8192 and "tools" not in summary
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 2
    with pytest.raises(gate.LlmBudgetBlocked) as stopped:
        await p._summarize_llm(session, "https://api.deepseek.com", "deepseek-flash", "", "No third post")
    assert stopped.value.code == "scope_posts_exhausted" and len(session.requests) == 2


async def test_real_overflow_fit_cannot_resend_after_failed_physical_post(tmp_path, monkeypatch):
    path = controlled(tmp_path); p = raw_provider(monkeypatch, path); session = FakeSocketSession(path, 400)
    async def emit(_event): pass
    with pytest.raises(gate.LlmScopeStopped):
        await p._llm_request_fit(session, URL, body(), emit, TurnHandle(), model="deepseek-flash", window=1048576,
            refit=lambda *_: pytest.fail("Breaker must stop automatic overflow refit/resend"))
    assert len(session.requests) == 1


@pytest.mark.parametrize("outcome", ["timeout", "crash_after_reserve"])
async def test_new_interpreter_unknown_or_crash_never_frees_context_scope(tmp_path, outcome):
    path = controlled(tmp_path)
    program = """
import asyncio,json,os,sys
sys.path.insert(0,sys.argv[1]);import conftest
from test_llm_input_envelope_1004 import through_gate,body
from test_llm_usd_gate import _route
from ComfyArt.api import provider_admin
from ComfyArt.bot import llm_usd_gate as g
provider_admin._llm_lock.set(_route())
if sys.argv[3]=='crash_after_reserve':
 def crash(stage):
  if stage=='after_replace':os._exit(91)
 g._write_fault=crash
async def fake(*args,**kwargs):raise TimeoutError('synthetic child timeout')
async def run():
 try:await through_gate(sys.argv[2],body(),fake)
 except g.LlmBudgetBlocked:pass
asyncio.run(run())
"""
    child = subprocess.run([sys.executable, "-c", program, str(Path(__file__).resolve().parent), path, outcome],
                           capture_output=True, text=True, timeout=30)
    assert child.returncode == (91 if outcome == "crash_after_reserve" else 0), child.stderr
    before = Path(path).read_bytes()
    async def no_send(*args, **kwargs): pytest.fail("A restart cannot create new authority")
    with pytest.raises(gate.LlmBudgetBlocked) as blocked: await through_gate(path, body(), no_send)
    assert blocked.value.code == ("scope_inflight" if outcome == "crash_after_reserve" else "scope_circuit_open")
    state = gate.ledger_state(path)
    assert state["control_state"]["attempts_total"] == 1 and state["accounted_nano"] == 324403200
    assert Path(path).read_bytes() == before


@pytest.mark.parametrize("limit", ["messages", "tools", "single_schema", "all_schemas", "text", "images", "body", "image_bytes", "all_image_bytes"])
async def test_profile_limit_edges_reject_before_count_or_post(tmp_path, monkeypatch, limit):
    path = controlled(tmp_path); payload = body()
    if limit == "messages": payload["messages"] = [{"role": "user", "content": "x"}] * 257
    elif limit in ("tools", "single_schema", "all_schemas"):
        count = 129 if limit == "tools" else (1 if limit == "single_schema" else 9)
        description = "x" * (65536 if limit == "single_schema" else 32768 if limit == "all_schemas" else 1)
        payload["tools"] = [{"type": "function", "function": {"name": f"fixture_{i}", "description": description, "parameters": {"type": "object"}}} for i in range(count)]
    elif limit == "text": payload["messages"][0]["content"][0]["text"] = "x" * (512 * 1024 + 1)
    elif limit == "images": payload["messages"][0]["content"] = [payload["messages"][0]["content"][1]] * 17
    elif limit == "body":
        assert envelope.MAX_BODY_BYTES == 40 * 1024 * 1024
        # Scaled threshold tests exercise the exact byte serializer without a
        # large allocation; production constant is separately asserted above.
        monkeypatch.setattr(envelope, "MAX_BODY_BYTES", len(json.dumps(payload).encode()) - 1)
    elif limit == "image_bytes":
        assert envelope.MAX_IMAGE_BYTES == 8 * 1024 * 1024
        monkeypatch.setattr(envelope, "MAX_IMAGE_BYTES", len(base64.b64decode(PNG)) - 1)
    else:
        assert envelope.MAX_ALL_IMAGE_BYTES == 24 * 1024 * 1024
        payload["messages"][0]["content"] *= 2
        monkeypatch.setattr(envelope, "MAX_ALL_IMAGE_BYTES", len(base64.b64decode(PNG)) * 2 - 1)
    before = Path(path).read_bytes()
    async def no_send(*args, **kwargs): pytest.fail("Exceeded profile bounds cannot consume POST")
    with pytest.raises(gate.LlmBudgetBlocked): await through_gate(path, payload, no_send)
    assert Path(path).read_bytes() == before
