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
              const colSkills = [...document.querySelectorAll('[data-testid="home-featured-col"]')].map(c =>
                [...c.querySelectorAll('[data-testid="home-featured-card"]')]
                  .sort((a, b) => a.getBoundingClientRect().y - b.getBoundingClientRect().y).map(e => e.dataset.skill));
              const domSkills = [...document.querySelectorAll('[data-testid="home-featured-card"]')].map(e => e.dataset.skill);
              return {grid: b(grid), scroll: grid.scrollWidth - grid.clientWidth, cards, covers, cols: allCols, tiles, colSkills, domSkills};
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
    _check_columns(m)


async def test_cut1_1920_five_columns(app_url):  # noqa: F811
    m = await _measure(app_url, 1920)
    assert len(m["cards"]) == 6 and m["scroll"] <= 0
    assert len(m["cols"]) == 5
    _check_tiles(m["tiles"])
    _check_columns(m)


# #595 Phase1 mount: upgrade9 + new6 + interior (custom-workflow has no featured[]). featured-v1 (cut1) + featured-v2 (new6).
PHASE1_FEATURED = {
    "product", "multi-angle", "brand", "character", "logo-material", "packaging",
    "motion", "meta-ads", "poster", "thumbnail", "mobile-ui", "social",
    "marketing-campaign", "web-product", "banner", "interior",
}


def _check_tiles(tiles):
    skills = [t["skill"] for t in tiles]
    assert set(skills) == PHASE1_FEATURED, set(skills)
    # #588/#594: every skill ships washed featured[] (v1 upgrade9+interior, v2 Phase1 new6)
    assert all("/580/featured-v1/" in t["img"] or "/580/featured-v2/" in t["img"] for t in tiles), [t["img"] for t in tiles]
    assert all(a != b for a, b in zip(skills, skills[1:])), skills  # data order: no adjacent duplicates
    assert len({t["img"] for t in tiles}) == len(tiles)
    assert len(tiles) > len(PHASE1_FEATURED)  # second round follows
    n = len(PHASE1_FEATURED)
    assert len(set(skills[:n])) == n  # first round: one per skill
    first_char = next(t for t in tiles if t["skill"] == "character")
    assert "/580/featured-v1/character/01.webp" in first_char["img"]  # #588 featured[] supersedes featuredPreset
    # #595 hot mount: first featured tile is the first Phase1 hot id with featured (product)
    assert skills[0] == "product"


def _check_columns(m):
    # #580 QA: no adjacent duplicates in each rendered column (visual top→bottom order) and in DOM order
    for col in m["colSkills"]:
        assert all(a != b for a, b in zip(col, col[1:])), m["colSkills"]
    dom = m["domSkills"]
    assert all(a != b for a, b in zip(dom, dom[1:])), dom


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
