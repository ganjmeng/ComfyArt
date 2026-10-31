"""#495 sidebar e2e: expanded ~160 + labels + recent (max 8) + collapse persist. Mock only, $0."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("SIDEBAR_495_SHOTS")


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
        pid = f"s495{i:02d}"
        status = await pg.evaluate(
            """async ({pid, name, snap, pinned}) => {
              const r = await fetch(`/comfyart/projects/${pid}`, {
                method: 'PUT', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({snapshot: snap, name, covers: []}),
              });
              if (!r.ok) return r.status;
              if (pinned) {
                const p = await fetch(`/comfyart/projects/${pid}`, {
                  method: 'PATCH', headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({pinned: true}),
                });
                return p.status;
              }
              return r.status;
            }""",
            {"pid": pid, "name": name, "snap": _snap(name), "pinned": i == 0},
        )
        assert status == 200, (pid, status)


async def _open(p, app_url, lang, theme, *, collapsed=False):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"""localStorage.setItem('comfyart.lang','{lang}');
            localStorage.setItem('comfyart.theme','{theme}');
            localStorage.setItem('comfyart.rail.collapsed','{"1" if collapsed else "0"}');"""
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("account-rail").wait_for()
    await pg.get_by_test_id("rail-home").wait_for()
    return browser, pg


async def _shot(pg, name: str) -> None:
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(500)
    await pg.screenshot(path=f"{SHOTS}/{name}.png")


NAMES = [
    "置顶示例",
    "Untitled",
    "品牌视觉提案",
    "电商主图改版",
    "用户搜索数据可视化",
    "海报草稿 A",
    "社交媒体套图",
    "包装结构探索",
    "第九个应被截断",
]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_sidebar_expanded_labels_recent(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme, collapsed=False)
        await _seed(pg, NAMES)
        await pg.reload()
        await pg.get_by_test_id("rail-recent").wait_for()
        rail = pg.get_by_test_id("account-rail")
        assert await rail.get_attribute("data-expanded") == "true"
        box = await rail.bounding_box()
        assert box and box["width"] == 240  # #546 Lovart
        # labels visible when expanded
        home = pg.get_by_test_id("rail-home")
        assert await home.locator(".ca-rail__label").inner_text() != ""
        # Assets gated; competitor slots absent
        assert await pg.get_by_test_id("rail-assets").count() == 0
        assert await pg.get_by_test_id("rail-schedules").count() == 1
        assert await pg.get_by_test_id("rail-ws-history").count() == 1
        assert await pg.get_by_test_id("rail-settings").count() == 1
        rows = pg.get_by_test_id("rail-recent-row")
        assert await rows.count() == 8
        # ⋯ menu has 4 items
        await rows.first.hover()
        await pg.get_by_test_id("rail-recent-more").first.click()
        menu = pg.get_by_test_id("rail-recent-menu")
        await menu.wait_for()
        assert await menu.locator(".ca-menu__item").count() == 4
        await pg.keyboard.press("Escape")
        await _shot(pg, f"sidebar-expanded-{lang}-{theme}")
        # collapse → icon rail, no recent
        await pg.get_by_test_id("rail-collapse").click()
        assert await rail.get_attribute("data-collapsed") == "true"
        assert await pg.get_by_test_id("rail-recent").count() == 0
        box2 = await rail.bounding_box()
        assert box2 and box2["width"] <= 70
        assert await pg.evaluate("() => localStorage.getItem('comfyart.rail.collapsed')") == "1"
        await _shot(pg, f"sidebar-collapsed-{lang}-{theme}")
        # expand via logo
        await pg.get_by_test_id("rail-expand").click()
        await pg.get_by_test_id("rail-recent").wait_for()
        assert await pg.evaluate("() => localStorage.getItem('comfyart.rail.collapsed')") == "0"
        await browser.close()


async def test_sidebar_empty_hides_recent(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh", "light", collapsed=False)
        await pg.get_by_test_id("rail-home").wait_for()
        assert await pg.get_by_test_id("rail-recent").count() == 0
        await browser.close()
