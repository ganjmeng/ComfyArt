"""#413: memory write is a tool inside the agent loop. Mocked LLM / MCP only ($0)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ComfyArt.api.bot_turns import _TurnState, _apply_event, memory_updated_block
from ComfyArt.bot.providers import TurnHandle

from test_agent_budget_391 import Rig

ROOT = Path(__file__).resolve().parents[1]


def _think_call(thought, name, args):
    return {"choices": [{"message": {"content": f"<think>{thought}</think>", "tool_calls": [
        {"id": "mem1", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}}]}


def _think_reply(thought, text):
    return {"choices": [{"message": {"content": f"<think>{thought}</think>{text}", "tool_calls": []}}]}


def _rig(monkeypatch, script, mcp):
    rig = Rig(monkeypatch, script, mcp=mcp)
    orig = rig.p._request_json

    async def with_memory_tool(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            return await orig(session, method, url, headers=headers, json_body=json_body, timeout=timeout)
        return {"result": {"tools": [{"name": t} for t in ("memory", "generate_image", "get_canvas")]}}
    monkeypatch.setattr(rig.p, "_request_json", with_memory_tool)
    rig.bodies = []

    async def capture(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            rig.bodies.append(dict(json_body))
        return await with_memory_tool(session, method, url, headers=headers, json_body=json_body, timeout=timeout)
    monkeypatch.setattr(rig.p, "_request_json", capture)
    return rig


def _blocks(events):
    st = _TurnState(TurnHandle(), "c", "m")
    payloads = [_apply_event(st, e) for e in events]
    return st.blocks, [p for p in payloads if p]


def test_tool_path_order_thought_memory_thought_reply(monkeypatch):
    script = [_think_call("用户说喜欢暖色调，先记下来。", "memory", {"action": "add", "text": "喜欢暖色调", "category": "taste"}),
              _think_reply("记忆已写入，组织回答。", "已记住。海报方向：落日橙。")]
    mcp = lambda name, args, n: json.dumps({"added": args.get("text"), "memory_ids": ["m1"]}, ensure_ascii=False)
    rig = _rig(monkeypatch, script, mcp)
    res, events = asyncio.run(rig.send("记住我喜欢暖色调，然后给我一个海报方向"))
    assert not res.error
    assert rig.n == 2  # no extra LLM call: the second thought is the loop's own next step
    assert [c[0] for c in rig.mcp] == ["memory"]
    blocks, payloads = _blocks(events)
    order = [b["type"] for b in blocks if b["type"] in ("thinking", "memory_updated", "text")]
    assert order == ["thinking", "memory_updated", "thinking", "text"]
    mem = next(b for b in blocks if b["type"] == "memory_updated")
    assert mem["memory_ids"] == ["m1"] and mem["texts"] == ["喜欢暖色调"] and mem["tool_id"] == "mem1"
    assert any(p.get("memory_updated") == mem for p in payloads)  # broadcast live with the tool result


def test_no_memory_turn_unchanged(monkeypatch):
    rig = _rig(monkeypatch, [_think_reply("直接回答。", "海报方向：落日橙。")], None)
    res, events = asyncio.run(rig.send("给我一个海报方向"))
    blocks, payloads = _blocks(events)
    assert [b["type"] for b in blocks if b["type"] != "run_stop"] == ["thinking", "text"]
    assert not any("memory_updated" in p for p in payloads)


def test_only_successful_add_with_ids_makes_a_row():
    use = [{"type": "tool_use", "id": "a", "name": "memory", "input": {"action": "add", "text": "x"}}]
    ok = json.dumps({"added": "x", "memory_ids": ["m9"]})
    assert memory_updated_block(use, "a", "mcp__comfyart__memory", ok, "success")["memory_ids"] == ["m9"]
    assert memory_updated_block(use, "a", "memory", ok, "error") is None
    assert memory_updated_block(use, "a", "memory", json.dumps({"added": "x", "memory_ids": []}), "success") is None  # duplicate
    lst = [{"type": "tool_use", "id": "a", "name": "memory", "input": {"action": "list"}}]
    assert memory_updated_block(lst, "a", "memory", ok, "success") is None
    assert memory_updated_block(use, "a", "skill", ok, "success") is None


def test_rules_in_tool_description_and_fallback():
    canvas = (ROOT / "api/mcp_tools/canvas.py").read_text()
    pro = (ROOT / "src/proactive.ts").read_text()
    for src in (canvas, pro):
        assert "confirmed or chose" in src and "trace back to one user" in src
        assert "generated content itself" in src and "one-off task details" in src
    assert "call add FIRST, then reply" in canvas


def test_fallback_skips_when_turn_wrote_memory():
    pro = (ROOT / "src/proactive.ts").read_text()
    assert "wrote: turnWroteMemory(reply.blocks)" in pro
    assert "if (plan?.memory && !ex.wrote) await learnMemory(" in pro
    layout = (ROOT / "src/botLayout.ts").read_text()
    assert "memory_ids: written.map((m) => m.id)" in layout  # #423: added + updated
    ui = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert "hideMemCall(b)) return" in ui
    assert "at < 0 ? appendBlock(next, e.memory_updated)" in (ROOT / "src/bot.ts").read_text()  # #423: append once, then replace


def test_live_second_thought_renders_like_first_live_thought():
    """#413 design: no status box repeating 思考中… under a live thought on the rail; latest line inline."""
    ui = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert "live && !mediaHero && live.kind !== 'thought' && !live.kind.startsWith('memory_') && <div className=\"ca-process__status\">" in ui
    assert "s.live && s.kind === 'thought' && !open && s.text?.trim() ?" in ui
    assert '<span className="ca-process__inline">' in ui
    css = (ROOT / "src/styles/overlays.css").read_text()
    inline = css.split(".ca-process__inline {")[1].split("}")[0]
    assert "grid-column: 3" in inline and "display: flex" in inline
    assert 'className="ca-chat__arg ca-process__arg" data-testid="live-thought-inline"' in ui


