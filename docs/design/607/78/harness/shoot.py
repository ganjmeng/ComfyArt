"""#607 #78 AFTER tip-pin — zh-light live dist @1280×800 (mock $0).

Prefer:
  DESIGN_607_78_SHOOT=1 PYTHONPATH=.. pytest -q tests/test_design_607_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-rail-default-expanded-zh-light.png",
    "AFTER-rail-collapsed-no-recent-zh-light.png",
]


def _snap(name: str) -> dict:
    return {
        "document": {
            "store": {"document:document": {"id": "document:document", "typeName": "document", "name": name}},
            "schema": {},
        },
        "session": {},
    }


async def _seed(pg, names: list[str]) -> None:
    for i, name in enumerate(names):
        pid = f"s607{i:02d}"
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


NAMES = ["置顶示例", "品牌视觉提案", "电商主图改版", "海报草稿 A"]


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # Cold start: do NOT seed rail.collapsed → #607 default expanded
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        pg = await ctx.new_page()
        await pg.add_init_script(
            "localStorage.setItem('comfyart.lang','zh');"
            "localStorage.setItem('comfyart.theme','light');"
            "localStorage.removeItem('comfyart.rail.collapsed');"
        )
        await pg.goto(app_url)
        await pg.get_by_test_id("account-rail").wait_for()
        await _seed(pg, NAMES)
        await pg.reload()
        rail = pg.get_by_test_id("account-rail")
        await pg.get_by_test_id("rail-recent").wait_for()
        assert await rail.get_attribute("data-expanded") == "true"
        assert (await rail.bounding_box())["width"] == 240
        await pg.wait_for_timeout(600)
        path0 = OUT / SHOTS[0]
        await pg.screenshot(path=str(path0))
        print("wrote", path0)

        await pg.get_by_test_id("rail-collapse").click()
        await pg.get_by_test_id("rail-expand").wait_for()
        assert await pg.get_by_test_id("rail-recent").count() == 0
        assert (await rail.bounding_box())["width"] == 60
        await pg.wait_for_timeout(400)
        path1 = OUT / SHOTS[1]
        await pg.screenshot(path=str(path1))
        print("wrote", path1)
        await browser.close()
