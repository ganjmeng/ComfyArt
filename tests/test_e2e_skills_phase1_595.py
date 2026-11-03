"""#595 Phase1-S5 mount e2e (mock only, $0): home quick-start hot order, website chip, new6 dialog→Agent project."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")

HOT_QUICK = ["product", "multi-angle", "brand", "character", "logo-material", "packaging"]


async def _open_home(p, app_url, lang="zh"):  # noqa: F811
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.rail.collapsed','0');")
    await pg.goto(app_url)
    await pg.get_by_test_id("home-start-skill").wait_for()
    return browser, pg


async def test_home_quickstart_hot_order_and_website_chip(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open_home(p, app_url)
        cards = pg.get_by_test_id("home-skill-card")
        await cards.first.wait_for()
        assert await cards.count() == 6
        ids = await cards.evaluate_all("els => els.map(e => e.dataset.skill)")
        assert ids == HOT_QUICK
        # website chip lit on home explore chips
        assert await pg.get_by_test_id("home-chip-website").count() == 1
        await pg.get_by_test_id("home-chip-website").click()
        shown = await pg.get_by_test_id("home-skill-card").evaluate_all("els => els.map(e => e.dataset.skill)")
        assert set(shown) <= {"mobile-ui", "web-product", "ppt-visual", "product-website", "premium-website", "restaurant-website"}  # + #634 ppt-visual, #640 NEW19 website skills
        assert "mobile-ui" in shown and "web-product" in shown
        await browser.close()


async def test_multi_angle_carousel_and_brand_dialog_to_agent(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open_home(p, app_url, "en")
        # new6: horizontal examples carousel + presets + inputs present
        await pg.locator('[data-testid="home-skill-card"][data-skill="multi-angle"]').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == "multi-angle"
        await pg.get_by_test_id("skill-run-example-thumb").first.wait_for()
        assert await pg.get_by_test_id("skill-run-examples").count() == 1
        assert await pg.get_by_test_id("skill-run-example-thumb").count() >= 2
        assert await dlg.locator('[data-left="examples"]').count() == 1  # #666 examples-only left pane
        # no preset UI on the right: 0 preset tiles / chips / current-template row (#691 option 2)
        assert await pg.get_by_test_id("skill-run-preset").count() == 0
        assert await dlg.locator('[data-testid="skill-run-preset-chips"], [data-testid="skill-run-current"]').count() == 0
        # exact Upload→Additional right pane is asserted on thumbnail (#657 skill); see test below / #691
        await pg.keyboard.press("Escape")
        await dlg.wait_for(state="hidden")
        # Phase1 upgrade skill: dialog → new Agent project (AC ≥1)
        await pg.locator('[data-testid="home-skill-card"][data-skill="brand"]').click()
        await dlg.wait_for()
        await pg.locator('[data-testid="skill-run-field"][data-key="brandInfo"]').fill("Autumn launch kit")
        await pg.get_by_test_id("skill-run-go").click()
        await pg.wait_for_url(re.compile(r"[?&]skill=brand"), timeout=10_000)
        assert "mode=agent" in pg.url
        await browser.close()


async def test_thumbnail_right_pane_upload_then_additional(app_url):  # noqa: F811
    """#657: thumbnail right pane = Upload + Additional only, no preset UI (#691)."""
    async with pw.async_playwright() as p:
        from test_e2e_skill_cards_494 import _open
        from test_e2e_skill_modal_541 import _modal
        browser, pg = await _open(p, app_url, "en")  # skills wall (thumbnail is not a home quick-start card)
        dlg = await _modal(pg, "thumbnail")
        assert await dlg.get_attribute("data-skill") == "thumbnail"
        right = dlg.locator(".ca-skillrun__right")
        await right.locator('[data-testid="skill-run-field"]').first.wait_for()
        fields = await right.locator('[data-testid="skill-run-field"]').evaluate_all(
            "els => els.map(e => [e.dataset.key, e.dataset.type])")
        assert fields == [["file", "image"], ["note", "textarea"]], fields
        assert await pg.get_by_test_id("skill-run-preset").count() == 0
        assert await dlg.locator('[data-testid="skill-run-preset-chips"], [data-testid="skill-run-current"]').count() == 0
        await browser.close()
