"""#949 Full App mock e2e ($0): youtube-channel-banner inquiry card — one ask for
card 1, no empty 1/3 pages, clean placeholders, Chinese first sentence.

Walks the official skill-page path with a scripted in-process agent (no LLM)
and the mock WaveSpeed server (no submit, no quote). Replays the #925 failure:
the agent opens with "I'll read the skill first." and calls ask_user with only
Q1, page_count 3, and placeholders ending in `”,`. The real server + UI must
show all three questions as one 1/3 ask (one question per page, no empty pages), strip the junk, and (in zh)
rewrite the first sentence into Chinese.

ASK949_SHOTS=/dir keeps the zh/en after-fix screenshots. Chromium is required;
never a silent skip.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import pytest

from conftest import FakeProvider, write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_skill_param_guard_e2e_956_957 import LOC, _bind_open_project, _call
from ask_card_pages import inspect_pages

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("ASK949_SHOTS")
CJK = re.compile(r"[\u4e00-\u9fff]")
JUNK = "\u201d,"
USER_TEXT = {
    "zh": "帮我做一张 YouTube 频道横幅。频道名 Loomi Studio，内容是 AI 绘画教程和创意工作流，每周二、周五更新。风格明亮活泼。",
    "en": "Make a YouTube channel banner for Loomi Studio. AI art tutorials and creative workflows, new episodes Tue & Fri, bright and lively.",
}
FIRST = {
    "zh": "I'll read the skill first.",  # the reported English boot line; server rewrites it
    "en": "I'll read the skill first.",
}
ZH_FIRST = "我先看一下技能说明。"
DONE = {"zh": "已收到你的选择，继续下一步。", "en": "Got your choices, continuing."}

# The paid-run failure: only Q1, page_count 3, dirty placeholders.
def _partial_card1(lang: str) -> dict:
    dirty = (
        "其它想法（比如一次出多个方向终稿）..." + JUNK
        if lang == "zh"
        else "Other ideas (e.g. several direction finals at once)..." + JUNK
    )
    if lang == "zh":
        q1 = {
            "id": "yt_delivery",
            "prompt": "这次横幅想怎么交付？（影响后续步骤与文字精度）",
            "allow_other": True,
            "placeholder": dirty,
            "options": [
                {"id": "A", "label": "先出三方向选择板，再做终稿"},
                {"id": "B", "label": "直接出一张终稿，文字用精确排版渲染"},
                {"id": "C", "label": "直接出一张终稿，文字由图像模型生成"},
            ],
        }
    else:
        q1 = {
            "id": "yt_delivery",
            "prompt": "How should this banner be delivered?",
            "allow_other": True,
            "placeholder": dirty,
            "options": [
                {"id": "A", "label": "Three-direction board first, then the final"},
                {"id": "B", "label": "One final now, with text set by the exact-layout renderer"},
                {"id": "C", "label": "One final now, with text drawn by the image model"},
            ],
        }
    return {"questions": [q1], "allow_skip": True, "page_count": 3}


class ScriptedAgent(FakeProvider):
    id = "fake-ask949"
    label = "FakeAsk949"

    def __init__(self):
        super().__init__()
        self.steps = None
        self.results: list = []

    async def send(self, turn, emit, handle):
        from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
        self.last_turn = turn
        token = BOT_CHAT_ID.set(turn.chat_id)
        try:
            if self.steps:
                await self.steps(self, turn, emit)
        finally:
            BOT_CHAT_ID.reset(token)
        return self.result


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("WAVESPEED_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN", "KIE_API_KEY"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def agent(monkeypatch):
    from ComfyArt.api.settings import SETTINGS_SPEC
    from ComfyArt.bot import register_provider
    a = ScriptedAgent()
    register_provider(a)
    monkeypatch.setitem(SETTINGS_SPEC, f"bot-model-{a.id}", "")
    write_settings(**{"bot-provider": a.id, "enable-bot": True, "enable-mcp": True})
    return a


@pytest.fixture
def ws_forward(monkeypatch):
    from server import PromptServer
    sockets: list = []
    send_sync = PromptServer.instance.send_sync

    def forward(event, data, sid=None):
        send_sync(event, data, sid)
        for ws in sockets:
            ws.send(json.dumps({"type": event, "data": data}, default=str))
    monkeypatch.setattr(PromptServer.instance, "send_sync", forward)
    return sockets


async def _shot(pg, name):
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(400)
    await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


async def _open_youtube(p, app_url, lang, sockets):  # noqa: F811
    try:
        browser = await p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"chromium not available, this e2e must not skip: {e}")
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900},
                                    locale="zh-CN" if lang == "zh" else "en-US")
    await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light')")
    await pg.goto(app_url)
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-wall").wait_for(timeout=20000)
    card = pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="youtube-channel-banner"]')
    await card.scroll_into_view_if_needed()
    await card.hover()
    await card.get_by_test_id("skills-card-try").click()
    dlg = pg.locator('[data-testid="skill-run-dialog"][data-skill="youtube-channel-banner"]')
    await dlg.wait_for(timeout=15000)
    note = dlg.locator('input[data-key="note"], textarea[data-key="note"]').first
    await note.fill(USER_TEXT[lang])
    await dlg.get_by_test_id("skill-run-go").click()
    await pg.locator(".ca-composer__input").wait_for(timeout=20000)
    await pg.locator(".ca-composer").get_by_text(ScriptedAgent.label, exact=True).wait_for(timeout=15000)
    box = pg.locator(".ca-composer__input")
    await box.click()
    await box.press("Enter")
    await _bind_open_project(pg)
    return browser, pg


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_card1_one_ask_clean_placeholders_zh_first_sentence(
    app_url, mock_ws, agent, ws_forward, lang,
):  # noqa: F811
    from ComfyArt.bot.providers import BotEvent

    async def steps(a, turn, emit):
        await emit(BotEvent(t="delta", text=FIRST[lang]))
        answered = await _call(a, emit, "ask_user", _partial_card1(lang), 1)
        a.answered = answered
        await emit(BotEvent(t="delta", text=DONE[lang]))

    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _open_youtube(p, app_url, lang, ws_forward)
        card = pg.locator('[data-testid="question-dock"] .ca-q')
        await card.wait_for(timeout=25000)
        await pg.wait_for_timeout(400)

        # (1) first visible sentence
        body = await pg.locator(".ca-chat, .ca-composer, body").first.inner_text()
        if lang == "zh":
            await pg.get_by_text(ZH_FIRST).first.wait_for(timeout=20000)
            assert "I'll read the skill first." not in body
            assert ZH_FIRST in (await pg.locator("body").inner_text())
        else:
            await pg.get_by_text("I'll read the skill first.").first.wait_for(timeout=20000)

        # (2) one ask, 1/3 header, one question per page, no empty 2/3 or 3/3
        pages = await inspect_pages(pg, 3)
        assert len(pages) == 3
        assert re.search(r"1\s*(of|/)\s*3", pages[0]["head"]), pages[0]["head"]
        assert re.search(r"2\s*(of|/)\s*3", pages[1]["head"]), pages[1]["head"]
        assert re.search(r"3\s*(of|/)\s*3", pages[2]["head"]), pages[2]["head"]
        for snap in pages:
            assert snap["block_count"] == 1
            assert snap["scroll_card"] is None
            assert snap["prompts"], snap
        prompts = [p["prompts"][0] for p in pages]
        if lang == "zh":
            assert prompts[0].startswith("这次横幅想怎么交付")
            assert prompts[1].startswith("横幅上实际要出现哪些文字")
            assert prompts[2].startswith("有需要放进去的品牌资产")
        else:
            assert all(not CJK.search(p) for p in prompts), prompts
            assert "delivered" in prompts[0].lower() or "How should" in prompts[0]

        # (3) placeholders have no trailing `”,` on every page
        visible = [ph for snap in pages for ph in snap["placeholders"] if ph]
        assert visible, pages
        for ph in visible:
            assert JUNK not in ph, ph
            assert "\u201d" not in ph, ph
            assert not ph.rstrip().endswith('",'), ph
            assert not ph.rstrip().endswith('"'), ph

        await _shot(pg, f"card1-first-{lang}")
        await _shot(pg, f"card1-top-{lang}")
        await _shot(pg, f"card1-bottom-{lang}")

        assert mock_ws["submits"] == [] and mock_ws["quotes"] == []
        await browser.close()
