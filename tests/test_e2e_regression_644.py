"""#644 e2e (mock only, $0).
(1) The live home + Skills page after #673: the Phase3 hard-lock 20 (19 NEW + upgrade `thumbnail`) are all on the Skills
    wall, none of the 9 hidden ids is anywhere, and QA644_SHOTS=/dir writes the 20-image regression set.
(2) The #673 hidden-skill notice sits clear of the chat's 「使用品牌套件」/'Use a brand kit' button and of the composer
    mascot, in zh/en x light/dark.
(3) An old ?skill= deep link to a hidden skill keeps its reference images (canvas + composer), not just the text."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conftest import write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_skills_hide_673 import COPY, HIDDEN, MAIN_ORDER_40

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("QA644_SHOTS")
NOTICE = '[data-testid="skill-hidden-notice"]'
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text()) for lg in ("zh", "en")}
HARDLOCK_20 = [
    "thumbnail", "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website", "studio-model",
    "youtube-channel-banner", "ai-model", "product-to-packaging", "game-art", "portrait-studio", "premium-website",
    "animated-poster", "pose-fission", "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website",
    "clothing-swap",
]
LR4 = ["taobao-product", "before-after", "linkedin-banner", "clothing-swap"]
COMBOS = [("zh", "light"), ("en", "dark"), ("zh", "dark"), ("en", "light")]
HIDDEN_SEL = ",".join(f'[data-skill="{h}"]' for h in HIDDEN)
PAID = ("wavespeed", "kie", "/send", "/generate", "/prompt")  # any non-GET to these = an agent turn or a paid submit
PNG = bytes.fromhex(  # 2x2 opaque PNG
    "89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73"
    "0000001649444154789c63f8cfc0f09f8181e1ff7f0606000024f205fd1c5a4a5f0000000049454e44ae426082")


@pytest.fixture
def fake_agent(fake_provider):
    write_settings(**{"bot-provider": fake_provider.id, "enable-bot": True, "enable-mcp": True})
    return fake_provider


async def _page(p, lang, theme, height=900):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": height})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    return browser, pg


async def _dismiss(pg):
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)


async def _shot(pg, name, full=False):
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(600)
    if full:  # grow the viewport to the tallest scroll container: the whole waterfall / grid in one PNG
        await pg.evaluate("document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0 })")
        h = await pg.evaluate("Math.min(16000, Math.max(...[...document.querySelectorAll('*')].map(e => e.scrollHeight - e.clientHeight + innerHeight)))")
        await pg.set_viewport_size({"width": 1440, "height": int(h)})
        await pg.wait_for_timeout(1500)
    await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))
    if full:
        await pg.set_viewport_size({"width": 1440, "height": 900})
        await pg.wait_for_timeout(300)


@pytest.mark.parametrize("lang,theme", COMBOS)
async def test_live_home_and_skills_regression_20(app_url, lang, theme):  # noqa: F811
    """4 shots per combo (home featured, home full, Skills, Skills full) = 16, plus the 4 L/R skills' dialogs in zh-light."""
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured-card").first.wait_for()
        await pg.get_by_test_id("home-featured").scroll_into_view_if_needed()
        assert await pg.locator(HIDDEN_SEL).count() == 0
        await _shot(pg, f"home-featured-{lang}-{theme}")
        await _shot(pg, f"home-full-{lang}-{theme}", full=True)

        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        await pg.wait_for_timeout(400)
        wall = [await c.get_attribute("data-skill") for c in await pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"]').all()]
        assert wall == MAIN_ORDER_40, wall
        assert [s for s in wall if s in HARDLOCK_20] == HARDLOCK_20  # hard-lock 20: all present, table order
        assert not set(wall) & set(HIDDEN)
        await _shot(pg, f"skills-{lang}-{theme}")
        await _shot(pg, f"skills-full-{lang}-{theme}", full=True)
        if (lang, theme) == ("zh", "light"):
            for sid in LR4:
                card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="{sid}"]')
                await card.scroll_into_view_if_needed()
                await card.hover()
                await card.get_by_test_id("skills-card-try").click()
                dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
                await dlg.wait_for(timeout=10000)
                await _shot(pg, f"skill-dialog-{sid}-{lang}-{theme}")
                await pg.keyboard.press("Escape")
                await dlg.wait_for(state="detached")
        assert not errors, errors
        await browser.close()


@pytest.mark.parametrize("lang,theme", COMBOS)
async def test_hidden_skill_notice_clear_of_brand_kit_button(app_url, fake_agent, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        await pg.goto(app_url + f"?project=p644gap{lang}{theme}&new=1&skill=yingzao&mode=agent")
        await pg.locator(".ca-composer__input").wait_for()
        await _dismiss(pg)
        notice = pg.locator(NOTICE)
        await notice.wait_for(timeout=15000)
        assert (await notice.inner_text()).strip() == COPY[lang]
        kit = pg.locator(".ca-chat__start", has_text=LOC[lang]["agentPanel.useBrandKit"])
        await kit.wait_for()
        await pg.wait_for_timeout(300)
        k, n = await kit.bounding_box(), await notice.bounding_box()
        c = await pg.locator(".ca-composer").bounding_box()
        m = await pg.locator(".arti-mascot-wrap").bounding_box()
        assert n["y"] - (k["y"] + k["height"]) >= 12, (k, n)       # >= 12px under the brand-kit button, never on it
        assert m["y"] - (n["y"] + n["height"]) >= 4, (n, m)         # clear of the mascot that peeks over the composer
        assert n["y"] + n["height"] <= c["y"], (n, c)
        await _shot(pg, f"notice-gap-{lang}-{theme}")
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_hidden_skill_deep_link_keeps_text_and_refs(app_url, mock_ws, fake_agent, lang, theme):  # noqa: F811
    import folder_paths
    (folder_paths.STATE["base"] / "input" / "r644.png").write_bytes(PNG)
    reqs: list[str] = []
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        pg.on("request", lambda r: reqs.append(r.url) if r.method != "GET" else None)
        ref = "%2Fapi%2Fview%3Ffilename%3Dr644.png%26type%3Dinput"
        await pg.goto(app_url + f"?project=p644ref{lang}&new=1&skill=yingzao&mode=agent&ask=keep644&ref={ref}")
        await pg.locator(".ca-composer__input").wait_for()
        await _dismiss(pg)
        await pg.locator(NOTICE).wait_for(timeout=15000)
        assert await pg.locator(".ca-composer__input").input_value() == "keep644"
        caps = pg.get_by_test_id("composer-capsule")
        await caps.first.wait_for(timeout=10000)
        assert await caps.count() == 1                                   # the link's reference image is kept
        assert await pg.get_by_test_id("composer-skill-chip").count() == 0  # still no skill chip
        await pg.wait_for_timeout(1000)
        await _shot(pg, f"notice-refs-{lang}-{theme}")
        assert not [u for u in reqs if any(k in u for k in PAID)], reqs
        assert fake_agent.last_turn is None and mock_ws["submits"] == []
        await browser.close()
