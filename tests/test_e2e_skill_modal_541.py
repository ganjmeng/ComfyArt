"""#541 e2e (mock only, $0): skill modal geometry to Lovart (1112×820, 752|360, tiles 344×288, 22px zoom, 312 controls),
real meta line, zoom view, dashed upload, pinned submit gating."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_skill_cards_494 import _open

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")

BOX = "el => { const r = el.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), Math.round(r.x), Math.round(r.y)] }"


async def _modal(pg, skill):
    await pg.set_viewport_size({"width": 1440, "height": 960})
    await pg.locator(f'[data-skill="{skill}"] .ca-swall__cover').click()
    dlg = pg.get_by_test_id("skill-run-dialog")
    await dlg.wait_for()
    await pg.wait_for_timeout(300)
    return dlg


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_geometry(app_url, lang):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang)
        dlg = await _modal(pg, "poster")
        assert (await dlg.evaluate(BOX))[:2] == [1112, 820]
        assert (await dlg.locator(".ca-skillrun__left").evaluate(BOX))[0] == 752
        assert (await dlg.locator(".ca-skillrun__right").evaluate(BOX))[0] == 360
        tiles = pg.locator(".ca-skillrun__tile")
        assert await tiles.count() == 3
        assert (await tiles.first.evaluate(BOX))[:2] == [344, 288]
        assert (await pg.locator(".ca-skillrun__presetimg").first.evaluate(BOX))[:2] == [344, 258]
        a, b = await tiles.nth(0).evaluate(BOX), await tiles.nth(1).evaluate(BOX)
        assert b[2] - a[2] == 360  # 344 + gap 16
        assert (await pg.get_by_test_id("skill-run-current").locator(".ca-skillrun__currentrow").evaluate(BOX))[:2] == [312, 86]
        assert (await pg.get_by_test_id("skill-run-upload").evaluate(BOX))[:2] == [312, 108]
        go = pg.get_by_test_id("skill-run-go")
        g, r = await go.evaluate(BOX), await dlg.evaluate(BOX)
        assert g[:2] == [312, 36] and r[3] + r[1] - (g[3] + g[1]) == 24  # pinned to bottom
        meta = await pg.get_by_test_id("skill-run-meta").inner_text()
        assert meta == ("3 个模板" if lang == "zh" else "3 templates")
        bg = await dlg.locator(".ca-skillrun__right").evaluate("el => getComputedStyle(el).backgroundColor")
        assert bg == "rgb(245, 245, 245)"
        await browser.close()


async def test_zoom_select_and_gating(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh")
        await _modal(pg, "product")
        assert await pg.locator(".ca-skillrun__tile").count() == 3
        tile = pg.locator(".ca-skillrun__tile").nth(1)
        await tile.hover()
        z = tile.get_by_test_id("skill-run-zoom")
        assert (await z.evaluate(BOX))[:2] == [22, 22]
        await z.click()
        view = pg.get_by_test_id("skill-run-zoomview")
        await view.wait_for()
        await view.click()
        assert await view.count() == 0
        assert await pg.get_by_test_id("skill-run-dialog").count() == 1  # zoom close ≠ modal close
        await tile.get_by_test_id("skill-run-preset").click()
        assert await tile.get_by_test_id("skill-run-preset").get_attribute("aria-checked") == "true"
        assert await tile.locator(".ca-skillrun__check").count() == 1
        ring = await tile.get_by_test_id("skill-run-preset").evaluate(
            "el => { const a = getComputedStyle(el, '::after'); const r = el.getBoundingClientRect();"
            " return [a.boxShadow, Math.round(r.width), Math.round(r.height)] }")
        assert "1px" in ring[0] and ring[1:] == [344, 288]  # ring spans image + label

        assert await pg.get_by_test_id("skill-run-go").is_disabled()  # productImage required, empty
        await browser.close()


async def test_custom_workflow_no_meta_no_tiles(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "en")
        await _modal(pg, "custom-workflow")
        assert await pg.get_by_test_id("skill-run-meta").count() == 0
        assert await pg.locator(".ca-skillrun__tile").count() == 0
        await browser.close()
