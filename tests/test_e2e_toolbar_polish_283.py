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


SEP = """e => { const c = getComputedStyle(e), r = e.getBoundingClientRect(), p = e.parentElement.getBoundingClientRect()
  return { bg: c.backgroundColor, phys: r.width * devicePixelRatio, ml: parseFloat(c.marginLeft), mr: parseFloat(c.marginRight),
    top: r.top - p.top, bottom: p.bottom - r.bottom, h: r.height, ph: p.height } }"""
SEP_BG = {"light": "rgb(239, 239, 239)", "dark": "rgba(255, 255, 255, 0.08)"}


async def _check_seps(bar, theme, expected):
    """#283 version A: count/positions as main; 1 physical px, #EFEFEF / white 8%, near full height, ~10px each side."""
    seps = bar.locator(".ca-bar__sep")
    assert await seps.count() == expected
    for i in range(expected):
        st = await seps.nth(i).evaluate(SEP)
        assert st["bg"] == SEP_BG[theme], st
        assert abs(st["phys"] - 1) < 0.05, st  # exactly one device pixel wide
        assert 8 <= st["ml"] <= 12 and 8 <= st["mr"] <= 12, st  # ~10px left/right
        assert st["h"] >= st["ph"] - 12 and st["top"] <= 6 and st["bottom"] <= 6, st  # near full height


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("width", [1280, 360])
@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_frame_toolbar_polish(app_url, fake_tools, lang, width, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang, theme)
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
        await _check_seps(bar, theme, 2)  # frame toolbar: same count as main
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


MAKE_IMAGE = """() => {
  const ed = window.__caEditor
  const c = document.createElement('canvas'); c.width = 64; c.height = 64
  const g = c.getContext('2d'); g.fillStyle = '#c66'; g.fillRect(0, 0, 64, 64)
  const assetId = 'asset:e2e283'
  ed.createAssets([{ id: assetId, typeName: 'asset', type: 'image', meta: {},
    props: { name: 'e2e.png', src: c.toDataURL('image/png'), w: 640, h: 480, mimeType: 'image/png', isAnimated: false } }])
  ed.createShape({ type: 'image', x: 0, y: 0, props: { assetId, w: 640, h: 480 } })
  const s = ed.getCurrentPageShapes().find((s) => s.type === 'image')
  ed.select(s.id); ed.zoomToSelection()
}"""


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("width", [1280, 360])
async def test_image_toolbar_separator(app_url, fake_tools, width, theme):  # noqa: F811
    """#283 version A: the image toolbar gets its upstream 5231d59 separator back (tools | download), hairline spec."""
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, "zh", theme)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await _dismiss(pg)
        await pg.set_viewport_size({"width": width, "height": 800})
        await pg.wait_for_function("!!window.__caEditor")
        await pg.evaluate(MAKE_IMAGE)
        bar = pg.locator(".ca-toolbar--image")
        await bar.wait_for()
        await pg.wait_for_timeout(300)
        await _check_seps(bar, theme, 1)
        # the separator sits right before the last control (download)
        assert await bar.evaluate("b => { const k = [...b.children]; return k.indexOf(b.querySelector(':scope > .ca-bar__sep')) === k.length - 2 }")
        await browser.close()
