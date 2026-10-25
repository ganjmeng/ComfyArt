"""#282: in Agent mode the ref button shows the item count at every width (only the word 参考 collapses), and
dropping items one by one into the reference area never shrinks it: each item stays inside, it grows downward
when full. Mock only, nothing paid is called ($0)."""
from __future__ import annotations

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_default_agent import _page, fake_tools  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

ADD = """([w, h]) => {
  const ed = window.__caEditor
  const frame = ed.getCurrentPageShapes().find((s) => s.type === 'frame' && s.meta.refFrame)
  // a note counts as a reference item (refFrameContents: media + non-empty ca-text)
  ed.createShape({ type: 'ca-text', parentId: frame.id, x: 40, y: 40, props: { w, h, text: 'ref ' + Date.now() } })
}"""
STATE = """() => {
  const ed = window.__caEditor
  const frame = ed.getCurrentPageShapes().find((s) => s.type === 'frame' && s.meta.refFrame)
  const fb = ed.getShapePageBounds(frame.id)
  const kids = ed.getSortedChildIdsForParent(frame.id).map((id) => ed.getShapePageBounds(id))
  return { w: frame.props.w, h: frame.props.h,
    inside: kids.every((b) => b.minX >= fb.minX - 0.5 && b.minY >= fb.minY - 0.5 && b.maxX <= fb.maxX + 0.5 && b.maxY <= fb.maxY + 0.5) }
}"""


async def _count(btn):
    c = btn.locator(".ca-refbtn__count")
    if not await c.count():
        return None
    assert await c.is_visible()
    return (await c.inner_text()).strip()


@pytest.mark.parametrize("width", [1280, 360])
async def test_ref_count_and_layout(app_url, fake_tools, width):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, "zh", "dark")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        await pg.set_viewport_size({"width": width, "height": 800})
        await pg.wait_for_function("!!window.__caEditor")
        btn = pg.locator(".ca-composer__foot .ca-refbtn")
        await btn.click()  # creates the reference area and links it
        await pg.wait_for_timeout(300)
        assert await btn.get_attribute("data-on") is not None
        assert await _count(btn) is None  # 0 items: no number
        size0 = await pg.evaluate(STATE)
        for n, (w, h) in enumerate([(300, 200), (300, 200)], start=1):
            await pg.evaluate(ADD, [w, h])
            await pg.wait_for_timeout(300)
            assert await _count(btn) == str(n)
            st = await pg.evaluate(STATE)
            assert st["w"] >= size0["w"] and st["h"] >= size0["h"], (size0, st)  # never shrinks
            assert st["inside"], st
        # fill past the original height: the frame grows downward and still holds every item
        for _ in range(6):
            await pg.evaluate(ADD, [500, 400])
        await pg.wait_for_timeout(400)
        st = await pg.evaluate(STATE)
        assert st["w"] == size0["w"] and st["h"] > size0["h"] and st["inside"], (size0, st)
        assert await _count(btn) == "8"
        await browser.close()
