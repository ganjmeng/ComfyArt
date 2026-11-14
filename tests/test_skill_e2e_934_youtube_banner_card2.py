"""#934 Full App mock e2e ($0): youtube-channel-banner card 2 — shared board
thumbnails, visible descriptions, one question per page, no default selection.

Walks the official skill-page path with a scripted in-process agent (no LLM)
and the mock WaveSpeed server (no submit, no quote). Card 1 is answered first,
then card 2 is shown with the same board image on all three direction options.

ASK934_SHOTS=/dir keeps the zh/en Full App screenshots (card 2 page 1 and page 2,
plus card 1 descriptions). Chromium is required; never a silent skip.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from ask_card_pages import answer_scroll_card, inspect_and_answer, inspect_pages, inspect_scroll_card, wait_dock
from conftest import FakeProvider, write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_skill_param_guard_e2e_956_957 import LOC, _bind_open_project, _call

pw = pytest.importorskip("playwright.async_api")

CJK = re.compile(r"[\u4e00-\u9fff]")
SHOTS = os.environ.get("ASK934_SHOTS")
USER_TEXT = {
    "zh": "帮我做一张 YouTube 频道横幅。频道名 Loomi Studio，内容是 AI 绘画教程和创意工作流，每周二、周五更新。风格明亮活泼。",
    "en": "Make a YouTube channel banner for Loomi Studio. AI art tutorials and creative workflows, new episodes Tue & Fri, bright and lively.",
}
DONE = {"zh": "已收到你的选择，继续下一步。", "en": "Got your choices, continuing."}


def _board_data_uri() -> str:
    """A 16:9 board. Default is a LOCAL FIXTURE; ASK934_BOARD points at an existing PNG
    (the published Lovart board on review-assets) so PR stills can reuse that image, $0."""
    extra = os.environ.get("ASK934_BOARD")
    if extra:
        data = Path(extra).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    img = Image.new("RGB", (512, 288), (240, 244, 255))
    d = ImageDraw.Draw(img)
    bands = [(80, 140, 230), (40, 90, 180), (20, 50, 120)]
    for i, color in enumerate(bands):
        y0, y1 = i * 96, (i + 1) * 96
        d.rectangle((8, y0 + 4, 504, y1 - 4), fill=color)
        d.text((20, y0 + 36), f"LOCAL FIXTURE DIR {chr(65+i)}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


BOARD = _board_data_uri()

CARD1 = {
    "zh": {
        "questions": [
            {"id": "yt_delivery", "prompt": "这次横幅想怎么交付？（影响后续步骤与文字精度）", "allow_other": True,
             "options": [{"id": "A", "label": "先出三方向选择板，再做终稿"},
                         {"id": "B", "label": "直接出一张终稿，文字用精确排版渲染"},
                         {"id": "C", "label": "直接出一张终稿，文字由图像模型生成"}]},
            {"id": "yt_banner_text", "prompt": "横幅上实际要出现哪些文字？", "allow_other": True,
             "options": [
                 {"id": "A", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流 ＋ 每周二/五更新",
                  "description": "信息最全，更新节奏作为辅助行"},
                 {"id": "B", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流",
                  "description": "只保留频道名与定位，画面更干净"},
                 {"id": "C", "label": "只有 Loomi Studio",
                  "description": "纯品牌名，靠视觉传达主题"},
             ]},
            {"id": "yt_brand_assets", "prompt": "有需要放进去的品牌资产吗？（Logo／头像／真人）", "allow_other": True,
             "options": [{"id": "A", "label": "没有，纯图形＋文字构成识别"},
                         {"id": "B", "label": "有 Logo／头像，我上传给你"},
                         {"id": "C", "label": "需要预留真人出镜位置"}]},
        ],
        "allow_skip": True, "page_count": 3,
    },
    "en": {
        "questions": [
            {"id": "yt_delivery", "prompt": "How should this banner be delivered?", "allow_other": True,
             "options": [{"id": "A", "label": "Three-direction board first, then the final"},
                         {"id": "B", "label": "One final now, with text set by the exact-layout renderer"},
                         {"id": "C", "label": "One final now, with text drawn by the image model"}]},
            {"id": "yt_banner_text", "prompt": "What text should appear on the banner?", "allow_other": True,
             "options": [
                 {"id": "A", "label": "Loomi Studio + AI art tutorials and creative workflows + Tue/Fri",
                  "description": "The most complete information, with the update cadence as a supporting line"},
                 {"id": "B", "label": "Loomi Studio + AI art tutorials and creative workflows",
                  "description": "Keep only the channel name and positioning; the frame stays cleaner"},
                 {"id": "C", "label": "Loomi Studio only",
                  "description": "Brand name only; the visuals carry the theme"},
             ]},
            {"id": "yt_brand_assets", "prompt": "Any brand assets to include?", "allow_other": True,
             "options": [{"id": "A", "label": "None, graphics + type only"},
                         {"id": "B", "label": "I have a logo / avatar to upload"},
                         {"id": "C", "label": "Reserve a spot for a real person"}]},
        ],
        "allow_skip": True, "page_count": 3,
    },
}

CARD2 = {
    "zh": {
        "questions": [
            {"id": "yt_direction", "prompt": "选哪个方向做 2560×1440 终稿？", "allow_other": True,
             "options": [
                 {"id": "A", "label": "方向 A：品牌主导·大留白",
                  "description": "（推荐）选择板顶部：最干净、缩到移动端也不丢信息，教程类频道辨识度高",
                  "image_url": BOARD},
                 {"id": "B", "label": "方向 B：全画幅叙事场景",
                  "description": "选择板中部：画面最丰富，TV 全屏下最有氛围，文字密度需要严控",
                  "image_url": BOARD},
                 {"id": "C", "label": "方向 C：模块化工作流网格",
                  "description": "选择板底部：最贴“工作流”主题，理性又活泼，适合做系列延伸",
                  "image_url": BOARD},
             ]},
            {"id": "yt_text_mode", "prompt": "终稿的文字怎么上？（中文＋三行信息，精度差异较大）", "allow_other": True,
             "options": [{"id": "A", "label": "精确排版（推荐）"}, {"id": "B", "label": "图像模型直出"}]},
        ],
        "allow_skip": True, "page_count": 2,
    },
    "en": {
        "questions": [
            {"id": "yt_direction", "prompt": "Which direction should become the 2560×1440 final?", "allow_other": True,
             "options": [
                 {"id": "A", "label": "Direction A: Brand-led with generous white space",
                  "description": "(Recommended) Top of the board: the cleanest, still readable on a phone, high recognition for a tutorial channel",
                  "image_url": BOARD},
                 {"id": "B", "label": "Direction B: Full-frame narrative scene",
                  "description": "Middle of the board: the richest image, the most atmosphere on a TV, type density must stay tight",
                  "image_url": BOARD},
                 {"id": "C", "label": "Direction C: Modular workflow grid",
                  "description": "Bottom of the board: closest to the workflow theme, rational and lively, good for a series",
                  "image_url": BOARD},
             ]},
            {"id": "yt_text_mode", "prompt": "How should the final's text be set?", "allow_other": True,
             "options": [{"id": "A", "label": "Exact layout (Recommended)"},
                         {"id": "B", "label": "Image model renders the text"}]},
        ],
        "allow_skip": True, "page_count": 2,
    },
}


class ScriptedAgent(FakeProvider):
    id = "fake-ask934"
    label = "FakeAsk934"

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
async def test_fullapp_card2_thumbs_descriptions_and_pagination(
    app_url, mock_ws, agent, ws_forward, lang,
):  # noqa: F811
    from ComfyArt.bot.providers import BotEvent

    async def steps(a, turn, emit):
        a.asked = await _call(a, emit, "ask_user", CARD1[lang], 1)
        a.asked2 = await _call(a, emit, "ask_user", CARD2[lang], 2)
        await emit(BotEvent(t="delta", text=DONE[lang]))

    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _open_youtube(p, app_url, lang, ws_forward)

        # Card 1: scrolling card, descriptions under titles, Next does not paginate.
        await wait_dock(pg)
        c1 = await inspect_scroll_card(pg, 3)
        await _shot(pg, f"card1-q1-{lang}")
        assert re.search(r"1\s*(of|/)\s*3", c1["head"]), c1["head"]
        assert not re.search(r"2\s*(of|/)\s*3", c1["head"]), c1["head"]
        assert c1["block_count"] == 3
        assert c1["scroll_card"] is not None
        assert c1["chevrons_disabled"] is True
        assert c1["selected"] == [0, 0, 0]
        # Locked card-1 options (delivery / assets) plus live banner-text all have descriptions.
        assert len(c1["descs"]) == 3
        assert all(row for row in c1["descs"]), c1["descs"]
        if lang == "zh":
            assert "推荐：一张板上放 3 个结构不同的方向" in " ".join(c1["descs"][0])
        await answer_scroll_card(pg, picks=(0, 0, 0))

        # Card 2 page 1: same board thumbnail on every direction; descriptions visible.
        for _ in range(200):
            head = await (await wait_dock(pg)).locator(".ca-q__head").inner_text()
            if re.search(r"1\s*(of|/)\s*2", head):
                break
            await asyncio.sleep(0.1)
        else:
            pytest.fail("card 2 did not appear")

        await _shot(pg, f"card2-q1-{lang}")
        pages = await inspect_pages(pg, 2)
        assert len(pages) == 2
        q1, q2 = pages
        assert re.search(r"1\s*(of|/)\s*2", q1["head"]), q1["head"]
        assert re.search(r"2\s*(of|/)\s*2", q2["head"]), q2["head"]
        assert q1["block_count"] == q2["block_count"] == 1
        assert q1["scroll_card"] is None and q2["scroll_card"] is None
        assert q1["selected"][0] == 0 and q2["selected"][0] == 0
        thumbs = q1["thumbs"][0]
        assert len(thumbs) == 3, thumbs
        assert len(set(thumbs)) == 1, thumbs
        assert thumbs[0].startswith("data:image/png;base64,"), thumbs[0]
        assert all(d for d in q1["descs"][0]), q1["descs"]
        if lang == "zh":
            assert any("选择板顶部" in d for d in q1["descs"][0])
            assert any("选择板中部" in d for d in q1["descs"][0])
            assert any("选择板底部" in d for d in q1["descs"][0])
            assert q1["prompts"][0].startswith("选哪个方向做 2560")
            assert q2["prompts"][0].startswith("终稿的文字怎么上")
        else:
            assert any("Top of the board" in d for d in q1["descs"][0])
            assert all(not CJK.search(d) for d in q1["descs"][0]), q1["descs"]
        # Q2 is text-only: descriptions under titles, no thumbnails.
        assert q2["thumbs"][0] == []
        assert q2["descs"][0], q2["descs"]
        if lang == "zh":
            assert any("先生成无字底图" in d for d in q2["descs"][0])
        await _shot(pg, f"card2-q2-{lang}")

        # Submit A / A from page 2 (inspect_pages left us on the last page, unselected).
        card = await wait_dock(pg)
        await card.locator(".ca-q__block").nth(0).locator(".ca-q__opt").nth(0).click()
        await card.locator(".ca-q__submit").click()
        for _ in range(200):
            if agent.asked2 is not None:
                break
            await asyncio.sleep(0.1)
        asked2 = agent.asked2 or {}
        assert asked2.get("status") == "answered", asked2
        got = {k: v.get("selected") for k, v in (asked2.get("answers") or {}).items()}
        assert got == {"yt_direction": ["A"], "yt_text_mode": ["A"]}, asked2
        await pg.get_by_text(DONE[lang]).first.wait_for(timeout=20000)
        assert mock_ws["submits"] == [] and mock_ws["quotes"] == []
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_card1_next_scrolls_before_answer_submit(
    app_url, mock_ws, agent, ws_forward, lang,
):  # noqa: F811
    """#998: Next must scroll the SAME pending card, even when all answers are filled."""
    from ComfyArt.bot.providers import BotEvent

    async def steps(a, turn, emit):
        a.asked = await _call(a, emit, "ask_user", CARD1[lang], 1)
        await emit(BotEvent(t="delta", text=DONE[lang]))

    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _open_youtube(p, app_url, lang, ws_forward)
        answer_posts = []
        pg.on("request", lambda req: answer_posts.append(req)
              if req.method == "POST" and re.search(r"/asks/[^/]+/answer$", req.url) else None)
        card = await wait_dock(pg)
        await inspect_scroll_card(pg, 3)
        body = card.get_by_test_id("question-body")
        button = card.locator(".ca-q__submit")
        # Real layout must overflow: this test must not pass on a non-scrolling fixture.
        assert await body.evaluate("el => el.scrollHeight > el.clientHeight + 2")
        await card.evaluate("el => { el.dataset.scroll998Identity = 'original' }")
        header = await card.locator(".ca-q__head").inner_text()

        # At the bottom, incomplete answers still cannot be submitted.
        await body.evaluate("el => { el.scrollTop = el.scrollHeight; el.dispatchEvent(new Event('scroll')) }")
        await pw.expect(button).to_be_disabled()
        assert answer_posts == [] and agent.asked is None

        # Fill every answer, then return to the top. allOk=true must NOT bypass scrolling.
        for i in range(3):
            await card.locator(".ca-q__block").nth(i).locator(".ca-q__opt").first.click()
        await body.evaluate("el => { el.scrollTop = 0; el.dispatchEvent(new Event('scroll')) }")
        await pw.expect(button).to_have_text(re.compile("下一步|Next"))
        before = await body.evaluate("el => el.scrollTop")
        await button.click()
        await pg.wait_for_function(
            "before => document.querySelector('[data-scroll998-identity=original] [data-testid=question-body]')?.scrollTop > before",
            arg=before,
        )
        # Wait until smooth scrolling settles before checking no answer request escaped.
        await pg.wait_for_function("""() => {
            const el = document.querySelector('[data-scroll998-identity=original] [data-testid=question-body]');
            if (!el) return false;
            const now = performance.now();
            if (el._last998Top !== el.scrollTop) {
                el._last998Top = el.scrollTop; el._last998Time = now; return false;
            }
            return now - el._last998Time > 150;
        }""")
        assert await body.evaluate("el => el.scrollTop") > before
        assert answer_posts == [], "Next submitted while the card was not at its end"
        assert agent.asked is None, "ask_user resolved before bottom submission"
        assert await card.get_attribute("data-scroll998-identity") == "original"
        assert await card.locator(".ca-q__block").count() == 3
        assert await card.locator(".ca-q__head").inner_text() == header
        assert await card.locator(".ca-q__opt[data-on]").count() == 3

        # Only the explicit bottom-of-card click submits the three completed answers.
        await body.evaluate("el => { el.scrollTop = el.scrollHeight; el.dispatchEvent(new Event('scroll')) }")
        await pw.expect(button).to_be_enabled()
        await button.click()
        await pg.get_by_text(DONE[lang], exact=True).first.wait_for(timeout=20000)
        assert len(answer_posts) == 1
        result = agent.asked or {}
        assert result.get("status") == "answered", result
        assert {k: v.get("selected") for k, v in result.get("answers", {}).items()} == {
            "yt_delivery": ["A"], "yt_banner_text": ["A"], "yt_brand_assets": ["A"],
        }, result
        assert mock_ws["submits"] == [] and mock_ws["quotes"] == []
        await browser.close()
