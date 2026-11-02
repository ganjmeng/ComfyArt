"""#595 #78 AFTER tip-pin — zh-light live dist screenshots via ComfyArt app_url (mock $0).

Run from repo root:
  PYTHONPATH=.. pytest -q docs/design/595/78/harness/shoot.py -s
Or:
  PYTHONPATH=.. python3 docs/design/595/78/harness/shoot.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "left-ours"
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT.parent))
os.chdir(ROOT)

# Re-use e2e fixtures by invoking pytest when run as __main__
SHOTS = [
    "AFTER-home-quickstart-order-zh-light.png",
    "AFTER-home-chip-website-zh-light.png",
    "AFTER-skills-explore-website-chip-zh-light.png",
    "AFTER-home-featured-waterfall-zh-light.png",
    "AFTER-skill-modal-brand-dualcol-zh-light.png",
    "AFTER-skill-modal-multi-angle-dualcol-zh-light.png",
]


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        pg = await ctx.new_page()
        await pg.add_init_script(
            "localStorage.setItem('comfyart.lang','zh');"
            "localStorage.setItem('comfyart.theme','light');"
            "localStorage.setItem('comfyart.rail.collapsed','0');"
        )
        await pg.goto(app_url)
        await pg.get_by_test_id("home-start-skill").wait_for()
        # Wait covers to settle
        await pg.get_by_test_id("home-skill-card").first.wait_for()
        await pg.wait_for_timeout(800)

        # 1) Home quick-start first 6 order
        qs = pg.get_by_test_id("home-start-skill")
        await qs.scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        await qs.screenshot(path=str(OUT / SHOTS[0]))
        print("wrote", OUT / SHOTS[0])

        # 2) website chip lit on home chips — click then shoot chips + filtered grid
        await pg.get_by_test_id("home-chip-website").click()
        await pg.wait_for_timeout(400)
        # shoot chips row + skill grid area
        box = await pg.get_by_test_id("home-chips").bounding_box()
        grid = await pg.get_by_test_id("home-skill-grid").bounding_box()
        # full viewport crop covering chips through skill grid
        await pg.screenshot(
            path=str(OUT / SHOTS[1]),
            clip={
                "x": 0,
                "y": max(0, (box or {"y": 0})["y"] - 8),
                "width": 1280,
                "height": min(800, ((grid or {"y": 400, "height": 200})["y"] + (grid or {"height": 200})["height"] + 24) - max(0, (box or {"y": 0})["y"] - 8)),
            },
        )
        print("wrote", OUT / SHOTS[1])

        # 3) Skills Explore website chip
        await pg.goto(app_url + "?view=skills")
        await pg.get_by_test_id("skills-wall-card").first.wait_for()
        await pg.get_by_test_id("skills-chip-website").wait_for()
        await pg.wait_for_timeout(600)
        # chip lit
        await pg.get_by_test_id("skills-chip-website").click()
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=str(OUT / SHOTS[2]))
        print("wrote", OUT / SHOTS[2])

        # 4) Explore featured waterfall (forYou) — back home, forYou, scroll featured
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured").wait_for()
        await pg.get_by_test_id("home-chip-forYou").click()
        await pg.wait_for_timeout(200)
        feat = pg.get_by_test_id("home-featured")
        await feat.scroll_into_view_if_needed()
        # wait at least one featured image
        await pg.wait_for_function(
            "()=>{const i=document.querySelector('[data-testid=home-featured-card] img');return i&&i.complete&&i.naturalWidth>0}",
            timeout=30000,
        )
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=str(OUT / SHOTS[3]))
        print("wrote", OUT / SHOTS[3])

        # 5) dual-col modal — brand
        await pg.get_by_test_id("home-start-skill").scroll_into_view_if_needed()
        await pg.locator('[data-testid="home-skill-card"][data-skill="brand"]').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        await pg.wait_for_timeout(800)
        await dlg.screenshot(path=str(OUT / SHOTS[4]))
        print("wrote", OUT / SHOTS[4])
        await pg.keyboard.press("Escape")
        await dlg.wait_for(state="hidden")

        # 6) dual-col modal — multi-angle
        await pg.locator('[data-testid="home-skill-card"][data-skill="multi-angle"]').click()
        await dlg.wait_for()
        await pg.get_by_test_id("skill-run-examples").wait_for()
        await pg.wait_for_timeout(800)
        await dlg.screenshot(path=str(OUT / SHOTS[5]))
        print("wrote", OUT / SHOTS[5])

        await browser.close()


def test_595_78_after_shots(app_url):  # noqa: F811 — fixture from test_e2e_comment_edit via conftest path
    """pytest entry: needs tests/ on path and built dist/."""
    import asyncio
    # Import fixtures by having pytest collect this under PYTHONPATH with tests conftest.
    # When collected via `pytest docs/design/.../shoot.py`, conftest may not load.
    # Prefer running via tests/test_design_595_78_shots.py wrapper.
    asyncio.get_event_loop().run_until_complete(capture(app_url))


if __name__ == "__main__":
    print("Use: PYTHONPATH=.. pytest -q tests/test_design_595_78_shots.py -s", file=sys.stderr)
    sys.exit(2)
