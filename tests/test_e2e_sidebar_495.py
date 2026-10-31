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
        # #539 PR-A: Assets entry now shown (was gated); competitor slots absent
        assert await pg.get_by_test_id("rail-assets").count() == 1
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


ASSET_SHOTS = os.environ.get("ASSETS_539_SHOTS")


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_assets_page_shell_539(app_url, lang, theme):  # noqa: F811
    """#539 PR-A: rail → Assets page; 4 kit tabs (no 文件); empty state; no demo data."""
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        pg = await ctx.new_page()
        await pg.add_init_script(
            f"""localStorage.setItem('comfyart.lang','{lang}');
                localStorage.setItem('comfyart.theme','{theme}');
                localStorage.setItem('comfyart.rail.collapsed','1');"""
        )
        await pg.goto(app_url)
        await pg.get_by_test_id("rail-assets").wait_for()
        if ASSET_SHOTS:
            Path(ASSET_SHOTS).mkdir(parents=True, exist_ok=True)
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539a-entry-{lang}-{theme}.png")
        await pg.get_by_test_id("rail-assets").click()
        await pg.get_by_test_id("assets-page").wait_for()
        assert "view=assets" in pg.url
        assert await pg.get_by_test_id("rail-assets").get_attribute("data-on") == "true"
        tabs = pg.get_by_test_id("assets-library").get_by_role("tab")
        assert await tabs.count() == 4
        want = ["品牌套件", "角色", "产品", "自定义"] if lang == "zh" else None
        names = [await tabs.nth(i).inner_text() for i in range(4)]
        if want:
            assert names == want, names
        assert "文件" not in names and "Files" not in names
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        # no demo data: fresh library → zero cards in every tab
        for i in range(4):
            await tabs.nth(i).click()
            assert await pg.locator(".ca-lib__card").count() == 0
            # #539 PR-B: assertion updated (not removed) — kitsOnly list keeps only 新建; the hint
            # moved to the right-pane empty state (one line + 新建, no icon, no auto-created kit).
            assert await pg.locator(".ca-side__empty").count() == 0
            await pg.get_by_test_id("assets-detail-empty").wait_for()
            assert await pg.get_by_test_id("assets-empty-new").count() == 1
            assert await pg.locator(".ca-assets-page__right .ca-icon").count() == 0
        await tabs.nth(0).click()
        if ASSET_SHOTS:
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539a-empty-{lang}-{theme}.png")
        await browser.close()


