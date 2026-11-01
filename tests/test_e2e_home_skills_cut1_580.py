"""#580 cut 1 e2e @1280x800 (sidebar expanded, home column 928): 6 quick-start cards ≈141 wide (cover 141×106, 4:3),
gap 16, no horizontal scroll; Skill 案例 masonry 3 columns ≈299 wide, gap 16, no repeated skill. Mock only, $0."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")


async def _measure(app_url, width, *, collapsed=False):
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": width, "height": 800})).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.rail.collapsed','{'1' if collapsed else '0'}');")
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured-grid").wait_for()
        await pg.wait_for_timeout(200)
        m = await pg.evaluate(
            """() => {
              const b = (el) => { const q = el.getBoundingClientRect(); return {x: q.x, w: q.width, h: q.height}; };
              const grid = document.querySelector('.ca-skillgrid');
              const cards = [...grid.querySelectorAll('.ca-skillcard')].map(b);
              const covers = [...document.querySelectorAll('[data-testid="home-skill-cover"]')].map(b);
              const cols = [...document.querySelectorAll('[data-testid="home-featured-col"]')].filter(c => c.children.length).map(b);
              const allCols = [...document.querySelectorAll('[data-testid="home-featured-col"]')].map(b);
              const names = [...document.querySelectorAll('[data-testid="home-featured-card"] .ca-featured__title')].map(e => e.textContent);
              return {grid: b(grid), scroll: grid.scrollWidth - grid.clientWidth, cards, covers, cols: allCols, names};
            }"""
        )
        await browser.close()
        return m


async def test_cut1_1280_expanded(app_url):  # noqa: F811
    m = await _measure(app_url, 1280)
    assert abs(m["grid"]["w"] - 928) <= 1
    assert len(m["cards"]) == 6 and m["scroll"] <= 0
    for c in m["cards"]:
        assert abs(c["w"] - 141) <= 1.5, c
    for a, b in zip(m["cards"], m["cards"][1:]):
        assert abs(b["x"] - (a["x"] + a["w"]) - 16) <= 0.6
    for cv in m["covers"]:
        assert abs(cv["w"] - 141) <= 1.5 and abs(cv["h"] - 106) <= 1.5, cv
    assert len(m["cols"]) == 3, m["cols"]
    for c in m["cols"]:
        assert abs(c["w"] - 299) <= 1.5, c
    for a, b in zip(m["cols"], m["cols"][1:]):
        assert abs(b["x"] - (a["x"] + a["w"]) - 16) <= 0.6
    assert len(m["names"]) == len(set(m["names"])) and m["names"]


async def test_cut1_1920_five_columns(app_url):  # noqa: F811
    m = await _measure(app_url, 1920)
    assert len(m["cards"]) == 6 and m["scroll"] <= 0
    assert len(m["cols"]) == 5
