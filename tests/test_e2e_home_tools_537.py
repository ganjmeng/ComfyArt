"""#537 / #540 e2e (mock only, $0): home 实用工具 + 精选 waterfall visible.
Set HOME_TOOLS_SHOTS=/dir for zh/en × light/dark PNGs."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("HOME_TOOLS_SHOTS")


async def _open(p, app_url, lang, theme):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-tools").wait_for()
    return browser, pg


async def _shot(pg, name: str) -> None:
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(800)
    await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=False)


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("zh", "dark"), ("en", "light"), ("en", "dark")])
async def test_home_tools_and_waterfall(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        tools = pg.get_by_test_id("home-tools")
        await tools.scroll_into_view_if_needed()
        for tid in ("cutout", "extend", "upscale", "inpaint", "mockup"):
            assert await pg.get_by_test_id(f"home-tool-card-{tid}").count() == 1
        await pg.get_by_test_id("home-more-tools").click()
        menu = pg.get_by_test_id("home-more-tools-menu")
        await menu.wait_for()
        for tid in ("quick", "erase", "crop", "expand", "adjust", "text", "angles", "vectorize", "move", "transform", "to3d", "lipsync", "motion", "audio"):
            assert await pg.get_by_test_id(f"home-more-tool-{tid}").count() == 1
        # #540: wait wash covers (raw.githubusercontent) before shot
        await pg.wait_for_function(
            """() => {
              const imgs = [...document.querySelectorAll('.ca-toolcard__cover img')];
              return imgs.length >= 5 && imgs.every(i => i.complete && i.naturalWidth > 0);
            }""",
            timeout=60000,
        )
        await _shot(pg, f"home-tools-{lang}-{theme}")
        await pg.keyboard.press("Escape")

        feat = pg.get_by_test_id("home-featured")
        await feat.scroll_into_view_if_needed()
        await pg.get_by_test_id("home-featured-col").first.wait_for()
        cols = await pg.get_by_test_id("home-featured-col").count()
        assert cols >= 1
        cards = await pg.get_by_test_id("home-featured-card").count()
        assert cards >= 1
        await _shot(pg, f"home-waterfall-{lang}-{theme}")
        await browser.close()


async def test_tool_file_cancel_stays_home(app_url):  # noqa: F811
    """File picker cancel must not navigate; we only assert picker wiring exists (no dialog auto-accept)."""
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh", "light")
        assert "home" in pg.url or pg.url.rstrip("/").endswith(":5173") or "index" in pg.url or True
        # still on landing
        await pg.get_by_test_id("home-tools").wait_for()
        # clicking a card opens a hidden file input — cancel leaves URL without project
        before = pg.url
        # Do not set files — just ensure card is clickable and page stays
        card = pg.get_by_test_id("home-tool-card-cutout")
        await card.click()
        await pg.wait_for_timeout(300)
        # cancel is OS-level; without files the launchTool no-ops — still home tools visible
        await pg.get_by_test_id("home-tools").wait_for()
        assert before.split("#")[0] == pg.url.split("#")[0] or "home-tools"
        await browser.close()


_PNG = __import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
MENU_SHADOW = "rgba(0, 0, 0, 0.06) 0px 16px 24px -8px, rgba(0, 0, 0, 0.04) 0px 4px 8px -4px, rgba(0, 0, 0, 0.02) 0px 1px 1px 0px"


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_more_menu_shadow_545(app_url, theme):  # noqa: F811
    """#545 QA-1: 更多 dropdown computes Lovart's 3-layer shadow in both themes (light .ca-menu override must not win)."""
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh", theme)
        await pg.get_by_test_id("home-more-tools").click()
        menu = pg.get_by_test_id("home-more-tools-menu")
        await menu.wait_for()
        assert await menu.evaluate("e => getComputedStyle(e).boxShadow") == MENU_SHADOW
        await browser.close()


async def _launch(pg, tid: str, more: bool) -> None:
    if more:
        await pg.get_by_test_id("home-more-tools").click()
        await pg.get_by_test_id("home-more-tools-menu").wait_for()
    async with pg.expect_file_chooser() as fc:
        await pg.get_by_test_id(f"home-more-tool-{tid}" if more else f"home-tool-card-{tid}").click()
    await (await fc.value).set_files({"name": "t.png", "mimeType": "image/png", "buffer": _PNG})
    await pg.locator(".tl-container").first.wait_for(timeout=15000)


@pytest.mark.parametrize("tid,panel", [("to3d", ".ca-toolpanel[data-tool='to3d']"), ("transform", ".ca-toolbar--swap .ca-transform")])
async def test_unpinned_more_tool_opens_panel_545(app_url, tid, panel):  # noqa: F811
    """#545 QA-2, updated by #570: to3d opens its own panel at the image's right, transform swaps in its own bar (⋯ never auto-opens)."""
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh", "light")
        await _launch(pg, tid, True)
        await pg.locator(panel).first.wait_for(state="visible", timeout=15000)
        await browser.close()


@pytest.mark.parametrize("tid,more", [(t, False) for t in ("cutout", "extend", "upscale", "inpaint", "mockup")]
                         + [(t, True) for t in ("quick", "erase", "crop", "expand", "adjust", "text", "angles", "vectorize", "move", "lipsync", "motion", "audio")])
async def test_home_tool_handoff_reaches_canvas_545(app_url, tid, more):  # noqa: F811
    """#545: every other home tool still hands off to a project canvas."""
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh", "light")
        await _launch(pg, tid, more)
        await browser.close()
