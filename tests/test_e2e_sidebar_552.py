"""#552 sidebar finish e2e @1280x800: grey rail bg (collapsed+expanded), collapsed hides Beta, expanded recent list. Mock only, $0."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_sidebar_495 import NAMES, _seed

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("SIDEBAR_552_SHOTS")
RAIL_BG = {"light": "rgb(245, 245, 245)", "dark": "rgb(28, 28, 28)"}


async def _open(p, app_url, lang, theme, collapsed):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"""localStorage.setItem('comfyart.lang','{lang}');
            localStorage.setItem('comfyart.theme','{theme}');
            localStorage.setItem('comfyart.rail.collapsed','{"1" if collapsed else "0"}');"""
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("account-rail").wait_for()
    return browser, pg


async def _shot(pg, name):
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.evaluate("() => window.scrollTo(0, 0)")
    await pg.wait_for_timeout(500)
    await pg.screenshot(path=f"{SHOTS}/{name}.png")


async def _bg(loc):
    return await loc.evaluate("el => getComputedStyle(el).backgroundColor")


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_sidebar_552_collapsed_and_expanded(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme, collapsed=True)
        await _seed(pg, NAMES)
        await pg.reload()
        rail = pg.get_by_test_id("account-rail")
        await rail.wait_for()
        assert await rail.get_attribute("data-collapsed") == "true"
        # (1) collapsed rail grey, distinct from page
        page_bg = await _bg(pg.get_by_test_id("home-shell"))
        assert await _bg(rail) == RAIL_BG[theme]
        assert await _bg(rail) != page_bg
        # (2) collapsed: no Beta badge, Arti entry still there
        assert await pg.get_by_test_id("rail-arti").count() == 1
        assert await pg.get_by_test_id("rail-arti-beta").count() == 0
        assert await pg.get_by_test_id("rail-recent").count() == 0
        await _shot(pg, f"552-collapsed-{lang}-{theme}")
        # (3) expand → 240, same grey, Beta back, recent list from data
        await pg.get_by_test_id("rail-expand").click()
        await pg.get_by_test_id("rail-recent").wait_for()
        box = await rail.bounding_box()
        assert box and box["width"] == 240
        assert await _bg(rail) == RAIL_BG[theme]
        assert await pg.get_by_test_id("rail-arti-beta").count() == 1
        rows = pg.get_by_test_id("rail-recent-row")
        assert await rows.count() == 8
        assert await rows.first.inner_text() == NAMES[0]  # pinned first
        await pg.mouse.move(700, 400)
        await _shot(pg, f"552-expanded-{lang}-{theme}")
        await browser.close()
