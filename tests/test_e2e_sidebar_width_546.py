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


async def _measure(p, app_url, width, *, collapsed, lang="zh", theme="light", seed=True):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": width, "height": 900})
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"""localStorage.setItem('comfyart.lang','{lang}');
            localStorage.setItem('comfyart.theme','{theme}');
            {"" if not seed else "localStorage.setItem('comfyart.rail.collapsed','" + ("1" if collapsed else "0") + "');"}"""
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
          const b = (id) => { const el = rail.querySelector(`[data-testid="${id}"]`); if (!el) return null; const q = el.getBoundingClientRect(); return {x: q.x, y: q.y, w: q.width, h: q.height}; };
          const icon = btn.querySelector('.ca-icon').getBoundingClientRect();
          return {rail: r(rail), btn: r(btn), tools: r(tools), border: cs.borderRightWidth,
            expanded: rail.hasAttribute('data-expanded'),
            new: b('rail-new'), home: b('rail-home'), projects: b('rail-projects'), toggle: b('rail-collapse'),
            icon: {w: icon.width, h: icon.height, cx: icon.x + icon.width / 2}};
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


async def test_default_is_collapsed(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        m = await _measure(p, app_url, 1280, collapsed=True, seed=False)
    assert m["expanded"] is False


@pytest.mark.parametrize("width", [1280, 1440])
async def test_collapsed_matches_lovart(app_url, width):  # noqa: F811
    async with pw.async_playwright() as p:
        m = await _measure(p, app_url, width, collapsed=True)
    assert m["rail"] == {"x": 0, "w": 60}
    assert m["home"]["x"] == 12 and m["home"]["w"] == 36 and m["home"]["h"] == 36
    assert m["icon"]["w"] == 20 and m["icon"]["h"] == 20 and m["icon"]["cx"] == 30
    assert m["projects"]["y"] - m["home"]["y"] == 38
    assert m["home"]["y"] - m["new"]["y"] == 52
    assert m["tools"]["x"] == 116 and m["tools"]["w"] == width - 60 - 112  # 1108 @1280


async def test_expanded_toggle_and_pitch(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        m = await _measure(p, app_url, 1280, collapsed=False)
    assert m["toggle"]["x"] == 196 and m["toggle"]["w"] == 36 and m["toggle"]["h"] == 36
    assert m["projects"]["y"] - m["home"]["y"] == 38
    assert m["home"]["y"] - m["new"]["y"] == 52


async def test_toggle_persists_across_reload(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await pg.goto(app_url)
        rail = pg.get_by_test_id("account-rail")
        await pg.get_by_test_id("rail-expand").click()
        await pg.get_by_test_id("rail-collapse").wait_for()
        await pg.reload()
        await pg.get_by_test_id("rail-collapse").wait_for()
        assert (await rail.bounding_box())["width"] == 240
        await pg.get_by_test_id("rail-collapse").click()
        await pg.reload()
        await pg.get_by_test_id("rail-expand").wait_for()
        assert (await rail.bounding_box())["width"] == 60
        await browser.close()
