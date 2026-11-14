"""#966 Full App mock e2e ($0): card 2 renders in the en UI with English fixed copy and keeps
the zh card byte-for-byte.

Same harness as #962: real app, real chat, real MCP tools, a scripted in-process agent (no
LLM) and the mock WaveSpeed server (no submit, no quote). The agent asks card 1, waits for
the real UI answer, then asks card 2. Chromium is required; never a silent skip.

ASK966_SHOTS=/dir keeps the zh/en Full App screenshots.
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

CJK = re.compile(r"[\u4e00-\u9fff]")
SHOTS = os.environ.get("ASK966_SHOTS")
USER_TEXT = {
    "zh": "Loomi Studio / AI 绘画教程和创意工作流 / 每周二、周五更新 / 明亮活泼",
    "en": "Loomi Studio / AI art tutorials and creative workflows / new episodes Tue & Fri / bright and lively",
}
DONE = {"zh": "已收到你的选择，继续下一步。", "en": "Got your choices, continuing."}

# Card 1 is only the gate to card 2 here; #962 covers its copy. Full 3-question card so the
# real answer path runs exactly as in the app.
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
# Card 2 as a locale-consistent agent sends it: the live three directions are authored in the
# card language; the fixed prompts / text-mode labels / placeholders are locked by the server.
CARD2 = {
    "zh": {
        "questions": [
            {"id": "yt_direction", "prompt": "选哪个方向做 2560×1440 终稿？", "allow_other": True,
             "options": [{"id": "A", "label": "方向 A：品牌主导·大留白（推荐）",
                          "description": "选择板顶部：最干净，缩到移动端也不丢信息"},
                         {"id": "B", "label": "方向 B：全画幅叙事场景（推荐）",
                          "description": "选择板中部：画面最丰富"},
                         {"id": "C", "label": "方向 C：模块化工作流网格",
                          "description": "选择板底部：最贴工作流主题"}]},
            {"id": "yt_text_mode", "prompt": "终稿的文字怎么上？", "allow_other": True,
             "options": [{"id": "A", "label": "精确排版（推荐）"}, {"id": "B", "label": "图像模型直出"}]},
        ],
        "allow_skip": True,
        "page_count": 2,
    },
    "en": {
        "questions": [
            {"id": "yt_direction", "prompt": "Which direction should become the 2560×1440 final?", "allow_other": True,
             "options": [{"id": "A", "label": "Direction A: Brand-led with generous white space",
                          "description": "Top of the board: the cleanest, still readable on mobile"},
                         {"id": "B", "label": "Direction B: Full-frame narrative scene",
                          "description": "(Recommended) Middle of the board: the richest image"},
                         {"id": "C", "label": "Direction C: Modular workflow grid",
                          "description": "Bottom of the board: closest to the workflow theme"}]},
            {"id": "yt_text_mode", "prompt": "How should the final's text be set?", "allow_other": True,
             "options": [{"id": "A", "label": "Exact layout (Recommended)"},
                         {"id": "B", "label": "Image model renders the text"}]},
        ],
        "allow_skip": True,
        "page_count": 2,
    },
}
# What the server must render on card 2 (the zh side is the main-branch reference copy).
EXPECTED = {
    "zh": {
        "prompts": ["选哪个方向做 2560×1440 终稿？", "终稿的文字怎么上？（中文＋三行信息，精度差异较大）"],
        "labels": [
            ["方向 A：品牌主导·大留白", "方向 B：全画幅叙事场景", "方向 C：模块化工作流网格"],
            ["精确排版（推荐）", "图像模型直出"],
        ],
        "placeholders": ["想调整（说哪里改）或让我直接定...", "其它要求..."],
    },
    "en": {
        "prompts": ["Which direction should become the 2560×1440 final?",
                    "How should the final's text be set? (Chinese + three lines of info; accuracy varies a lot)"],
        "labels": [
            ["Direction A: Brand-led with generous white space",
             "Direction B: Full-frame narrative scene",
             "Direction C: Modular workflow grid"],
            ["Exact layout (Recommended)", "Image model renders the text"],
        ],
        "placeholders": ["Want changes (say what to adjust), or let me decide...", "Any other requirements..."],
    },
}


class ScriptedAgent(FakeProvider):
    """Stands in for the LLM: sends card 1, waits for the real answer, sends card 2."""

    id = "fake-966"
    label = "Fake966"

    def __init__(self):
        super().__init__()
        self.steps = None
        self.results: list = []
        self.asked = None
        self.asked2 = None

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
    await inspect_and_answer(pg, picks)


async def _wait_card(pg, prompts):
    card = pg.locator('[data-testid="question-dock"] .ca-q')
    await card.wait_for(timeout=25000)
    first = prompts[0] if isinstance(prompts, list) else prompts
    got = []
    for _ in range(200):
        got = [t.strip() for t in await card.locator(".ca-q__prompt").all_inner_texts()]
        if got and got[0] == first:
            return card
        await asyncio.sleep(0.1)
    pytest.fail(f"card did not render the expected first prompt {first!r}, got {got!r}")


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_card2_is_in_the_ui_language(app_url, mock_ws, agent, ws_forward, lang):  # noqa: F811
    from ComfyArt.bot.providers import BotEvent

    async def steps(a, turn, emit):
        a.asked = await _call(a, emit, "ask_user", CARD1[lang], 1)
        a.asked2 = await _call(a, emit, "ask_user", CARD2[lang], 2)
        await emit(BotEvent(t="delta", text=DONE[lang]))

    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _open_youtube(p, app_url, lang, ws_forward)

        # Card 1 (already fixed by #962): answer it, then card 2 appears through the real flow.
        await _wait_card(pg, EXP_START[lang])
        await _answer(pg, picks=(0, 0, 0))
        await _wait_card(pg, EXPECTED[lang]["prompts"])
        await pg.wait_for_timeout(400)

        expected = EXPECTED[lang]
        pages = await inspect_and_answer(pg, picks=(0, 0))
        assert len(pages) == 2
        assert re.search(r"1\s*(of|/)\s*2", pages[0]["head"]), pages[0]["head"]
        prompts = [p["prompts"][0] for p in pages]
        assert prompts == expected["prompts"], prompts
        for i, snap in enumerate(pages):
            assert snap["block_count"] == 1
            assert snap["scroll_card"] is None
            assert snap["labels"][0] == expected["labels"][i], (i, snap["labels"])
            assert snap["placeholders"][0] == expected["placeholders"][i], (i, snap["placeholders"])
            assert snap["selected"][0] == 0
        if lang == "en":
            # #966 AC: fixed card-2 copy is English — no CJK in prompts, labels or placeholders.
            for text in prompts + [t for row in expected["labels"] for t in row] + expected["placeholders"]:
                assert not CJK.search(text), text
        await _shot(pg, f"card2-{lang}")

        # Answer A / A already submitted above.
        for _ in range(200):
            if agent.asked2 is not None:
                break
            await asyncio.sleep(0.1)
        assert agent.asked is not None and agent.asked.get("status") == "answered", agent.asked
        assert agent.asked2 is not None and agent.asked2.get("status") == "answered", agent.asked2
        got1 = {k: v.get("selected") for k, v in (agent.asked.get("answers") or {}).items()}
        got2 = {k: v.get("selected") for k, v in (agent.asked2.get("answers") or {}).items()}
        assert got1 == {"yt_delivery": ["A"], "yt_banner_text": ["A"], "yt_brand_assets": ["A"]}, agent.asked
        assert got2 == {"yt_direction": ["A"], "yt_text_mode": ["A"]}, agent.asked2
        await pg.get_by_text(DONE[lang]).first.wait_for(timeout=20000)

        # Zero paid: nothing was submitted or quoted.
        assert mock_ws["submits"] == [] and mock_ws["quotes"] == []
        await browser.close()


# Card 1's locked en prompts, only used to know which card is on screen before answering it.
EXP_START = {
    "zh": ["这次横幅想怎么交付？（影响后续步骤与文字精度）", "横幅上实际要出现哪些文字？",
           "有需要放进去的品牌资产吗？（Logo／头像／真人）"],
    "en": ["How should this banner be delivered? (It changes the next steps and how precise the text can be)",
           "What text should actually appear on the banner?",
           "Any brand assets to include? (Logo / avatar / real person)"],
}
