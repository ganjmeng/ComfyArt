"""#673/#812 e2e (mock only, $0): after #812 yingzao is listed again — deep link attaches the chip and does NOT
show skills.hiddenUnavailable. Hide-guard machinery remains for any future hide-list ids.
HIDE673_SHOTS=/dir keeps zh-light / en-dark PNGs."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conftest import write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_skills_hide_673 import COPY

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("HIDE673_SHOTS")
NOTICE = '[data-testid="skill-hidden-notice"]'
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text()) for lg in ("zh", "en")}
PAID = ("wavespeed", "kie", "/send", "/log", "/comfyart/generate", "/prompt")


@pytest.fixture
def fake_agent(fake_provider):
    write_settings(**{"bot-provider": fake_provider.id, "enable-bot": True, "enable-mcp": True})
    return fake_provider


async def _open(p, url, lang, theme):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    await pg.goto(url)
    await pg.locator(".ca-composer__input").wait_for()
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)
    return browser, pg


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def _posts(reqs):
    return [r for r in reqs if r[0] != "GET" or any(k in r[1] for k in ("wavespeed", "kie"))]


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_deep_link_to_yingzao_attaches_after_812_unhide(app_url, mock_ws, fake_agent, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url + f"?project=p673link{lang}&new=1&skill=yingzao&mode=agent", lang, theme)
        # #812: listed again — no hidden notice; chip may show name
        assert await pg.locator(NOTICE).count() == 0
        name = LOC[lang].get("skills.yingzao")
        if name:
            assert name in await pg.locator(".ca-composer").inner_text()
        await _shot(pg, f"yingzao-link-listed-{lang}-{theme}")
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_resend_listed_yingzao_session_has_no_hidden_notice_812(app_url, mock_ws, fake_agent, lang, theme):  # noqa: F811
    """#812: yingzao is listed — regenerating an old session must not show hiddenUnavailable."""
    from ComfyArt.api import chat_store
    project = f"p673resend{lang}"
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url + f"?project={project}&new=1", lang, theme)
        chat = await pg.evaluate("""async ([project, provider]) => (await (await fetch('/comfyart/bot/chats', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify({project, provider})})).json()).chat""", [project, fake_agent.id])
        skill_name = LOC[lang]["skills.yingzao"]
        u = chat_store.create_message(chat_id=chat["id"], role="user", blocks=[{"type": "text", "text": "old alley"}, {"type": "skill", "name": skill_name}])
        chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=[{"type": "text", "text": "OLD-REPLY-673"}], parent_id=u["id"])
        await pg.reload()
        await pg.locator(".ca-composer__input").wait_for()
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        await pg.get_by_title(LOC[lang]["agentPanel.chatHistory"]).first.click()
        await pg.locator(".ca-history__item").first.click()
        await pg.get_by_text("OLD-REPLY-673").wait_for(timeout=15000)
        await pg.get_by_text("OLD-REPLY-673").last.hover()
        await pg.get_by_title(LOC[lang]["common.regenerate"]).last.dispatch_event("click")
        await pg.wait_for_timeout(800)
        assert await pg.locator(NOTICE).count() == 0
        assert await pg.get_by_text("OLD-REPLY-673").count() >= 1
        await _shot(pg, f"yingzao-resend-listed-{lang}-{theme}")
        await browser.close()
