"""#706: identical-call guard, garbled tool names, and generate_image that never submitted.

No WaveSpeed call. The guard is pure; the loop tests use a scripted LLM and a fake MCP.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.bot.guide import CORE_MCP_TOOLS
from ComfyArt.bot.local_llm import LocalLlmProvider, explain_unsubmitted, model_call_failed
from ComfyArt.bot.run_budget import IdenticalCallGuard, unknown_tool_message
from tests.test_agent_budget_391 import Rig, calls, reply, stop_of

GARBLED = "cofyart_m_cp_m_t_s.m_s"
SKILL_ARGS = {"action": "read", "name": "电商高端工作室模特摄影"}
GEN_ARGS = {"prompt": "studio look", "model": "wavespeed-ai/flux-kontext-pro"}


@pytest.fixture
def store():
    from ComfyArt.api.run_store_sqlite import SqliteRunStore
    from ComfyArt.bot.run_store import set_run_store
    saved = SqliteRunStore()
    set_run_store(saved)
    yield saved
    set_run_store(None)


def test_identical_call_guard_blocks_the_fourth() -> None:
    """Four identical calls: the first three pass, the fourth is the one that trips."""
    guard = IdenticalCallGuard()
    seen = [guard.blocks("generate_image", dict(GEN_ARGS)) for _ in range(4)]
    assert seen == [False, False, False, True]
    assert guard.blocks("generate_image", dict(GEN_ARGS)) is True  # still blocked, not a 5th run


def test_identical_call_guard_resets_on_different_args_and_ignores_polls() -> None:
    guard = IdenticalCallGuard()
    assert [guard.blocks("generate_image", {"prompt": p}) for p in "abc"] == [False, False, False]
    skill = {"action": "read", "name": "pose-fission"}
    # one different call starts a new streak; the 4th identical skill read is the one that trips
    assert [guard.blocks("skill", skill) for _ in range(4)] == [False, False, False, True]
    fresh = IdenticalCallGuard()
    assert [fresh.blocks("wait_generation", {"ids": ["job-1"]}) for _ in range(6)] == [False] * 6
    # a poll breaks a generate streak: three, a wait, three more, and only the next one trips
    streak = IdenticalCallGuard()
    assert [streak.blocks("generate_image", GEN_ARGS) for _ in range(3)] == [False, False, False]
    assert streak.blocks("wait_generation", {"ids": ["job-1"]}) is False
    assert [streak.blocks("generate_image", GEN_ARGS) for _ in range(3)] == [False, False, False]
    assert streak.blocks("generate_image", GEN_ARGS) is True


def test_garbled_tool_name_hints_skill() -> None:
    msg = unknown_tool_message(GARBLED, SKILL_ARGS, known=CORE_MCP_TOOLS, lang="zh")
    assert f"`{GARBLED}`" in msg
    assert "没有名为" in msg
    assert "`skill`" in msg
    assert "action" in msg and "read" in msg
    en = unknown_tool_message(GARBLED, SKILL_ARGS, known=CORE_MCP_TOOLS, lang="en")
    assert "skill" in en and "did not run" in en
    assert unknown_tool_message("nope", {}, known=CORE_MCP_TOOLS, lang="zh")


def test_quote_only_and_model_refusal_explain_why_nothing_submitted() -> None:
    quote = explain_unsubmitted("generate_image", json.dumps({
        "price": 0.04, "confirm": True, "model": "wavespeed-ai/flux-kontext-pro",
    }), "zh")
    assert quote is not None
    agent, user = quote
    assert "没有提交" in agent and "报价" in agent and "没有提交" in user
    assert model_call_failed("generate_image", GEN_ARGS, agent) is None  # not a silent model switch

    refused = explain_unsubmitted("generate_image", json.dumps({
        "status": "failed",
        "error": "content moderation refused the prompt",
        "model": "wavespeed-ai/flux-kontext-pro",
    }), "zh")
    assert refused is not None and "没有提交" in refused[0] and "moderation" in refused[0]
    assert model_call_failed("generate_image", GEN_ARGS, refused[0]) is None

    empty = explain_unsubmitted("generate_image", "", "en")
    assert empty is not None and "did not submit" in empty[0] and "nothing" in empty[1].lower()

    # a real submit, a user cancel, and a task that failed after submit stay on their own paths
    assert explain_unsubmitted("generate_image", json.dumps({"ids": ["shape:1"], "model": "m"}), "zh") is None
    assert explain_unsubmitted("generate_image", "已取消该生成，未扣费。", "zh") is None
    failed = json.dumps({"status": "failed", "error": "WaveSpeed task failed", "model": "m"})
    assert explain_unsubmitted("generate_image", failed, "zh") is None
    assert model_call_failed("generate_image", {"model": "m"}, failed) == "m"


async def test_fourth_identical_call_in_one_step_does_not_run(monkeypatch, store) -> None:
    """One assistant message with 4 identical generate_image calls: only 3 reach MCP."""
    script = [calls(*[("generate_image", GEN_ARGS)] * 4), reply("done")]
    r = Rig(monkeypatch, script, store=store,
            mcp=lambda name, a, i: json.dumps({"ids": [f"shape:{i}"]}))
    res, _ev = await r.send("画四张一样的")
    assert len(r.paid_mcp()) == 3
    assert stop_of(res)["sub"] == "repeat"
    assert "第 4 次已拦截" in res.error
    assert "生成图像" in res.error


async def test_skill_read_loop_stops_on_the_fourth_not_the_sixth(monkeypatch, store) -> None:
    read = ("skill", dict(SKILL_ARGS))
    r = Rig(monkeypatch, lambda m, n: calls(read), store=store,
            mcp=lambda name, a, i: json.dumps({"id": "studio-model", "instructions": "shoot"}))
    res, ev = await r.send("工作室模特")
    # The first read hits MCP; the next two reuse the skill cache but still show a row.
    # The 4th identical read is blocked, so this never runs out to six 「技能加载完成」.
    reads = [e for e in ev if e.t == "tool_use" and e.name == "skill"]
    assert len(reads) == 3
    assert len(r.mcp) == 1
    assert stop_of(res)["sub"] == "repeat"
    assert "第 4 次已拦截" in res.error


async def test_garbled_tool_call_returns_the_hint_and_does_not_hit_mcp(monkeypatch, store) -> None:
    script = [calls((GARBLED, SKILL_ARGS)), reply("改用 skill 再读")]
    r = Rig(monkeypatch, script, store=store)
    res, ev = await r.send("读取技能")
    assert r.mcp == []
    tr = next(e for e in ev if e.t == "tool_result")
    assert tr.is_error is True
    assert GARBLED in tr.text and "`skill`" in tr.text and "没有名为" in tr.text
    assert any(e.t == "notify" and "`skill`" in e.text for e in ev)
    assert stop_of(res)["reason"] == "done"


async def test_quote_only_generate_is_an_error_and_is_not_submitted_again(monkeypatch, store) -> None:
    script = [calls(("generate_image", GEN_ARGS)), reply("已经告诉用户了")]

    def mcp(name, args, i):
        return json.dumps({"price": 0.04, "confirm": True, "model": GEN_ARGS["model"]})

    r = Rig(monkeypatch, script, store=store, mcp=mcp)
    res, ev = await r.send("姿势裂变")
    assert [c[0] for c in r.mcp] == ["generate_image"]  # no fallback, no second submit
    tr = next(e for e in ev if e.t == "tool_result" and e.name == "generate_image")
    assert tr.is_error is True and "没有提交" in tr.text and "报价" in tr.text
    note = next(e for e in ev if e.t == "notify")
    assert "没有提交" in note.text and "报价" in note.text
    assert stop_of(res)["reason"] == "done"


async def test_model_refusal_is_surfaced_and_not_silently_switched(monkeypatch, store) -> None:
    script = [calls(("generate_image", GEN_ARGS)), reply("已经告诉用户了")]

    def mcp(name, args, i):
        if name == "ask_user":
            return json.dumps({"status": "answered", "selected": ["yes"]})
        return json.dumps({
            "status": "failed",
            "error": "content moderation refused the prompt",
            "model": GEN_ARGS["model"],
        })

    r = Rig(monkeypatch, script, store=store, mcp=mcp)
    _res, ev = await r.send("姿势裂变")
    assert [c[0] for c in r.mcp] == ["generate_image"]
    tr = next(e for e in ev if e.t == "tool_result" and e.name == "generate_image")
    assert tr.is_error is True and "没有提交" in tr.text and "moderation" in tr.text
    assert any(e.t == "notify" and "没有提交" in e.text for e in ev)


async def test_rpc_unknown_tool_is_not_an_empty_result(monkeypatch) -> None:
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        return {"jsonrpc": "2.0", "id": "call-x",
                "error": {"code": -32602, "message": f"unknown tool {GARBLED!r}"}}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    text, images = await provider._mcp_call_tool(None, "http://x/mcp", GARBLED, SKILL_ARGS)
    assert text.startswith("[tool error]")
    assert "skill" in text and GARBLED in text
    assert images == []
