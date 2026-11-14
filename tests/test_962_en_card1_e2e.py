"""#962 Full App mock e2e ($0): the real app renders youtube-channel-banner card 1 in the
en UI with an English prompt and English options, and keeps the zh card byte-for-byte.

Same harness as #960: real app, real chat, real MCP tools, a scripted in-process agent
(no LLM) and the mock WaveSpeed server (no submit, no quote). Chromium is required; never
a silent skip.

ASK962_SHOTS=/dir keeps the zh/en Full App screenshots.
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
from ask_card_pages import answer_scroll_card, inspect_scroll_card, wait_dock, read_page

pw = pytest.importorskip("playwright.async_api")

CJK = re.compile(r"[\u4e00-\u9fff]")
SHOTS = os.environ.get("ASK962_SHOTS")
USER_TEXT = {
    "zh": "Loomi Studio / AI 绘画教程和创意工作流 / 每周二、周五更新 / 明亮活泼",
    "en": "Loomi Studio / AI art tutorials and creative workflows / new episodes Tue & Fri / bright and lively",
}
DONE = {"zh": "已收到你的选择，继续下一步。", "en": "Got your choices, continuing."}

# What the agent sends per language (the skill's card 1: fixed English/Chinese prompts + live tiers).
CARD1 = {
    "zh": {
        "questions": [
            {"id": "yt_delivery", "prompt": "这次横幅想怎么交付？（影响后续步骤与文字精度）", "allow_other": True,
             "options": [{"id": "A", "label": "先出三方向选择板，再做终稿"},
                         {"id": "B", "label": "直接出一张终稿，文字用精确排版渲染"},
                         {"id": "C", "label": "直接出一张终稿，文字由图像模型生成"}]},
            {"id": "yt_banner_text", "prompt": "横幅上实际要出现哪些文字？", "allow_other": True,
             "options": [{"id": "A", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流 ＋ 每周二/五更新"},
                         {"id": "B", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流"},
                         {"id": "C", "label": "只有 Loomi Studio"}]},
            {"id": "yt_brand_assets", "prompt": "有需要放进去的品牌资产吗？（Logo／头像／真人）", "allow_other": True,
             "options": [{"id": "A", "label": "没有，纯图形＋文字构成识别"},
                         {"id": "B", "label": "有 Logo／头像，我上传给你"},
                         {"id": "C", "label": "需要预留真人出镜位置"}]},
        ],
        "allow_skip": True,
        "page_count": 3,
    },
    "en": {
        "questions": [
            {"id": "yt_delivery", "prompt": "How should this banner be delivered?", "allow_other": True,
             "options": [{"id": "A", "label": "Three-direction board first"},
                         {"id": "B", "label": "One final with exact text layout"},
                         {"id": "C", "label": "One final with model-rendered text"}]},
            {"id": "yt_banner_text", "prompt": "What text should appear on the banner?", "allow_other": True,
             "options": [{"id": "A", "label": "Loomi Studio + AI tutorials + Tue/Fri"},
                         {"id": "B", "label": "Loomi Studio + AI tutorials"},
                         {"id": "C", "label": "Loomi Studio only"}]},
            {"id": "yt_brand_assets", "prompt": "Any brand assets to include?", "allow_other": True,
             "options": [{"id": "A", "label": "None"},
                         {"id": "B", "label": "Logo / avatar upload"},
                         {"id": "C", "label": "Reserve a person slot"}]},
        ],
        "allow_skip": True,
        "page_count": 3,
    },
}
# What the server must render: the locked skeleton in that language; live tiers kept as sent.
EXPECTED = {
    "zh": {
        "prompts": ["这次横幅想怎么交付？（影响后续步骤与文字精度）", "横幅上实际要出现哪些文字？",
                    "有需要放进去的品牌资产吗？（Logo／头像／真人）"],
        "labels": [
            ["先出三方向选择板，再做终稿", "直接出一张终稿，文字用精确排版渲染", "直接出一张终稿，文字由图像模型生成"],
            ["Loomi Studio ＋ AI 绘画教程和创意工作流 ＋ 每周二/五更新",
             "Loomi Studio ＋ AI 绘画教程和创意工作流", "只有 Loomi Studio"],
            ["没有，纯图形＋文字构成识别", "有 Logo／头像，我上传给你", "需要预留真人出镜位置"],
        ],
        "placeholders": ["其它想法（比如一次出多个方向终稿）...", "自己指定文案（含大小写、符号、换行）...",
                         "其它（比如指定参考图／配色）..."],
    },
    "en": {
        "prompts": ["How should this banner be delivered? (It changes the next steps and how precise the text can be)",
                    "What text should actually appear on the banner?",
                    "Any brand assets to include? (Logo / avatar / real person)"],
        "labels": [
            ["Three-direction board first, then the final",
             "One final now, with text set by the exact-layout renderer",
             "One final now, with text drawn by the image model"],
            ["Loomi Studio + AI tutorials + Tue/Fri", "Loomi Studio + AI tutorials", "Loomi Studio only"],
            ["None, graphics + type only", "I have a logo / avatar to upload", "Reserve a spot for a real person"],
        ],
        "placeholders": ["Other ideas (e.g. several direction finals at once)...",
                         "Your own copy (including case, symbols and line breaks)...",
                         "Other (e.g. a reference image / colors)..."],
    },
}


class ScriptedAgent(FakeProvider):
    """Stands in for the LLM: sends card 1 through the real MCP dispatch."""
    id = "fake-962"
    label = "Fake962"

    def __init__(self):
        super().__init__()
        self.steps = None
        self.results: list = []
        self.asked = None

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
    send_sync = PromptServer.instance.send_sync
    sockets = []

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
    await pg.wait_for_timeout(500)
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


async def _answer(pg, picks):
    await answer_scroll_card(pg, picks)


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_card1_is_in_the_ui_language(app_url, mock_ws, agent, ws_forward, lang):  # noqa: F811
    from ComfyArt.bot.providers import BotEvent

    async def steps(a, turn, emit):
        a.asked = await _call(a, emit, "ask_user", CARD1[lang], 1)
        await emit(BotEvent(t="delta", text=DONE[lang]))

    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _open_youtube(p, app_url, lang, ws_forward)
        card = pg.locator('[data-testid="question-dock"] .ca-q')
        await card.wait_for(timeout=25000)
        await pg.wait_for_timeout(400)

        expected = EXPECTED[lang]
        snap = await inspect_scroll_card(pg, 3)
        assert re.search(r"1\s*(of|/)\s*3", snap["head"]), snap["head"]
        assert not re.search(r"2\s*(of|/)\s*3", snap["head"]), snap["head"]
        prompts = snap["prompts"]
        assert prompts == expected["prompts"], prompts
        assert snap["block_count"] == 3
        assert snap["scroll_card"] is not None
        assert snap["chevrons_disabled"] is True
        assert snap["labels"] == expected["labels"], snap["labels"]
        assert snap["placeholders"] == expected["placeholders"], snap["placeholders"]
        assert snap["selected"] == [0, 0, 0]  # no default selection
        await answer_scroll_card(pg, picks=(1, 2, 0))
        if lang == "en":
            # #962 AC: prompt and every option are English — no CJK anywhere in card 1.
            for text in prompts + [t for row in expected["labels"] for t in row] + expected["placeholders"]:
                assert not CJK.search(text), text
        await _shot(pg, f"card1-{lang}")

        # Answer B / C / A already submitted above: the ids (not the visible copy) carry the meaning.
        for _ in range(200):
            if agent.asked is not None:
                break
            await asyncio.sleep(0.1)
        asked = agent.asked or {}
        assert asked.get("status") == "answered", asked
        got = {k: v.get("selected") for k, v in (asked.get("answers") or {}).items()}
        assert got == {"yt_delivery": ["B"], "yt_banner_text": ["C"], "yt_brand_assets": ["A"]}, asked
        await pg.get_by_text(DONE[lang]).first.wait_for(timeout=20000)

        # Zero paid: nothing was submitted or quoted.
        assert mock_ws["submits"] == [] and mock_ws["quotes"] == []
        await browser.close()
