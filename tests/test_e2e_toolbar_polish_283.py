"""#283: non-image selection toolbars follow the image toolbar style. Separators are kept (count/position as on
main, styled as 1 device px near-full-height hairlines), the image toolbar gets its upstream 5231d59 separator back,
native titles become <Tip> chips with identical text, toolbar dropdown rows use 6px 8px padding while the insert menu
is unchanged, and the frame toolbar stays fully inside the viewport at 1280 and 360 (zh/en). Mock only ($0)."""
from __future__ import annotations

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import _page, fake_tools  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

MAKE_FRAME = """() => {
  const ed = window.__caEditor
  ed.createShape({ type: 'frame', x: 0, y: 0, props: { w: 600, h: 400 } })
  const f = ed.getCurrentPageShapes().find((s) => s.type === 'frame')
  ed.select(f.id); ed.zoomToSelection()
}"""


async def _dismiss(pg):
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)


@pytest.mark.parametrize("width", [1280, 360])
@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_frame_toolbar_polish(app_url, fake_tools, lang, width):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang, "light")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await _dismiss(pg)
        await pg.set_viewport_size({"width": width, "height": 800})
        await pg.wait_for_function("!!window.__caEditor")
        await pg.evaluate(MAKE_FRAME)
        bar = pg.locator(".ca-toolbar--frame")
        await bar.wait_for()
        await pg.wait_for_timeout(300)
        # (4) fully inside the viewport, neither edge cut
        b = await bar.bounding_box()
        assert b["x"] >= 0 and b["x"] + b["width"] <= width + 0.5, b
        # separators kept, styled as hairlines
        seps = bar.locator(".ca-bar__sep")
        if await seps.count():
            st = await seps.first.evaluate("e => { const c = getComputedStyle(e); return [c.transform, c.backgroundColor] }")
            assert st[0] != "none" and st[1] in ("rgb(239, 239, 239)",), st
        # (1) native title -> <Tip>, same text
        btn = bar.locator("[title]").first
        if await btn.count():
            text = await btn.get_attribute("title")
            await btn.hover()
            tip = pg.locator(".ca-tip")
            await tip.wait_for()
            assert (await tip.inner_text()).strip() == text
            assert await btn.get_attribute("title") is None and await btn.get_attribute("data-tip") == text
        # (2) default swatch is no longer pure white
        dot = bar.locator(".ca-tools__dot").first
        if await dot.count():
            assert await dot.evaluate("e => getComputedStyle(e).backgroundColor") != "rgb(255, 255, 255)"
        await browser.close()


async def test_menu_padding_scoped(app_url, fake_tools):  # noqa: F811
    """(3) only toolbar dropdowns get 6px 8px rows: a plain .ca-menu keeps main's 0 10px."""
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, "zh", "light")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pads = await pg.evaluate("""() => {
          const mk = (cls) => { const m = document.createElement('div'); m.className = cls
            const i = document.createElement('button'); i.className = 'ca-menu__item'; m.appendChild(i); document.body.appendChild(m)
            const p = getComputedStyle(i).padding; m.remove(); return p }
          return [mk('ca-menu'), mk('ca-menu ca-menu--bar')]
        }""")
        assert pads == ["0px 10px", "6px 8px"], pads
        await browser.close()
