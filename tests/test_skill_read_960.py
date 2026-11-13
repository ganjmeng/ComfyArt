"""#960 — skill text: paged reads, explicit truncation, and no silent repeat reads.

$0: real src/skills.ts through a node harness, plus the local-LLM loop with a scripted
LLM and a fake MCP. No WaveSpeed, no external model, no paid call.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from ComfyArt.bot._cli_common import TOOL_RESULT_CAP
from ComfyArt.bot.local_llm import _skill_read_key, cap_tool_result

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install")


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"skillpage960-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/skillpage960/rolldown.config.mjs"],
                   cwd=ROOT, check=True, capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


# --- real src/skills.ts: long skill text has a complete, usable read path ----------------

@needs_node
def test_long_skill_page1_is_not_the_whole_text_and_says_how_to_continue() -> None:
    r = report()
    assert r["page1IsWhole"] is False
    assert r["page1"]["has_more"] is True
    assert r["page1"]["offset"] == 0
    assert r["page1"]["next_offset"] == 3000
    assert r["page1"]["total_chars"] == r["total"]
    assert "next_offset" in r["page1"]["note"]
    assert "not a summary" in r["page1"]["note"]


@needs_node
def test_youtube_card1_spec_is_whole_on_page1_not_in_the_dropped_tail() -> None:
    """The QA failure had the card spec past `…[truncated]`; page 1 must carry all of card 1."""
    assert report()["page1HasCard1"] is True


@needs_node
def test_pages_join_to_the_exact_full_text() -> None:
    r = report()
    assert r["pageCount"] >= 2
    assert r["offsets"] == [0, 3000, 6000]
    assert r["contentsMatch"] is True  # every page is the real slice, not a summary
    assert r["joinedIsWhole"] is True  # no gap, no duplicate: the entire skill text is reachable
    assert r["lastHasMore"] is False and r["lastNext"] is None
    assert r["notes"] is True and r["metas"] == [r["total"]] * r["pageCount"]


@needs_node
def test_pages_fit_under_the_agent_tool_result_cap() -> None:
    r = report()
    assert r["page1Len"] < TOOL_RESULT_CAP
    assert r["file"]["len"] < TOOL_RESULT_CAP
    assert r["clampedLen"] == r["clampedCap"] == 3000
    assert r["small"]["match"] is True and r["small"]["offset"] == 10  # offset/limit honored


@needs_node
def test_long_bundled_file_is_paged_and_short_read_keeps_the_old_shape() -> None:
    r = report()
    assert r["file"]["isWhole"] is False and r["file"]["hasMore"] is True
    assert r["file"]["pages"] >= 2 and r["file"]["joined"] is True
    assert r["file"]["lastHasMore"] is False
    # a short skill still returns instructions (no consumer/test regression) and no page fields
    sr = r["shortRead"]
    assert sr["instructions"] == "short body"
    assert sr["hasContent"] is False and "hasMore" not in sr
    assert sr["jsonLen"] < TOOL_RESULT_CAP
    assert r["past"]["content"] == "" and r["past"]["hasMore"] is False
    assert "past the end" in r["past"]["note"]
    assert "notes.md" in r["missingPath"]["error"]  # no silent empty read


# --- the tool-result cap now says the tail is missing and how to fetch it -----------------

def test_truncation_marker_says_it_is_not_the_full_text_zh() -> None:
    text = "技能" * 3000
    out = cap_tool_result(text, "get_canvas", {}, "zh")
    assert len(out) > TOOL_RESULT_CAP
    assert out.startswith(text[:TOOL_RESULT_CAP])
    assert "…[truncated" in out
    assert "不是完整结果" in out and "不要把它当成全文" in out
    assert "缩小查询范围" in out


def test_truncation_marker_on_a_skill_read_names_offset_and_limit() -> None:
    out = cap_tool_result("s" * (TOOL_RESULT_CAP + 321), "skill", {"action": "read", "id": "youtube-channel-banner"}, "en")
    assert "NOT the complete result" in out and "do not treat it as the full text" in out.lower()
    assert 'skill action="read"' in out and "offset=<chars already read>" in out and "limit=2500" in out
    assert "truncated 321 chars" in out


def test_truncation_marker_leaves_short_results_untouched() -> None:
    assert cap_tool_result("short", "skill", {"action": "read", "id": "x"}, "zh") == "short"


def test_agent_facing_skill_schema_documents_paging() -> None:
    """Mutation: drop offset/limit from the skill schema -> the agent cannot page."""
    canvas = (ROOT / "api/mcp_tools/canvas.py").read_text(encoding="utf-8")
    seg = canvas[canvas.index('"skill": _tool('):canvas.index('"custom_workflow"')]
    assert '"offset": {"type": "integer"' in seg and '"limit": {"type": "integer"' in seg
    assert "next_offset" in seg and "offset=next_offset" in seg


def test_agent_guide_documents_paging() -> None:
    from ComfyArt.bot.guide import AGENT_GUIDE
    assert "offset=next_offset" in AGENT_GUIDE and "has_more" in AGENT_GUIDE


# --- repeat reads: one cache entry per path/page, and an explicit recovery note -----------

def test_skill_read_cache_key_separates_pages_paths_and_limits() -> None:
    base = {"action": "read", "id": "YouTube-Channel-Banner"}
    first = _skill_read_key("skill", base)
    assert first == _skill_read_key("skill", {"action": "read", "id": "youtube-channel-banner"})
    assert first != _skill_read_key("skill", {**base, "offset": 3000})
    assert first != _skill_read_key("skill", {**base, "path": "reference.md"})
    assert first != _skill_read_key("skill", {**base, "limit": 100})
    assert first != _skill_read_key("skill", {**base, "offset": 3000, "limit": 100})
    assert _skill_read_key("skill", {"action": "list"}) == ""
    assert _skill_read_key("ask_user", base) == ""


@pytest.fixture
def store():
    from ComfyArt.api.run_store_sqlite import SqliteRunStore
    from ComfyArt.bot.run_store import set_run_store
    saved = SqliteRunStore()
    set_run_store(saved)
    yield saved
    set_run_store(None)


CARD1 = {
    "questions": [
        {"id": "yt_delivery", "prompt": "这次横幅想怎么交付？", "allow_other": True,
         "options": [{"id": "A", "label": "先出三方向选择板，再做终稿"},
                     {"id": "B", "label": "直接出一张终稿，文字用精确排版渲染"},
                     {"id": "C", "label": "直接出一张终稿，文字由图像模型生成"}],
         "placeholder": "其它想法（比如一次出多个方向终稿）..."},
        {"id": "yt_banner_text", "prompt": "横幅上实际要出现哪些文字？", "allow_other": True,
         "options": [{"id": "A", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流 ＋ 每周二/五更新"},
                     {"id": "B", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流"},
                     {"id": "C", "label": "只有 Loomi Studio"}],
         "placeholder": "自己指定文案（含大小写、符号、换行）..."},
        {"id": "yt_brand_assets", "prompt": "有需要放进去的品牌资产吗？", "allow_other": True,
         "options": [{"id": "A", "label": "没有，纯图形＋文字构成识别"},
                     {"id": "B", "label": "有 Logo／头像，我上传给你"},
                     {"id": "C", "label": "需要预留真人出镜位置"}],
         "placeholder": "其它（比如指定参考图／配色）..."},
    ],
    "allow_skip": True,
    "page_count": 3,
}
ANSWERED = {"status": "answered", "selected": ["A"], "other_text": "",
            "answers": {"yt_delivery": {"selected": ["A"]}, "yt_banner_text": {"selected": ["A"]},
                        "yt_brand_assets": {"selected": ["A"]}}}


def _tool_messages(rig) -> list[str]:
    return [m["content"] for req in rig.requests for m in req
            if m.get("role") == "tool" and isinstance(m.get("content"), str)]


async def test_reading_the_next_page_is_not_a_cached_replay(monkeypatch, store) -> None:
    """Mutation (cache key without offset): page 2 is served from page 1's cache and the model loops."""
    from tests.test_agent_budget_391 import Rig, calls, reply, stop_of
    page1 = {"content": "PAGE-ONE " + "a" * 40, "offset": 0, "total_chars": 200, "next_offset": 100, "has_more": True}
    page2 = {"content": "PAGE-TWO " + "b" * 140, "offset": 100, "total_chars": 200, "next_offset": None, "has_more": False}

    def mcp(name, args, i):
        if name == "skill":
            return json.dumps(page2 if args.get("offset") else page1)
        if name == "ask_user":
            return json.dumps(ANSWERED)
        return "{}"

    script = [
        calls(("skill", {"action": "read", "id": "youtube-channel-banner"})),
        calls(("skill", {"action": "read", "id": "youtube-channel-banner", "offset": 100})),
        calls(("ask_user", CARD1)),
        reply("继续"),
    ]
    rig = Rig(monkeypatch, script, store=store, mcp=mcp)
    res, events = await rig.send("做 YouTube 频道横幅", goal="读一下技能说明并询问用户")
    skills = [c for c in rig.mcp if c[0] == "skill"]
    assert [c[1].get("offset") for c in skills] == [None, 100]  # page 2 really ran
    msgs = _tool_messages(rig)
    assert any("PAGE-ONE" in m for m in msgs) and any("PAGE-TWO" in m for m in msgs)
    assert not any(m.startswith("[cached]") for m in msgs)
    assert any(c[0] == "ask_user" for c in rig.mcp)  # reached the card, not stuck:repeat
    assert stop_of(res)["reason"] == "done" and res.error == ""


