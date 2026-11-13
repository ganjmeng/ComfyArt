"""#956 / #957 Full App mock e2e ($0): default skill-dialog upload → answer card →
generate_image missing required params is refused in the real chat, and valid
args submit onto the canvas. Not a standalone text layout.

PARAM_GUARD_SHOTS=/dir keeps the Full App screenshots.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from conftest import FakeProvider, write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_skill_e2e_portrait_studio import ScriptedAgent as _PortraitAgent, _call


class ScriptedAgent(_PortraitAgent):
    id = "fake-param-guard"
    label = "FakeParamGuard"

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("PARAM_GUARD_SHOTS")
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text(encoding="utf-8")) for lg in ("zh", "en")}
UPLOAD = Path(__file__).parent / "fixtures" / "ma_subject_691.png"


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing")


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


def _shot(pg, name):
    async def go():
        if not SHOTS:
            return
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=False)
    return go()


def _refs(turn):
    refs = []
    for a in getattr(turn, "attachments", None) or []:
        if isinstance(a, dict):
            refs.append(str(a.get("url") or a.get("src") or a.get("id") or "").strip())
        elif a:
            refs.append(str(a))
    refs = [r for r in refs if r]
    return refs or ["loose:0"]


async def _open_skill(p, app_url, lang, sid, sockets):  # noqa: F811
    try:
        browser = await p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"chromium not available, this e2e must not skip: {e}")
    ctx = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="zh-CN" if lang == "zh" else "en-US",
    )
    await ctx.route_web_socket(__import__("re").compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light')"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-wall").wait_for(timeout=20000)
    card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="{sid}"]')
    await card.scroll_into_view_if_needed()
    await card.hover()
    await card.get_by_test_id("skills-card-try").click()
    dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
    await dlg.wait_for(timeout=15000)
    await dlg.locator('input[type="file"]').first.set_input_files(str(UPLOAD))
    await pg.wait_for_function(
        "() => { const b = document.querySelector('[data-testid=skill-run-go]');"
        " return b && !b.disabled && !b.getAttribute('data-missing'); }"
    )
    await dlg.get_by_test_id("skill-run-go").click()
    await pg.locator(".ca-composer__input").wait_for(timeout=20000)
    # #725: the skill dialog lands ask+ref+skill as a composer draft; it is not auto-sent.
    await pg.locator(".ca-composer").get_by_text(ScriptedAgent.label, exact=True).wait_for(timeout=15000)
    box = pg.locator(".ca-composer__input")
    await box.click()
    await box.press("Enter")
    await _bind_open_project(pg)
    return browser, pg


async def _answer_first_options(pg, lang, n=3):
    card = pg.locator('[data-testid="question-dock"] .ca-q')
    await card.wait_for(timeout=20000)
    blocks = card.locator(".ca-q__block")
    for i in range(min(n, await blocks.count())):
        opts = blocks.nth(i).locator(".ca-q__opt")
        if await opts.count():
            await opts.first.click()
    submit = card.locator(".ca-q__submit")
    for _ in range(8):
        if LOC[lang]["chatMessage.submit"] in await submit.inner_text():
            break
        await submit.click()
        await pg.wait_for_timeout(300)
    await submit.click()
    await pg.wait_for_timeout(400)



async def _bind_open_project(pg):
    """Stub PromptServer has no live sockets; seed the current tab like test_e2e_auto_pose_game_707."""
    from ComfyArt.api import mcp_commands
    from server import PromptServer
    project = await pg.evaluate("() => new URL(location.href).searchParams.get('project') || ''")
    pages = {}
    for _ in range(50):
        pages = dict(mcp_commands._pages)
        if project and project in pages.values():
            break
        if not project and pages:
            break
        await asyncio.sleep(0.1)
    for client, proj in list(pages.items()):
        if not project or proj == project:
            PromptServer.instance.sockets[client] = object()
    bound = {c: pr for c, pr in mcp_commands._pages.items() if not project or pr == project}
    assert bound, f"the canvas did not register a project (url={project!r} pages={pages!r})"
    return bound


def _paid(mock_ws):  # noqa: F811
    return mock_ws["submits"] + mock_ws["quotes"]


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_portrait_upload_card_reject_and_valid(
    app_url, mock_ws, agent, ws_forward, lang,  # noqa: F811
):
    from ComfyArt.api import portrait_studio as ps
    from ComfyArt.bot.providers import BotEvent

    async def steps(a, turn, emit):
        sloppy = {
            "questions": [
                {"id": "ps_shots", "prompt": "shots", "options": [{"id": "A", "label": "A"}], "page": 1},
                {"id": "ps_outfit", "prompt": "outfit", "options": [{"id": "A", "label": "A"}], "page": 1},
                {"id": "ps_scene", "prompt": "scene", "options": [{"id": "A", "label": "A"}], "page": 1},
            ],
            "page_count": 3, "allow_skip": True, "allow_other": True,
        }
        await _call(a, emit, "ask_user", sloppy, 1)
        refs = _refs(turn)
        # #957 paid failure: refs present, skill/shot omitted.
        missing = await _call(a, emit, "generate_image", {
            "prompt": "professional portrait set", "refs": refs, "count": 1,
        }, 2)
        await emit(BotEvent(t="delta", text=missing.get("user_message") or missing.get("error") or "NO ERROR"))
        a.missing = missing
        a.refs = refs
        for _ in range(150):
            if getattr(a, "snap_reject", False):
                break
            await asyncio.sleep(0.1)
        if missing.get("kind") == "missingSkillParams":
            ok = await _call(a, emit, "generate_image", {
                "prompt": "face close-up, casual look, solid studio backdrop",
                "skill": "portrait-studio", "refs": refs, "shot": "closeup", "count": 1,
            }, 3)
            a.ok = ok
        else:
            a.ok = None

    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, lang, "portrait-studio", ws_forward)
        await _answer_first_options(pg, lang)
        for _ in range(150):
            if getattr(agent, "missing", None) is not None:
                break
            await asyncio.sleep(0.1)
        missing = agent.missing
        await _shot(pg, f"956-957-{lang}-portrait-reject")
        agent.snap_reject = True
        assert missing.get("kind") == "missingSkillParams", missing
        assert missing.get("submitted") is False and missing.get("charged") is False
        assert "skill" in (missing.get("missing") or []) and "shot" in (missing.get("missing") or [])
        text = await pg.locator(".ca-chat").inner_text()
        assert missing.get("user_message") in text
        assert await pg.locator(".ca-composer").count() == 1
        for _ in range(150):
            if getattr(agent, "ok", None) is not None:
                break
            await asyncio.sleep(0.1)
        ok = agent.ok
        assert ok and ok.get("submitted") is not False
        assert ok.get("ids") or ok.get("status") != "failed", ok
        # The mock generate should have been submitted once for the valid call.
        assert mock_ws["submits"], "valid args must reach the mock WaveSpeed submit"
        await pg.wait_for_timeout(800)
        await _shot(pg, f"956-957-{lang}-portrait-valid")
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_packaging_upload_card_reject_and_valid(
    app_url, mock_ws, agent, ws_forward, lang,  # noqa: F811
):
    from ComfyArt.bot.providers import BotEvent

    async def steps(a, turn, emit):
        card = {
            "questions": [
                {"id": "pk_product", "prompt": "这款产品具体是什么？品牌名/产品名怎么定（直接决定包装上的文案与必要信息版面）",
                 "options": [{"id": "A", "label": "护肤精华油"}, {"id": "B", "label": "面乳"}, {"id": "C", "label": "喷雾"}]},
                {"id": "pk_color", "prompt": "包装的主色方向选哪个？",
                 "options": [{"id": "A", "label": "琥珀棕"}, {"id": "B", "label": "黑色"}, {"id": "C", "label": "白色"}]},
                {"id": "pk_scope", "prompt": "这套包装要交付到哪个范围？（可多选）",
                 "options": [{"id": "A", "label": "核心三件：外盒 ＋ 瓶标 ＋ 内托"}]},
            ],
            "page_count": 3, "allow_skip": True, "allow_other": True,
        }
        await _call(a, emit, "ask_user", card, 1)
        # #956 paid failure: skill present, refs omitted, upload is in the chat.
        missing = await _call(a, emit, "generate_image", {
            "prompt": "the package and the product together",
            "skill": "product-to-packaging", "count": 1,
        }, 2)
        await emit(BotEvent(t="delta", text=missing.get("user_message") or missing.get("error") or "NO ERROR"))
        a.missing = missing
        refs = _refs(turn)
        a.refs = refs
        for _ in range(150):
            if getattr(a, "snap_reject", False):
                break
            await asyncio.sleep(0.1)
        if missing.get("kind") == "missingSkillParams":
            ok = await _call(a, emit, "generate_image", {
                "prompt": "the package and the product together",
                "skill": "product-to-packaging", "refs": refs, "count": 1,
            }, 3)
            a.ok = ok
        else:
            a.ok = None

    agent.steps = steps
    before = len(mock_ws["submits"])
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, lang, "product-to-packaging", ws_forward)
        await _answer_first_options(pg, lang)
        for _ in range(150):
            if getattr(agent, "missing", None) is not None:
                break
            await asyncio.sleep(0.1)
        missing = agent.missing
        await _shot(pg, f"956-957-{lang}-packaging-reject")
        agent.snap_reject = True
        assert missing.get("kind") == "missingSkillParams", missing
        assert missing.get("submitted") is False and missing.get("charged") is False
        assert "refs" in (missing.get("missing") or [])
        assert len(mock_ws["submits"]) == before  # missing refs: zero upstream submit
        text = await pg.locator(".ca-chat").inner_text()
        assert missing.get("user_message") in text
        for _ in range(150):
            if getattr(agent, "ok", None) is not None:
                break
            await asyncio.sleep(0.1)
        ok = agent.ok
        assert ok and (ok.get("ids") or ok.get("submitted") is True), ok
        assert len(mock_ws["submits"]) > before
        await pg.wait_for_timeout(800)
        await _shot(pg, f"956-957-{lang}-packaging-valid")
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_portrait_all_omitted_then_text_only_switch(
    app_url, mock_ws, agent, ws_forward, lang,
):
    """Real skill upload + card, continuation refusal, then same-chat text switch."""
    from ComfyArt.bot.providers import BotEvent
    from ComfyArt.api import portrait_studio as ps

    agent.phase = 0
    agent.outcomes = []
    agent.chat_ids = []

    async def steps(a, turn, emit):
        a.chat_ids.append(turn.chat_id)
        phase = a.phase
        a.phase += 1
        if phase == 0:
            await _call(a, emit, "ask_user", {"questions": ps.card_questions(lang)}, 10)
        result = await _call(a, emit, "generate_image", {
            "prompt": "professional portrait" if phase < 2 else "a landscape poster",
            "count": 1,
        }, 11 + phase)
        a.outcomes.append(result)
        await emit(BotEvent(t="delta", text=result.get("user_message") or
                           result.get("error") or "Mock text-to-image completed ($0)."))

    async def ready(pg, count):
        for _ in range(200):
            if len(agent.outcomes) >= count and not await pg.get_by_test_id("composer-stop").count():
                return
            await asyncio.sleep(0.1)
        pytest.fail(f"turn {count} did not finish: {agent.outcomes}")

    agent.steps = steps
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, lang, "portrait-studio", ws_forward)
        try:
            await _answer_first_options(pg, lang)
            await ready(pg, 1)
            for key in ("submitted", "charged"):
                assert agent.outcomes[0].get(key) is False
            assert set(agent.outcomes[0].get("missing", [])) == {"refs", "skill", "shot"}
            assert not mock_ws["submits"]
            await _shot(pg, f"958-{lang}-portrait-all-omitted-reject")
            box = pg.locator(".ca-composer__input")
            await box.fill("继续形象照，换蓝色背景。" if lang == "zh" else
                           "Continue the portrait, change the background to blue.")
            await box.press("Enter")
            await ready(pg, 2)
            assert agent.outcomes[1].get("kind") == "missingSkillParams"
            assert agent.outcomes[1].get("submitted") is False
            assert not mock_ws["submits"]
            capsules = pg.locator('[data-testid="composer-capsule"]')
            while await capsules.count():
                await capsules.first.locator('button').click()
            await box.fill('结束刚才的人像任务，不要使用之前上传的照片。这是全新的独立文生图请求：画一张山间湖泊风景，不要人物，也不要参考图。' if lang == "zh" else
                           'End the previous portrait task. Do not use the uploaded photo. This is a new independent text-to-image request: draw a mountain lake landscape, no person and no reference image.')
            await box.press("Enter")
            await ready(pg, 3)
            assert len(set(agent.chat_ids)) == 1, agent.chat_ids
            assert not agent.last_turn.attachments, agent.last_turn.attachments
            assert agent.outcomes[2].get("kind") != "missingSkillParams", agent.outcomes[2]
            assert mock_ws["submits"], agent.outcomes[2]
            await pg.wait_for_timeout(800)
            await _shot(pg, f"958-{lang}-same-chat-text-only-t2i")
        finally:
            await browser.close()
