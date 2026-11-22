"""Drive the real agent loop and the legacy local-model loop.

Tools are mocked. generate/wait still call the brand recorders the canvas
handler calls, and the assertions are the delta events each loop emits.
No WaveSpeed call.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.api import brand_identity as brand
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.providers import TurnHandle
from ComfyArt.bot.run_budget import resolve_policy
from test_agent_budget_391 import Rig, calls, reply
from test_brand_wrapup_1027 import SUCCESS, _reach_finals

SLOTS = ("spec", "cup", "bag", "storefront")
LINK = "https://example.com/spec.png"
LINK2 = "https://example.com/b.png"


def _deltas(events) -> list[str]:
    return [e.text for e in events if e.t == "delta" and e.text]


def _running():
    return {"status": "running", "results": [
        {"id": f"h-{slot}", "status": "running"} for slot in SLOTS]}


def _done():
    return {"status": "done", "results": [
        {"id": f"h-{slot}", "status": "done", "shapes": [f"shape:{slot}"], "urls": [f"/{slot}.png"]}
        for slot in SLOTS]}


def _one_error():
    rows = []
    for slot in SLOTS:
        if slot == "cup":
            rows.append({"id": "h-cup", "status": "error", "shapes": [], "error": "generation failed"})
        else:
            rows.append({"id": f"h-{slot}", "status": "done", "shapes": [f"shape:{slot}"], "urls": [f"/{slot}.png"]})
    return {"status": "done", "results": rows}


async def _drive(monkeypatch, script, mcp, *, budget: bool, handle=None):
    brand.reset_for_tests()
    BOT_CHAT_ID.set("c")
    _reach_finals()
    rig = Rig(monkeypatch, script, mcp=mcp)

    async def confirm_plan(spec, turn, handle, **_kw):
        # Brand stages always quote. This file has no live turn, so the real
        # confirm would return unattended and never reach generate/wait.
        return "start"

    monkeypatch.setattr(rig.p, "_confirm_plan", confirm_plan)
    if not budget:
        pol = resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"})
        monkeypatch.setattr(rig.p, "_run_policy", lambda: pol)
    res, events = await rig.send("做品牌", goal="", handle=handle or TurnHandle())
    return res, events


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_progress_then_list_then_duplicate_keeps_links(monkeypatch, budget):
    waits = {"n": 0}

    def script(messages, n):
        if n == 0:
            return calls(*((
                "generate_image",
                {"prompt": slot, "skill": brand.SKILL, "brand_slot": slot},
            ) for slot in SLOTS))
        if n == 1:
            return {
                "choices": [{"message": {
                    "content": f"还在生成最后一张。\n下载：{LINK}",
                    "tool_calls": [{"id": "w1", "function": {
                        "name": "wait_generation",
                        "arguments": json.dumps({"ids": [f"h-{s}" for s in SLOTS]}),
                    }}],
                }}],
            }
        if n == 2:
            return {
                "choices": [{"message": {
                    "content": SUCCESS,
                    "tool_calls": [{"id": "w2", "function": {
                        "name": "wait_generation",
                        "arguments": json.dumps({"ids": [f"h-{s}" for s in SLOTS]}),
                    }}],
                }}],
            }
        return reply(f"补充说明。\n本次交付清单：又一份。\n下载：{LINK2}")

    def mcp(name, args, i):
        if name == "generate_image":
            slot = args["brand_slot"]
            brand.record_submitted(args, {"ids": [f"h-{slot}"]})
            return json.dumps({"ids": [f"h-{slot}"]})
        if name == "wait_generation":
            waits["n"] += 1
            # The wait tool polls while the payload says running. The first
            # batch stays running so the loop must not flush; the next tool
            # call is the completion.
            payload = _running() if waits["n"] <= 12 else _done()
            brand.record_wait(payload)
            return json.dumps(payload)
        return json.dumps({})

    _res, events = await _drive(monkeypatch, script, mcp, budget=budget)
    text = "\n".join(_deltas(events))
    assert "还在生成最后一张" in text
    assert LINK in text and LINK2 in text
    assert "补充说明" in text
    assert SUCCESS in text
    assert "又一份" not in text
    assert text.index(LINK) < text.index(SUCCESS)


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_explicit_failure_is_named_and_the_success_list_is_not(monkeypatch, budget):
    def script(messages, n):
        if n == 0:
            return calls(*((
                "generate_image",
                {"prompt": slot, "skill": brand.SKILL, "brand_slot": slot},
            ) for slot in SLOTS))
        if n == 1:
            return {
                "choices": [{"message": {
                    "content": SUCCESS + "\n下载：" + LINK,
                    "tool_calls": [{"id": "w", "function": {
                        "name": "wait_generation",
                        "arguments": json.dumps({"ids": [f"h-{s}" for s in SLOTS]}),
                    }}],
                }}],
            }
        return reply("失败之后的说明")

    def mcp(name, args, i):
        if name == "generate_image":
            slot = args["brand_slot"]
            brand.record_submitted(args, {"ids": [f"h-{slot}"]})
            return json.dumps({"ids": [f"h-{slot}"]})
        if name == "wait_generation":
            payload = _one_error()
            brand.record_wait(payload)
            return json.dumps(payload)
        return json.dumps({})

    _res, events = await _drive(monkeypatch, script, mcp, budget=budget)
    text = "\n".join(_deltas(events))
    assert "没有落图" in text and "外带杯与杯套" in text
    assert "本次交付清单" not in text
    assert LINK in text
    assert "失败之后的说明" in text
    assert text.count("没有落图") == 1


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_cancel_while_running_does_not_announce_a_failure(monkeypatch, budget):
    handle = TurnHandle()

    def script(messages, n):
        if n == 0:
            return calls(*((
                "generate_image",
                {"prompt": slot, "skill": brand.SKILL, "brand_slot": slot},
            ) for slot in SLOTS))
        return {
            "choices": [{"message": {
                "content": SUCCESS,
                "tool_calls": [{"id": "w", "function": {
                    "name": "wait_generation",
                    "arguments": json.dumps({"ids": [f"h-{s}" for s in SLOTS]}),
                }}],
            }}],
        }

    def mcp(name, args, i):
        if name == "generate_image":
            slot = args["brand_slot"]
            brand.record_submitted(args, {"ids": [f"h-{slot}"]})
            return json.dumps({"ids": [f"h-{slot}"]})
        if name == "wait_generation":
            payload = _running()
            brand.record_wait(payload)
            handle.stop_requested = True
            return json.dumps(payload)
        return json.dumps({})

    res, events = await _drive(monkeypatch, script, mcp, budget=budget, handle=handle)
    text = "\n".join(_deltas(events))
    assert "仍在生成" in text
    assert "规范卡" in text and "外带杯与杯套" in text
    assert "没有落图" not in text
    assert "本次交付清单" not in text
    assert res.aborted or (res.run and res.run.get("stop", {}).get("reason") == "user_stop")
    # The next turn on this chat does not replay the discarded list or the same note.
    assert brand.release_wrapup("zh") == ""
    assert brand.end_turn("zh") == ""


QUESTION = "你问“本次交付清单”是什么意思：它是文件列表，不含商标注册服务。"
BLOCK = "\n".join([
    "本次交付清单：",
    "- 规范卡、杯、纸袋、门头均已生成。",
    "如实说明的边界：需要矢量替换，色值为屏幕估算。",
    "下一步：菜单板。",
])
SAME_LINE = "本次交付清单：四张。下载地址 /download/qimu.zip，请用这个链接。"


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_quoted_title_multiline_block_and_same_line_download(monkeypatch, budget):
    waits = {"n": 0}

    def script(messages, n):
        if n == 0:
            gen = calls(*((
                "generate_image",
                {"prompt": slot, "skill": brand.SKILL, "brand_slot": slot},
            ) for slot in SLOTS))
            gen["choices"][0]["message"]["content"] = QUESTION
            return gen
        if n == 1:
            return {
                "choices": [{"message": {
                    "content": BLOCK,
                    "tool_calls": [{"id": "w1", "function": {
                        "name": "wait_generation",
                        "arguments": json.dumps({"ids": [f"h-{s}" for s in SLOTS]}),
                    }}],
                }}],
            }
        if n == 2:
            # The first wait stays on running for its twelve polls. This later
            # call is the completion, so the held block can be released.
            return {
                "choices": [{"message": {
                    "content": "",
                    "tool_calls": [{"id": "w2", "function": {
                        "name": "wait_generation",
                        "arguments": json.dumps({"ids": [f"h-{s}" for s in SLOTS]}),
                    }}],
                }}],
            }
        return reply(SAME_LINE)

    def mcp(name, args, i):
        if name == "generate_image":
            slot = args["brand_slot"]
            brand.record_submitted(args, {"ids": [f"h-{slot}"]})
            return json.dumps({"ids": [f"h-{slot}"]})
        if name == "wait_generation":
            waits["n"] += 1
            payload = _running() if waits["n"] <= 12 else _done()
            brand.record_wait(payload)
            return json.dumps(payload)
        return json.dumps({})

    _res, events = await _drive(monkeypatch, script, mcp, budget=budget)
    text = "\n".join(_deltas(events))
    assert QUESTION in text
    assert "/download/qimu.zip" in text and "请用这个链接" in text
    assert "本次交付清单：四张" not in text
    assert "均已生成" in text and "如实说明的边界" in text and "下一步：菜单板" in text
    claim_at = next(i for i, e in enumerate(events) if e.t == "delta" and e.text and "均已生成" in e.text)
    placed = next(i for i, e in enumerate(events)
                  if e.t == "tool_result" and "shape:spec" in str(getattr(e, "text", "")))
    assert claim_at > placed
    assert text.index(QUESTION) < text.index("均已生成")
    assert text.index("/download/qimu.zip") > text.index("均已生成")
