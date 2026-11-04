"""#673 e2e (mock only, $0): the 9 hidden Phase2 skills appear nowhere on home (featured, chips, + → 技能) or the
Skills page (every chip). Set HIDE673_SHOTS=/dir for zh-light / en-dark PNGs."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_skills_hide_673 import HIDDEN, MAIN_ORDER_40

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("HIDE673_SHOTS")
SEL = ",".join(f'[data-skill="{h}"]' for h in HIDDEN)


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=False)


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_hidden_skills_absent_home_and_skills_page(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured-card").first.wait_for()
        await pg.get_by_test_id("home-featured").scroll_into_view_if_needed()
        await pg.wait_for_timeout(400)
        assert await pg.locator(SEL).count() == 0
        await _shot(pg, f"home-featured-{lang}-{theme}")
        for chip in await pg.locator('[data-testid^="home-chip-"]').all():
            await chip.click()
            await pg.wait_for_timeout(150)
            assert await pg.locator(SEL).count() == 0, await chip.get_attribute("data-testid")
        await pg.reload()
        await pg.get_by_test_id("home-plus").wait_for(state="visible")
        await pg.get_by_test_id("home-plus").click()
        await pg.get_by_test_id("home-plus-skills").click()
        rows = pg.get_by_test_id("home-skill-row")
        await rows.first.wait_for()
        ids = [await r.get_attribute("data-skill") for r in await rows.all()]
        assert ids == MAIN_ORDER_40, ids
        await pg.keyboard.press("Escape")

        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        await pg.wait_for_timeout(400)
        wall = [await c.get_attribute("data-skill") for c in await pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"]').all()]
        assert wall == MAIN_ORDER_40, wall
        await _shot(pg, f"skills-page-{lang}-{theme}")
        for chip in await pg.locator('[data-testid^="skills-chip-"]').all():
            await chip.click()
            await pg.wait_for_timeout(150)
            assert await pg.locator(SEL).count() == 0, await chip.get_attribute("data-testid")
        if lang == "zh":
            web = pg.get_by_test_id("skills-chip-website")
            if await web.count():
                await web.click()
                await pg.wait_for_timeout(300)
                await _shot(pg, f"skills-chip-website-{lang}-{theme}")
        assert not errors, errors
        await browser.close()
