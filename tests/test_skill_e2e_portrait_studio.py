"""portrait-studio e2e (Lovart 7fc60c86): the real built app in headless Chromium, real ComfyArt routes,
real MCP tool dispatch (api.mcp._tools_call), real chat panel. $0: the agent is a scripted in-process
provider (no LLM), WaveSpeed is the local mock and nothing is submitted to it.

1. No reference photo: the user sends the portrait-studio skill with no image. The agent's generate_image
   call goes through the real MCP dispatch; the server does not generate (needs_input) and the agent relays
   the upload request. The chat shows it in the UI language only, no goal-check warning, no card; no model
   submit, no price quote.
2. Card: the agent sends a sloppy ask_user (wrong language, a default, a recommended flag, an extra
   question). The docked question card in the real chat panel shows the locked Lovart card in the UI
   language: 1 of 3, the three verbatim questions, options and free-text placeholders, nothing
   preselected, no 推荐. Answering A/A/A returns the answers to the agent (3 images by default).

dist/ must be a local build of this tree (`npx vite build`, not committed); a missing or stale dist/ or a
missing Chromium is a hard failure, never a skip. PORTRAIT_E2E_SHOTS=/dir keeps the screenshots.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

import pytest

from conftest import FakeProvider, write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures: real routes + local mock WaveSpeed)
from test_portrait_studio_flow import EXPECTED, UPLOAD

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("PORTRAIT_E2E_SHOTS")
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text(encoding="utf-8")) for lg in ("zh", "en")}
USER_TEXT = {"zh": "帮我用这张照片做一组专业形象照。", "en": "Make a professional portrait set from my photo."}


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing: run `npx vite build` (local build, not committed) before this e2e")
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "dist").rglob("*.js"))
    if "ps_shots" not in bundle:
        pytest.fail("dist/ is stale (no portrait-studio card in skills): run `npx vite build` (local, not committed)")


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("WAVESPEED_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


class ScriptedAgent(FakeProvider):
    """Stands in for the LLM: runs a fixed tool script through the real MCP dispatch, in the turn's context."""
    id = "fake-portrait"
    label = "FakePortrait"

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


async def _call(agent, emit, name, args, n):
    from ComfyArt.api import mcp
    from ComfyArt.bot.providers import BotEvent
    await emit(BotEvent(t="tool_use", name=f"mcp__comfyart__{name}", input=args, id=f"t{n}"))
    out = await mcp._tools_call({"name": name, "arguments": args})
    text = out["content"][0]["text"]
    await emit(BotEvent(t="tool_result", id=f"t{n}", text=text, is_error=bool(out.get("isError"))))
    try:
        payload = json.loads(text)
    except ValueError:
        payload = {"raw": text}
    agent.results.append((name, payload))
    return payload


@pytest.fixture
def agent(monkeypatch):
    from ComfyArt.api.settings import SETTINGS_SPEC
    from ComfyArt.bot import register_provider
    a = ScriptedAgent()
    register_provider(a)
    monkeypatch.setitem(SETTINGS_SPEC, f"bot-model-{a.id}", "")
    write_settings(**{"bot-provider": a.id, "enable-bot": True, "enable-mcp": True})
    return a


async def _page(p, app_url, lang, sockets):  # noqa: F811
    try:
        browser = await p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"chromium not available, this e2e must not skip: {e}")
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN" if lang == "zh" else "en-US")
    await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
    pg = await ctx.new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light')")
    await pg.goto(app_url + f"?project=pps{lang}&new=1&skill=portrait-studio&mode=agent")
    await pg.locator(".ca-composer__input").wait_for(timeout=20000)
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)
    assert LOC[lang]["skills.portraitStudio"] in await pg.locator(".ca-composer").inner_text()
    await pg.locator(".ca-composer").get_by_text(ScriptedAgent.label, exact=True).wait_for(timeout=15000)
    return browser, pg


@pytest.fixture
def ws_forward(monkeypatch):
    """The stubbed PromptServer only records send_sync; forward the server's events to the page's /ws."""
    from server import PromptServer
    sockets: list = []
    send_sync = PromptServer.instance.send_sync

    def forward(event, data, sid=None):
        send_sync(event, data, sid)
        for ws in sockets:
            ws.send(json.dumps({"type": event, "data": data}, default=str))
    monkeypatch.setattr(PromptServer.instance, "send_sync", forward)
    return sockets


