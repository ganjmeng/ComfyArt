"""#608 #78 AFTER tip-pin — Lucide icons zh-light live dist @1280×800 (mock $0).

Prefer:
  DESIGN_608_78_SHOOT=1 PYTHONPATH=.. pytest -q tests/test_design_608_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-sidebar-expanded-icons-zh-light.png",
    "AFTER-tools-strip-zh-light.png",
    "AFTER-canvas-toolbar-zh-light.png",
]


def _snap(name: str) -> dict:
    return {
        "document": {
            "store": {"document:document": {"id": "document:document", "typeName": "document", "name": name}},
            "schema": {},
        },
        "session": {},
    }


async def _seed_project(pg, pid: str, name: str) -> None:
    status = await pg.evaluate(
        """async ({pid, name, snap}) => {
          const r = await fetch(`/comfyart/projects/${pid}`, {
            method: 'PUT', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({snapshot: snap, name, covers: []}),
          });
          return r.status;
        }""",
        {"pid": pid, "name": name, "snap": _snap(name)},
    )
    assert status == 200, (pid, status)


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
            "localStorage.removeItem('comfyart.rail.collapsed');"
        )
        await pg.goto(app_url)
        await pg.get_by_test_id("account-rail").wait_for()
        # Seed a few projects so expanded rail shows recent + icons
        for i, name in enumerate(["图标预览 A", "图标预览 B", "图标预览 C"]):
            await _seed_project(pg, f"s608{i:02d}", name)
        await pg.reload()
        rail = pg.get_by_test_id("account-rail")
        await rail.wait_for()
        # ensure expanded
        if await rail.get_attribute("data-expanded") != "true":
            expand = pg.get_by_test_id("rail-expand")
            if await expand.count():
                await expand.click()
        await pg.wait_for_timeout(500)
        # 1) sidebar expanded icons
        path0 = OUT / SHOTS[0]
        await rail.screenshot(path=str(path0))
        print("wrote", path0)

        # 2) home utility tools strip
        tools = pg.get_by_test_id("home-tools")
        await tools.scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        path1 = OUT / SHOTS[1]
        await tools.screenshot(path=str(path1))
        print("wrote", path1)

        # 3) canvas: new project → Dock + CanvasTools
        await pg.get_by_test_id("rail-new").click()
        await pg.locator(".tl-canvas").wait_for(timeout=30000)
        await pg.wait_for_timeout(800)
        # dismiss possible first-run modal
        if await pg.locator(".ca-modal").count():
            await pg.locator(".ca-modal button").last.click()
            await pg.wait_for_timeout(300)
        dock = pg.locator(".ca-dock")
        tools_bar = pg.locator(".ca-tools")
        await dock.first.wait_for(timeout=30000)
        await tools_bar.first.wait_for(timeout=15000)
        await pg.wait_for_timeout(400)
        path2 = OUT / SHOTS[2]
        await pg.screenshot(path=str(path2))
        print("wrote", path2)
        await browser.close()
