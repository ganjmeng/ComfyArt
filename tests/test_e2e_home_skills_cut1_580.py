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
              const tiles = [...document.querySelectorAll('[data-testid="home-featured-card"]')]
                .sort((a, b) => a.dataset.order - b.dataset.order).map(e => ({skill: e.dataset.skill, preset: e.dataset.preset || null, img: e.querySelector('img').getAttribute('src')}));
              return {grid: b(grid), scroll: grid.scrollWidth - grid.clientWidth, cards, covers, cols: allCols, tiles};
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
    _check_tiles(m["tiles"])


async def test_cut1_1920_five_columns(app_url):  # noqa: F811
    m = await _measure(app_url, 1920)
    assert len(m["cards"]) == 6 and m["scroll"] <= 0
    assert len(m["cols"]) == 5
    _check_tiles(m["tiles"])


# built-in skills with real images in src/skills.ts (example-type: 效果示例; template-type: preset images)
EXAMPLE_SKILLS = {"poster", "social", "thumbnail", "banner", "interior"}
TEMPLATE_SKILLS = {"brand", "packaging", "character", "product", "motion"}


def _check_tiles(tiles):
    skills = [t["skill"] for t in tiles]
    assert set(skills) == EXAMPLE_SKILLS | TEMPLATE_SKILLS, set(skills)
    assert any(t["preset"] is None and t["skill"] in EXAMPLE_SKILLS for t in tiles)
    assert any(t["preset"] and t["skill"] in TEMPLATE_SKILLS for t in tiles)
    assert all(a != b for a, b in zip(skills, skills[1:])), skills  # data order: no adjacent duplicates
    assert len({t["img"] for t in tiles}) == len(tiles)
    assert len(tiles) > len(EXAMPLE_SKILLS | TEMPLATE_SKILLS)  # second round follows
    assert skills[: len(set(skills))] and len(set(skills[:10])) == 10  # first round: one per skill
    first_char = next(t for t in tiles if t["skill"] == "character")
    assert first_char["preset"] == "editorial"


async def test_cut1_example_tile_opens_dialog(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
        await pg.goto(app_url)
        card = pg.locator('[data-testid="home-featured-card"]:not([data-preset])').first
        await card.wait_for()
        skill = await card.get_attribute("data-skill")
        await card.click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == skill
        await browser.close()