async def _assets_page(p, lang, theme):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"""localStorage.setItem('comfyart.lang','{lang}');
            localStorage.setItem('comfyart.theme','{theme}');
            localStorage.setItem('comfyart.rail.collapsed','1');"""
    )
    return browser, pg


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_assets_detail_539b(app_url, lang, theme):  # noqa: F811
    """#539 PR-B: list 380 / dashed 新建; empty state; create → default-select → rename → reload persists."""
    async with pw.async_playwright() as p:
        browser, pg = await _assets_page(p, lang, theme)
        await pg.goto(app_url + "?view=assets")
        await pg.get_by_test_id("assets-page").wait_for()
        left = await pg.locator(".ca-assets-page__left").bounding_box()
        assert round(left["width"]) == 380, left
        new = pg.get_by_test_id("assets-new")
        assert await new.evaluate("e => getComputedStyle(e).borderTopStyle") == "dashed"
        assert await pg.locator(".ca-assets-page__title").evaluate("e => getComputedStyle(e).fontSize") == "18px"
        # empty: no auto-created kit
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        await pg.wait_for_timeout(600)
        assert await pg.locator(".ca-lib__card").count() == 0
        if ASSET_SHOTS:
            await pg.screenshot(path=f"{ASSET_SHOTS}/539b-empty-{lang}-{theme}.png")
        # create via the empty-state 新建 (same action as list 新建) → selected in detail
        await pg.get_by_test_id("assets-empty-new").click()
        await pg.get_by_test_id("assets-detail").wait_for()
        assert await pg.locator(".ca-lib__card").count() == 1
        page = await pg.locator(".ca-kit[data-embedded] .ca-kit__page").bounding_box()
        assert round(page["width"]) == 800, page
        foot = await pg.get_by_test_id("assets-detail-foot").bounding_box()
        detail = await pg.locator(".ca-assets-page__detail").bounding_box()
        assert round(foot["width"]) == round(detail["width"])
        cta = pg.get_by_test_id("assets-create-project")
        assert await cta.get_attribute("aria-disabled") == "true"
        await pg.get_by_test_id("assets-import-url").wait_for()
        name = "Acme 品牌" if lang == "zh" else "Acme Brand"
        await pg.get_by_test_id("assets-detail-name").fill(name)
        await pg.get_by_test_id("assets-detail-name").press("Enter")
        await pg.wait_for_timeout(800)
        # CTA not wired: stays on the Assets page
        await cta.click(force=True)
        await pg.wait_for_timeout(300)
        assert "view=assets" in pg.url
        # reload → persisted + default-selected first kit
        await pg.reload()
        await pg.get_by_test_id("assets-detail").wait_for()
        assert await pg.get_by_test_id("assets-detail-name").input_value() == name
        assert await pg.locator(".ca-lib__card[data-on]").count() == 1
        if ASSET_SHOTS:
            await pg.mouse.move(0, 0)
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539b-selected-{lang}-{theme}.png")
        # other tab with no kits → empty state; back → selected again
        tabs = pg.get_by_test_id("assets-library").get_by_role("tab")
        await tabs.nth(1).click()
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        await tabs.nth(0).click()
        await pg.get_by_test_id("assets-detail").wait_for()
        # delete via 「…」 → empty, persisted after reload
        await pg.get_by_test_id("assets-detail-more").click()
        await pg.locator(".ca-lib__menu .ca-menu__item--danger").click()
        await pg.locator(".ca-confirm .ca-panel__primary").click()
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        await pg.wait_for_timeout(500)
        await pg.reload()
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        assert await pg.locator(".ca-lib__card").count() == 0
        await browser.close()


async def test_canvas_library_unchanged_539b(app_url):  # noqa: F811
    """#539 PR-B no-regression: canvas LibraryPanel keeps 5 tabs (incl. 文件) + solid 新建; KitEditor stays the overlay."""
    async with pw.async_playwright() as p:
        browser, pg = await _assets_page(p, "zh", "light")
        await pg.goto(app_url)
        await pg.get_by_test_id("rail-new").click()
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(1500)
        if await pg.locator(".ca-modal").count():
            await pg.locator(".ca-modal button").nth(-2).click()
        await pg.locator('button[title="我的素材"]').first.click()
        lib = pg.locator(".ca-lib").first
        await lib.wait_for()
        assert await pg.get_by_test_id("assets-library").count() == 0
        tabs = lib.get_by_role("tab")
        assert await tabs.count() == 5
        assert "文件" in [await tabs.nth(i).inner_text() for i in range(5)]
        await tabs.nth(1).click()
        new = lib.locator(".ca-lib__new")
        assert await new.evaluate("e => getComputedStyle(e).borderTopStyle") == "solid"
        assert await lib.locator(".ca-side__empty").count() == 1
        await new.click()
        kit = pg.locator(".ca-kit")
        await kit.wait_for()
        assert await kit.get_attribute("data-embedded") is None
        assert await kit.evaluate("e => getComputedStyle(e).position") == "fixed"
        assert await pg.locator(".ca-kit__bar").count() == 1
        if ASSET_SHOTS:
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539b-canvas-kiteditor-zh-light.png")
        await pg.locator(".ca-kit__title").focus()
        await pg.keyboard.press("Escape")  # canvas overlay still closes on Escape
        await pg.wait_for_timeout(300)
        assert await pg.locator(".ca-kit").count() == 0
        assert await lib.locator(".ca-lib__card").count() == 1
        if ASSET_SHOTS:
            await pg.screenshot(path=f"{ASSET_SHOTS}/539b-canvas-library-zh-light.png")
        await browser.close()