async def test_same_page_read_shows_cached_and_continues(monkeypatch, store, caplog) -> None:
    """Mutation (silent cache replay): the model sees identical text again with no recovery note."""
    from tests.test_agent_budget_391 import Rig, calls, reply, stop_of
    page1 = {"content": "PAGE-ONE " + "a" * 40, "offset": 0, "total_chars": 100, "next_offset": None, "has_more": False}

    def mcp(name, args, i):
        if name == "skill":
            return json.dumps(page1)
        if name == "ask_user":
            return json.dumps(ANSWERED)
        return "{}"

    script = [
        calls(("skill", {"action": "read", "id": "youtube-channel-banner"})),
        calls(("skill", {"action": "read", "id": "youtube-channel-banner"})),
        calls(("ask_user", CARD1)),
        reply("继续"),
    ]
    rig = Rig(monkeypatch, script, store=store, mcp=mcp)
    with caplog.at_level(logging.INFO, logger="ComfyArt.bot.local_llm"):
        res, _events = await rig.send("做 YouTube 频道横幅", goal="读一下技能说明并询问用户")
    assert len([c for c in rig.mcp if c[0] == "skill"]) == 1  # the repeat did not hit MCP again
    cached = [m for m in _tool_messages(rig) if m.startswith("[cached]")]
    assert cached and all(m == cached[0] for m in cached)  # one distinct cached result, re-sent each step
    assert "不要再读同一段" in cached[0] and "PAGE-ONE" in cached[0]
    assert any(c[0] == "ask_user" for c in rig.mcp)
    assert stop_of(res)["reason"] == "done"
    assert any("skill read from cache" in rec.getMessage() and "youtube-channel-banner" in rec.getMessage()
               for rec in caplog.records)


