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
    assert "before you reply" in canvas


def test_fallback_skips_when_turn_wrote_memory():
    pro = (ROOT / "src/proactive.ts").read_text()
    assert "wrote: turnWroteMemory(reply.blocks)" in pro
    assert "if (plan?.memory && !ex.wrote) await learnMemory(" in pro
    layout = (ROOT / "src/botLayout.ts").read_text()
    assert "memory_ids: added.map((m) => m.id)" in layout
    ui = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert "hideMemCall(b)) return" in ui
    assert "e.memory_updated ? appendBlock(next, e.memory_updated)" in (ROOT / "src/bot.ts").read_text()


def test_live_second_thought_renders_like_first_live_thought():
    """#413 design: no status box repeating 思考中… under a live thought on the rail; latest line inline."""
    ui = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert "live && !mediaHero && live.kind !== 'thought' && <div className=\"ca-process__status\">" in ui
    assert "s.live && s.kind === 'thought' && !open && s.text?.trim() ?" in ui
    assert '<span className="ca-process__inline">' in ui
    css = (ROOT / "src/styles/overlays.css").read_text()
    inline = css.split(".ca-process__inline {")[1].split("}")[0]
    assert "grid-column: 3" in inline and "display: flex" in inline
    assert 'className="ca-chat__arg ca-process__arg" data-testid="live-thought-inline"' in ui