async def _send(pg, text):
    box = pg.locator(".ca-composer__input")
    await box.fill(text)
    await box.press("Enter")


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def _paid(mock_ws):  # noqa: F811
    return mock_ws["submits"] + mock_ws["quotes"]


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_skill_e2e_portrait_studio_no_reference_asks_to_upload(app_url, mock_ws, agent, ws_forward, lang):  # noqa: F811
    async def steps(a, turn, emit):
        from ComfyArt.bot.providers import BotEvent
        out = await _call(a, emit, "generate_image", {"prompt": "professional portrait set", "skill": "portrait-studio", "count": 1}, 1)
        await emit(BotEvent(t="delta", text=out.get("user_message") or "NO USER MESSAGE"))
    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang, ws_forward)
        await _send(pg, USER_TEXT[lang])
        bot = pg.locator(".ca-chat__bot").last
        await pg.get_by_text(UPLOAD[lang]).first.wait_for(timeout=20000)
        name, payload = agent.results[0]
        assert name == "generate_image" and payload["status"] == "needs_input", payload
        assert payload["submitted"] is False and payload["charged"] is False and payload["lang"] == lang
        assert "Use the ComfyArt skill" in agent.last_turn.user_text and agent.last_turn.attachments == []
        text = await bot.inner_text()
        other = "en" if lang == "zh" else "zh"
        assert UPLOAD[lang] in text and UPLOAD[other] not in text, text
        assert await pg.locator(".ca-q").count() == 0  # no card without a reference photo
        await pg.wait_for_timeout(1500)  # turn end: the goal self-check runs and must not flag the upload request
        text = await bot.inner_text()
        assert "Goal check failed" not in text and "目标核对未通过" not in text, text
        assert UPLOAD[lang] in text, text
        # Design (#926): nothing was generated, so no 生成图像 / Generate image tool row on the upload request.
        label = LOC[lang]["bot.generateImage"]
        assert label not in text, text
        panel = await pg.locator(".ca-chat").first.inner_text()
        assert label not in panel and LOC[other]["bot.generateImage"] not in panel, panel
        rows = await bot.locator(".ca-process__labeltext").all_inner_texts()
        assert label not in [r.strip() for r in rows], rows
        assert await bot.locator(".ca-chat__tool, .ca-chat__step").count() == 0
        await _shot(pg, f"upload-prompt-{lang}")
        assert _paid(mock_ws) == []  # no model submit, no price quote
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_skill_e2e_portrait_studio_card_renders_locked_lovart_text(app_url, mock_ws, agent, ws_forward, lang):  # noqa: F811
    sloppy = {
        "questions": [
            {"id": "count", "prompt": "How many professional portraits?" if lang == "zh" else "这组专业形象照想要几张？",
             "options": [{"id": "1", "label": "3"}, {"id": "2", "label": "4"}], "defaults": ["1"], "page": 1},
            {"id": "q2", "prompt": "服装方向怎么定？", "options": [{"id": "a", "label": "休闲", "recommended": True}, {"id": "b", "label": "正装"}],
             "page": 2},
            {"id": "q4", "prompt": "要不要美颜？", "options": [{"id": "a", "label": "要"}, {"id": "b", "label": "不要"}], "page": 3},
        ],
        "page_count": 4, "allow_skip": False,
    }

    async def steps(a, turn, emit):
        await _call(a, emit, "ask_user", sloppy, 1)
    agent.steps = steps
    expected = EXPECTED[lang]
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang, ws_forward)
        await _send(pg, USER_TEXT[lang])
        card = pg.locator('[data-testid="question-dock"] .ca-q')
        await card.wait_for(timeout=20000)
        head = await card.locator(".ca-q__head").inner_text()
        assert re.search(r"1\s*(of|/)\s*3", head), head
        assert [t.strip() for t in await card.locator(".ca-q__prompt").all_inner_texts()] == [e[1] for e in expected]
        blocks = card.locator(".ca-q__block")
        assert await blocks.count() == 3
        for i, (_, _, labels, placeholder) in enumerate(expected):
            blk = blocks.nth(i)
            assert [t.strip() for t in await blk.locator(".ca-q__text").all_inner_texts()] == labels
            assert await blk.locator(".ca-q__letter").all_inner_texts() == ["A", "B", "C", "D"]
            assert await blk.locator(".ca-q__input").get_attribute("placeholder") == placeholder
            assert await blk.locator(".ca-q__opt[data-on]").count() == 0  # nothing preselected
        assert await card.locator(".ca-q__rec").count() == 0  # no 推荐 marker
        assert await card.locator(".ca-q__skip").count() == 1
        visible = await card.inner_text()
        assert "要不要美颜" not in visible and "推荐" not in visible and "ecommended" not in visible
        for needle in ("ps_shots", "ps_outfit", "ps_scene", "7fc60c86", "Lovart", "portrait-studio"):
            assert needle not in visible, needle
        cjk = re.compile(r"[\u4e00-\u9fff]")
        body = "\n".join(await card.locator(".ca-q__body").all_inner_texts())
        assert bool(cjk.search(body)) is (lang == "zh"), body
        await _shot(pg, f"card-{lang}")
        await card.locator(".ca-q__body").evaluate("el => { el.scrollTop = el.scrollHeight }")
        await _shot(pg, f"card-{lang}-bottom")
        for i in range(3):
            await blocks.nth(i).locator(".ca-q__opt").first.click()
        submit = card.locator(".ca-q__submit")
        for _ in range(6):  # scroll card: Next scrolls, Submit appears at the bottom
            if LOC[lang]["chatMessage.submit"] in await submit.inner_text():
                break
            await submit.click()
            await pg.wait_for_timeout(400)
        await submit.click()
        for _ in range(100):
            if agent.results:
                break
            await asyncio.sleep(0.1)
        name, answer = agent.results[0]
        assert name == "ask_user" and answer["status"] == "answered", answer
        assert {k: v["selected"] for k, v in answer["answers"].items()} == {"ps_shots": ["A"], "ps_outfit": ["A"], "ps_scene": ["A"]}
        from ComfyArt.api import portrait_studio
        assert portrait_studio.images_for(answer["answers"]["ps_shots"]["selected"][0]) == 3
        assert _paid(mock_ws) == []
        await browser.close()
