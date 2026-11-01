"""#578 sidebar style e2e @1280x800 (zh light / en dark): bordered 新建项目 both states, Beta tag after Arti, recent pitch 38. Mock only, $0."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_sidebar_495 import NAMES, _seed

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("SIDEBAR_578_SHOTS")
BLUE = "rgb(59, 130, 246)"


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.mouse.move(700, 400)
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=f"{SHOTS}/{name}.png")


async def _style(loc, prop):
    return await loc.evaluate(f"el => getComputedStyle(el).{prop}")


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_sidebar_578_style(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
        await pg.add_init_script(
            f"""localStorage.setItem('comfyart.lang','{lang}');
                localStorage.setItem('comfyart.theme','{theme}');
                localStorage.setItem('comfyart.rail.collapsed','1');"""
        )
        await pg.goto(app_url)
        await pg.get_by_test_id("account-rail").wait_for()
        await _seed(pg, NAMES)
        await pg.reload()
        new = pg.get_by_test_id("rail-new")
        await new.wait_for()
        # (1) collapsed: ＋ inside a bordered 36 square
        assert await _style(new, "borderTopWidth") == "1px"
        assert await _style(new, "borderTopStyle") == "solid"
        box = await new.bounding_box()
        assert box and box["width"] == 36 and box["height"] == 36
        assert await pg.get_by_test_id("rail-arti-beta").count() == 0
        await _shot(pg, f"578-collapsed-{lang}-{theme}")
        await pg.get_by_test_id("rail-expand").click()
        await pg.get_by_test_id("rail-recent").wait_for()
        # (1) expanded: bordered, float-bg, rounded full-width button
        assert await _style(new, "borderTopWidth") == "1px"
        assert await _style(new, "borderTopLeftRadius") != "0px"
        assert await _style(new, "backgroundColor") == ("rgb(255, 255, 255)" if theme == "light" else await _style(pg.get_by_test_id("home-shell"), "backgroundColor"))
        nb = await new.bounding_box()
        assert nb and nb["width"] > 200
        # (2) Beta: light-blue tag, blue text, right after the Arti label
        beta = pg.get_by_test_id("rail-arti-beta")
        assert await _style(beta, "color") == BLUE
        bg = await _style(beta, "backgroundColor")
        assert bg not in (BLUE, "rgba(0, 0, 0, 0)")
        label = pg.get_by_test_id("rail-arti").locator(".ca-rail__label")
        lb, bb = await label.bounding_box(), await beta.bounding_box()
        assert lb and bb and 0 <= bb["x"] - (lb["x"] + lb["width"]) <= 10
        # (3) recent row pitch 38
        rows = pg.get_by_test_id("rail-recent-row")
        a, b = await rows.nth(0).bounding_box(), await rows.nth(1).bounding_box()
        assert a and b and b["y"] - a["y"] == 38
        await _shot(pg, f"578-expanded-{lang}-{theme}")
        await browser.close()
