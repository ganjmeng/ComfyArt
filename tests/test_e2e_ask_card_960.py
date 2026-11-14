"""#960 Full App mock e2e ($0): default YouTube-banner skill flow — the real app, real chat,
real MCP tools, a scripted in-process agent (no LLM).

1. The agent calls ask_user with only allow_skip (the QA failure) -> the real MCP rejects it,
   no card is rendered and no answer is recorded.
2. It reads the real skill through the page relay: page 1 carries all three card-1 questions
   and a next_offset, so the card spec is not in a dropped tail.
3. It calls ask_user again with card 1 -> the real QuestionCard renders 1 of 3, answerable;
   the test answers B / C / A and the agent receives exactly those answers, then continues.
4. Nothing paid: mock WaveSpeed only, no submit, no quote.

ASK960_SHOTS=/dir keeps the zh/en screenshots. Chromium is required; never a silent skip.
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
from ask_card_pages import inspect_and_answer, inspect_pages, wait_dock, read_page

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("ASK960_SHOTS")
USER_TEXT = {"zh": "Loomi Studio / AI 绘画教程和创意工作流 / 每周二、周五更新 / 明亮活泼",
             "en": "Loomi Studio / AI art tutorials and creative workflows / new episodes Tue & Fri / bright and lively"}
DONE = {"zh": "已收到你的选择，继续下一步。", "en": "Got your choices, continuing."}
BAD_ZH = "没有渲染卡片"
BAD_EN = "no card was shown"

CARD1 = {
    "questions": [
        {"id": "yt_delivery", "prompt": "这次横幅想怎么交付？（影响后续步骤与文字精度）", "allow_other": True,
         "options": [{"id": "A", "label": "先出三方向选择板，再做终稿"},
                     {"id": "B", "label": "直接出一张终稿，文字用精确排版渲染"},
                     {"id": "C", "label": "直接出一张终稿，文字由图像模型生成"}],
         "placeholder": "其它想法（比如一次出多个方向终稿）..."},
        {"id": "yt_banner_text", "prompt": "横幅上实际要出现哪些文字？", "allow_other": True,
         "options": [{"id": "A", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流 ＋ 每周二/五更新"},
                     {"id": "B", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流"},
                     {"id": "C", "label": "只有 Loomi Studio"}],
         "placeholder": "自己指定文案（含大小写、符号、换行）..."},
        {"id": "yt_brand_assets", "prompt": "有需要放进去的品牌资产吗？（Logo／头像／真人）", "allow_other": True,
         "options": [{"id": "A", "label": "没有，纯图形＋文字构成识别"},
                     {"id": "B", "label": "有 Logo／头像，我上传给你"},
                     {"id": "C", "label": "需要预留真人出镜位置"}],
         "placeholder": "其它（比如指定参考图／配色）..."},
    ],
    "allow_skip": True,
    "page_count": 3,
}


class ScriptedAgent(FakeProvider):
    """Stands in for the LLM: runs the fixed tool script through the real MCP dispatch."""
    id = "fake-ask960"
    label = "FakeAsk960"

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
    await inspect_and_answer(pg, picks)


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_card1_appears_answers_and_continues(app_url, mock_ws, agent, ws_forward, lang):  # noqa: F811
    from ComfyArt.bot.providers import BotEvent

    async def steps(a, turn, emit):
        bad = await _call(a, emit, "ask_user", {"allow_skip": True}, 1)
        a.bad = bad
        read = await _call(a, emit, "skill", {"action": "read", "id": "youtube-channel-banner"}, 2)
        a.read = read
        # #934 lengthened the skill text; follow the pager so later asserts can see every card-1 id.
        chunks = [read.get("content") or ""]
        offset = read.get("next_offset")
        n = 10
        while offset and n < 16:
            more = await _call(a, emit, "skill", {"action": "read", "id": "youtube-channel-banner", "offset": offset}, n)
            chunks.append(more.get("content") or "")
            offset = more.get("next_offset")
            n += 1
        a.skill_text = "".join(chunks)
        answered = await _call(a, emit, "ask_user", CARD1, 3)
        a.answered = answered
        await emit(BotEvent(t="delta", text=DONE[lang]))

    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _open_youtube(p, app_url, lang, ws_forward)
        card = pg.locator('[data-testid="question-dock"] .ca-q')
        await card.wait_for(timeout=25000)
        await pg.wait_for_timeout(400)

        # (1) the QA failure is a real error result — no card, no answer, no paid fallback
        assert agent.bad.get("status") != "answered"
        raw = agent.bad.get("raw") or ""
        assert "prompt is required" in raw, agent.bad
        assert (BAD_ZH if lang == "zh" else BAD_EN) in raw, agent.bad
        assert mock_ws["submits"] == [] and mock_ws["quotes"] == []

        # (2) the real skill read is paged, and the full text still has the card-1 spec
        r = agent.read
        assert r.get("has_more") is True and r.get("next_offset"), r
        assert r.get("total_chars", 0) > 3000
        text = getattr(agent, "skill_text", "") or (r.get("content") or "")
        for needle in ("yt_delivery", "yt_banner_text", "yt_brand_assets"):
            assert needle in text, needle

        # (3+4) the card from the fixed call is real, 1 of 3, one question per
        # page, nothing preselected; answer B / C / A and the agent receives that.
        pages = await inspect_and_answer(pg, picks=(1, 2, 0))
        assert len(pages) == 3
        assert re.search(r"1\s*(of|/)\s*3", pages[0]["head"]), pages[0]["head"]
        prompts = [p["prompts"][0] for p in pages]
        if lang == "zh":
            assert prompts == [q["prompt"] for q in CARD1["questions"]]
        else:
            # #962: the server locks card 1 in the ask-card language, so an en turn renders the
            # en skeleton even when the scripted agent sent the zh copy.
            assert all(not re.search(r"[\u4e00-\u9fff]", p) for p in prompts), prompts
        for snap in pages:
            assert snap["block_count"] == 1
            assert snap["selected"][0] == 0
            assert snap["scroll_card"] is None
        await _shot(pg, f"card1-{lang}")
        for _ in range(200):
            if getattr(agent, "answered", None) is not None:
                break
            await asyncio.sleep(0.1)
        answered = agent.answered
        assert answered.get("status") == "answered", answered
        got = {k: v.get("selected") for k, v in (answered.get("answers") or {}).items()}
        assert got == {"yt_delivery": ["B"], "yt_banner_text": ["C"], "yt_brand_assets": ["A"]}, answered

        # (5) the turn continues after the answer and nothing was generated/charged
        await pg.get_by_text(DONE[lang]).first.wait_for(timeout=20000)
        await _shot(pg, f"card1-answered-{lang}")
        assert mock_ws["submits"] == [] and mock_ws["quotes"] == []
        await browser.close()