def test_prompts_say_call_memory_first_then_reply():
    """#415 product: tool description and agent system prompt both say memory FIRST, then reply; no fallback."""
    import re
    from ComfyArt.bot.guide import AGENT_GUIDE
    src = (ROOT / "api/mcp_tools/canvas.py").read_text()
    desc = re.sub(r'"\s*\n\s*"', "", src.split('"memory": _tool(')[1].split("_schema(")[0])
    for text in (desc, AGENT_GUIDE):
        flat = " ".join(text.split())
        assert "preference, brand, requirement, or makes a choice" in flat
        assert "FIRST" in flat and "then reply" in flat
        assert "do not rely on a later fallback" in flat.lower()


# --- #413 go-ahead: low reasoning only on the call right after a successful memory add ---

from ComfyArt.bot import reasoning_boost  # noqa: E402
from ComfyArt.bot.local_llm import LlmHttpError  # noqa: E402

_REASON_KEYS = ("reasoning_effort", "reasoning", "thinking")


def _plain_call(name, args, cid):
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": cid, "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]}}]}


def _mem_ok(name, args, n):
    if name == "memory":
        return json.dumps({"added": args.get("text"), "memory_ids": ["m1"]}, ensure_ascii=False)
    return json.dumps({"shapes": []})


def _boosted(body):
    return {k: body[k] for k in _REASON_KEYS if k in body}


def test_low_reasoning_only_on_call_after_memory_add(monkeypatch):
    script = [_think_call("先记下来。", "memory", {"action": "add", "text": "喜欢暖色调", "category": "taste"}),
              _plain_call("get_canvas", {}, "c2"),
              _think_reply("组织回答。", "已记住。")]
    rig = _rig(monkeypatch, script, _mem_ok)
    res, _ = asyncio.run(rig.send("记住我喜欢暖色调"))
    assert not res.error and rig.n == 3
    assert [_boosted(b) for b in rig.bodies] == [{}, {"reasoning_effort": "low"}, {}]
    assert all(b["temperature"] == 0.2 and b["tool_choice"] == "auto" for b in rig.bodies)  # rest unchanged


def test_no_boost_when_memory_add_failed_or_not_add(monkeypatch):
    for mcp, args in (
        (lambda n, a, k: json.dumps({"error": "nope"}), {"action": "add", "text": "x", "category": "taste"}),
        (_mem_ok, {"action": "list"}),
    ):
        script = [_think_call("t", "memory", args), _think_reply("t2", "ok")]
        rig = _rig(monkeypatch, script, mcp)
        asyncio.run(rig.send("hi"))
        assert [_boosted(b) for b in rig.bodies] == [{}, {}]


def test_no_boost_on_turn_without_memory(monkeypatch):
    script = [_plain_call("get_canvas", {}, "c1"), _think_reply("t", "ok")]
    rig = _rig(monkeypatch, script, _mem_ok)
    asyncio.run(rig.send("hi"))
    assert [_boosted(b) for b in rig.bodies] == [{}, {}]


def test_model_rejecting_reasoning_replies_plain_without_fake_thought(monkeypatch):
    def script(messages, n):
        if n == 0:
            return _plain_call("memory", {"action": "add", "text": "喜欢暖色调", "category": "taste"}, "mem1")
        if n == 1:
            return LlmHttpError(400, "unsupported parameter: reasoning_effort")
        return {"choices": [{"message": {"content": "已记住。", "tool_calls": []}}]}
    rig = _rig(monkeypatch, script, _mem_ok)
    res, events = asyncio.run(rig.send("记住我喜欢暖色调"))
    assert not res.error and rig.n == 3
    assert [_boosted(b) for b in rig.bodies] == [{}, {"reasoning_effort": "low"}, {}]  # retried once, plain
    assert not [e for e in events if e.t == "thinking"]  # no thought synthesized


def test_reasoning_params_per_provider():
    from ComfyArt.api import settings
    default_url = settings.SETTINGS_SPEC["bot-local-llm-url"]
    assert default_url == "https://llm.wavespeed.ai/v1"
    assert settings.SETTINGS_SPEC["bot-model-local-llm"] == "deepseek/deepseek-v4.1-flash-1017"
    rp = reasoning_boost.reasoning_params
    assert rp(default_url, "deepseek/deepseek-v4.1-flash-1017") == {"reasoning_effort": "low"}
    assert rp("https://openrouter.ai/api/v1", "x/y") == {"reasoning": {"effort": "low"}}
    assert rp("https://api.anthropic.com/v1", "claude-x") == {"thinking": {"type": "enabled", "budget_tokens": 1024}}
    assert rp("https://api.deepseek.com/v1", "deepseek-flash") == {"reasoning_effort": "low", "thinking": {"type": "enabled"}}
    assert rp("https://api.openai.com/v1", "o4") == {"reasoning_effort": "low"}
