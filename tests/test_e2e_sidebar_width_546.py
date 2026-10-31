"""#546 e2e: measure rail + home column vs Lovart (1280 / 1440). Mock only, $0."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("SIDEBAR_546_SHOTS")


async def _measure(p, app_url, width, *, collapsed, lang="zh", theme="light"):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": width, "height": 900})
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"""localStorage.setItem('comfyart.lang','{lang}');
            localStorage.setItem('comfyart.theme','{theme}');
            localStorage.setItem('comfyart.rail.collapsed','{"1" if collapsed else "0"}');"""
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-tools").wait_for()
    m = await pg.evaluate(
        """() => {
          const r = (el) => { const b = el.getBoundingClientRect(); return {x: b.x, w: b.width}; };
          const rail = document.querySelector('[data-testid="account-rail"]');
          const btn = rail.querySelector('[data-testid="rail-home"]');
          const tools = document.querySelector('[data-testid="home-tools"]');
          const cs = getComputedStyle(rail);
          return {rail: r(rail), btn: r(btn), tools: r(tools), border: cs.borderRightWidth};
        }"""
    )
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(500)
        state = "collapsed" if collapsed else "expanded"
        await pg.screenshot(path=f"{SHOTS}/546-{width}-{state}-{lang}-{theme}.png")
    await browser.close()
    return m


@pytest.mark.parametrize("width,col", [(1280, 928), (1440, 1088)])
async def test_expanded_matches_lovart(app_url, width, col):  # noqa: F811
    async with pw.async_playwright() as p:
        m = await _measure(p, app_url, width, collapsed=False)
    assert m["rail"] == {"x": 0, "w": 240}
    assert m["btn"]["x"] == 12 and m["btn"]["w"] == 216
    assert m["border"] == "0px"
    assert m["tools"]["x"] == 296 and m["tools"]["w"] == col


async def test_collapsed_rail(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        m = await _measure(p, app_url, 1280, collapsed=True)
    # TODO(#546): pin to Lovart collapsed numbers once measured
    assert m["rail"]["x"] == 0 and m["rail"]["w"] <= 70
    assert m["tools"]["x"] == m["rail"]["w"] + 56