async def test_truncated_tool_result_tells_the_agent_it_is_incomplete(monkeypatch, store) -> None:
    """Mutation (bare `…[truncated N chars]`): the model cannot tell the tail is missing."""
    from tests.test_agent_budget_391 import Rig, calls, reply

    rig = Rig(monkeypatch, [calls(("get_canvas", {})), reply("ok")], store=store,
              mcp=lambda name, a, i: "C" * (TOOL_RESULT_CAP + 500))
    await rig.send("看画布")
    msg = next(m for m in _tool_messages(rig) if m.startswith("C"))
    assert "…[truncated 500 chars" in msg
    assert "不是完整结果" in msg and "不要把它当成全文" in msg
    assert "缩小查询范围" in msg


async def test_tool_error_result_is_marked_as_a_failed_step(monkeypatch, store) -> None:
    """Mutation: drop the `[tool error]` check -> an ask_user rejection looks like a success row."""
    from tests.test_agent_budget_391 import Rig, calls, reply

    rig = Rig(monkeypatch, [calls(("ask_user", {"allow_skip": True})), reply("ok")], store=store,
              mcp=lambda name, a, i: "[tool error] ValueError: prompt is required (or pass questions[])")
    _res, events = await rig.send("问用户")
    tr = next(e for e in events if e.t == "tool_result" and e.name == "ask_user")
    assert tr.is_error is True and "prompt is required" in tr.text
