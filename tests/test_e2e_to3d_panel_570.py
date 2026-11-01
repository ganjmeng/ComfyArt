"""#570 e2e (mock WaveSpeed only, $0): home → canvas lands on the tool's own panel / bar, ⋯ has one 转 3D,
the 转 3D panel renders each model's params from data, and closing a panel leaves ⋯ on its main list.
Set TO3D_570_SHOTS=/dir for 1280×800 zh-light / en-dark PNGs."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_home_tools_537 import _PNG

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("TO3D_570_SHOTS")
MORE_LABEL = {"zh": "更多", "en": "More"}

PANEL = ".ca-toolpanel"
MORE_POP = ".ca-pop .ca-menu--image"


async def _open(p, app_url, lang="zh", theme="light"):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    await pg.goto(app_url)
    await pg.get_by_test_id("home-tools").wait_for()
    return browser, pg


async def _launch(pg, tid: str, png: bytes = _PNG) -> None:
    more = tid not in ("cutout", "extend", "upscale", "inpaint", "mockup")
    if more:
        await pg.get_by_test_id("home-more-tools").click()
        await pg.get_by_test_id("home-more-tools-menu").wait_for()
    async with pg.expect_file_chooser() as fc:
        await pg.get_by_test_id(f"home-more-tool-{tid}" if more else f"home-tool-card-{tid}").click()
    await (await fc.value).set_files({"name": "t.png", "mimeType": "image/png", "buffer": png})
    await pg.locator(".tl-container").first.wait_for(timeout=15000)


async def _shot(pg, name: str) -> None:
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.locator(".tl-container").first.wait_for()
    await pg.wait_for_load_state("networkidle")
    await pg.wait_for_timeout(2500)  # let the boot splash fade before capturing
    await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=False)


async def _panel_right_of_image(pg, tool: str) -> None:
    panel = pg.locator(f"{PANEL}[data-tool='{tool}']")
    await panel.wait_for(state="visible", timeout=15000)
    assert await pg.locator(MORE_POP).count() == 0, "⋯ must not auto-open"
    bar = await pg.locator(".ca-toolbar--image").bounding_box()
    box = await panel.bounding_box()
    assert box and bar and box["width"] == pytest.approx(172, abs=2)
    if tool == "to3d":  # design 6551032261: to3d is ~172×346; upscale follows its content (review 5725811299)
        assert box["height"] >= 340
    sel = await pg.evaluate("() => { const e = window.__caEditor; const b = e.getSelectionScreenBounds(); return b && { r: b.maxX } }")
    if sel:
        assert box["x"] >= sel["r"] - 2  # at the image's right


def _spec_param_counts() -> dict[str, int]:
    """Param count per built-in model, read from MODEL3D_SPECS (the data the panel renders)."""
    import re
    src = (ROOT / "src/assetGen.ts").read_text(encoding="utf-8")
    block = src[src.index("export const MODEL3D_SPECS"):]
    block = block[: block.index("\n]\n")]
    out = {}
    for m in re.finditer(r"\{ id: '(\w+)', label: '[^']+', params: \[(.*?)\] \}", block, re.S):
        out[m.group(1)] = len(re.findall(r"key:", m.group(2)))
    assert set(out) == {"trellis2", "pixal3d"}, out
    return out


async def _open_more(pg, lang="zh"):
    await pg.locator(".ca-toolbar--image").get_by_role("button", name=MORE_LABEL[lang]).click()
    await pg.locator(MORE_POP).wait_for()


async def test_a_home_to3d_opens_panel_not_more(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, "to3d")
        await _panel_right_of_image(pg, "to3d")
        await browser.close()


async def test_b_home_upscale_opens_its_panel(app_url, mock_ws):  # noqa: F811
    """Acceptance 6550945029 + design 6551032261: home → upscale opens its own panel at the image's right
    (title, segmented mode + resolution, 取消 / 立即使用; review 5725811299) — not the toolbar dropdown, never ⋯."""
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, "upscale")
        panel = pg.locator(f"{PANEL}[data-tool='upscale']")
        await panel.wait_for(timeout=15000)
        assert await pg.locator(".ca-pop .ca-upscale").count() == 0 and await pg.locator(MORE_POP).count() == 0
        await _panel_right_of_image(pg, "upscale")
        # no native <select>; mode and resolution reuse the to3d segmented switch
        assert await panel.locator("select").count() == 0
        assert await panel.locator(".ca-panel__chip").count() == 0
        assert await panel.locator(".ca-seg [data-mode]").count() == 2
        assert await panel.locator(".ca-seg [data-res]").all_inner_texts() == ["2K", "4K", "8K"]
        await panel.locator(".ca-seg [data-mode='detail']").click()
        assert await panel.locator(".ca-seg [data-mode='detail']").get_attribute("aria-selected") == "true"
        await panel.locator(".ca-seg [data-mode='faithful']").click()
        res = panel.locator(".ca-seg [data-res]:not([disabled])").last
        await res.click()
        assert await res.get_attribute("aria-selected") == "true"
        # height follows content: no fixed 346 and no big gap between controls and the footer
        box = await panel.bounding_box()
        assert box["height"] <= 160, box  # head + mode + resolution + footer, no filler
        gap = await panel.evaluate("""e => e.querySelector('.ca-toolpanel__foot').getBoundingClientRect().top
            - [...e.querySelector('.ca-toolpanel__body').children].reduce((m, c) => Math.max(m, c.getBoundingClientRect().bottom), 0)""")
        assert gap <= 16, gap
        before = len(mock_ws["submits"])
        await panel.get_by_role("button", name="立即使用").click()
        for _ in range(50):
            if len(mock_ws["submits"]) > before:
                break
            await asyncio.sleep(0.2)
        assert len(mock_ws["submits"]) > before and await panel.count() == 0
        await browser.close()


async def test_c2_more_transform_swaps_bar(app_url):  # noqa: F811
    """⋯ → 更多工具 → 翻转与旋转 swaps the image toolbar for the flip/rotate bar; ⋯ never stays on .ca-transform."""
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, "cutout")
        await pg.locator(".ca-toolbar--image").wait_for(timeout=15000)
        await _open_more(pg)
        await pg.locator(".ca-menu__sub").hover()
        await pg.locator(".ca-menu__flyout").get_by_text("翻转与旋转", exact=True).click()
        await pg.locator(".ca-toolbar--swap[data-tool='transform'] .ca-transform").wait_for()
        assert await pg.locator(".ca-pop .ca-transform").count() == 0 and await pg.locator(MORE_POP).count() == 0
        await pg.locator(".ca-toolbar--swap").get_by_role("button", name="完成").click()
        await pg.locator(".ca-toolbar--image:not(.ca-toolbar--swap)").wait_for()
        await browser.close()


async def test_c_home_transform_swaps_bar(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, "transform")
        await pg.locator(".ca-toolbar--swap[data-tool='transform'] .ca-transform").wait_for(timeout=15000)
        assert await pg.locator(PANEL).count() == 0 and await pg.locator(MORE_POP).count() == 0
        bar = pg.locator(".ca-toolbar--swap[data-tool='transform'] .ca-transform")
        # design order with counter-clockwise rotate restored (reused main control): angle, ccw, cw, flipH, flipV
        kids = await bar.evaluate("e => [...e.children].map(c => c.tagName === 'LABEL' ? 'angle' : c.getAttribute('title'))")
        assert kids == ["angle", "向左旋转 90°", "旋转 90°", "水平翻转", "垂直翻转"]
        ccw = bar.get_by_title("向左旋转 90°")
        assert await ccw.count() == 1
        inp = bar.locator(".ca-crop__input")
        start = int(await inp.input_value())
        await ccw.click()
        await pg.wait_for_function("([s]) => { const v = Number(document.querySelector('.ca-toolbar--swap .ca-crop__input').value); return v !== s }", arg=[start])
        assert (int(await inp.input_value()) - start) % 360 == 270
        await browser.close()


async def test_d_home_cutout_unchanged(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, "cutout")
        await pg.locator(".ca-toolbar--image").wait_for(timeout=15000)
        await pg.wait_for_timeout(500)
        assert await pg.locator(PANEL).count() == 0 and await pg.locator(MORE_POP).count() == 0
        assert await pg.locator(".ca-toolbar--swap").count() == 0
        await browser.close()


async def test_e_more_has_one_to3d_click_opens_panel(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, "cutout")
        await pg.locator(".ca-toolbar--image").wait_for(timeout=15000)
        await _open_more(pg)
        await pg.locator(".ca-menu__sub").hover()  # existing submenu expands right on hover
        fly = pg.locator(".ca-menu__flyout")
        await fly.wait_for()
        sub, fb = await pg.locator(".ca-menu__sub").bounding_box(), await fly.bounding_box()
        assert fb["x"] >= sub["x"] + sub["width"] - 2
        pop = pg.locator(".ca-pop")
        assert await pop.get_by_text("转 3D", exact=True).count() == 1
        assert await pop.get_by_text("TRELLIS.2").count() == 0 and await pop.get_by_text("Pixal3D").count() == 0
        await pop.get_by_text("转 3D", exact=True).click()
        await pg.locator(f"{PANEL}[data-tool='to3d']").wait_for()
        assert await pg.locator(MORE_POP).count() == 0
        await browser.close()


async def test_f_switch_renders_params_from_data_and_runs_mock(app_url, mock_ws):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, "to3d")
        panel = pg.locator(f"{PANEL}[data-tool='to3d']")
        await panel.wait_for()
        expected = _spec_param_counts()
        for mid, n in expected.items():
            await panel.locator(f".ca-seg__btn[data-model='{mid}']").click()
            assert await panel.locator(f".ca-seg__btn[data-model='{mid}']").get_attribute("aria-selected") == "true"
            if n:
                assert await panel.locator(".ca-toolpanel__params").get_attribute("data-count") == str(n)
                assert await panel.locator(".ca-toolpanel__params [data-param]").count() == n
            else:  # no params in the model's data: no section and no "no params" note
                assert await panel.locator(".ca-toolpanel__params").count() == 0
                assert await panel.locator(".ca-toolpanel__empty").count() == 0
                for note in ("没有可调参数", "no adjustable parameters"):
                    assert await panel.get_by_text(note).count() == 0
        for mid in ("trellis2", "pixal3d"):
            before = len(mock_ws["submits"])
            await pg.locator(".tl-container").first.wait_for()
            if not await panel.count():  # the run selects its 3D result; hand off the image again from home
                await pg.goto(app_url)
                await pg.get_by_test_id("home-tools").wait_for()
                await _launch(pg, "to3d")
                await panel.wait_for()
            await panel.locator(f".ca-seg__btn[data-model='{mid}']").click()
            await panel.get_by_role("button", name="立即使用").click()
            for _ in range(50):
                if len(mock_ws["submits"]) > before:
                    break
                await asyncio.sleep(0.2)
            assert len(mock_ws["submits"]) > before, f"{mid}: no mock submit"
            assert "3d" in mock_ws["submits"][-1][0], mock_ws["submits"][-1]  # same WaveSpeed image-to-3D call as before
            # reselect the source image for the next run
            await pg.evaluate("() => { const e = window.__caEditor; const s = e.getCurrentPageShapes().find((s) => s.type === 'image'); e.select(s.id) }")
        await browser.close()


@pytest.mark.parametrize("tool", ["to3d", "upscale"])
async def test_g_i_close_panel_then_more_opens_main_list(app_url, tool):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, tool)
        panel = pg.locator(f"{PANEL}[data-tool='{tool}']")
        await panel.wait_for()
        await panel.get_by_role("button", name="取消").click()
        assert await pg.locator(PANEL).count() == 0
        await _open_more(pg)
        assert await pg.locator(".ca-pop .ca-menu__sub").count() == 1  # main list, not a subview
        assert await pg.locator(".ca-pop .ca-upscale, .ca-pop .ca-seg").count() == 0
        await browser.close()


@pytest.mark.parametrize("first,ready", [("upscale", f"{PANEL}[data-tool='upscale']"), ("transform", ".ca-toolbar--swap")])
async def test_h_two_handoffs_do_not_leak(app_url, first, ready):  # noqa: F811
    """QA (h): home → upscale/transform, then a new home → to3d handoff: only the to3d panel, fresh state."""
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, first)
        await pg.locator(ready).wait_for(timeout=15000)
        await pg.goto(app_url)
        await pg.get_by_test_id("home-tools").wait_for()
        await _launch(pg, "to3d")
        assert await pg.locator(".ca-pop .ca-upscale").count() == 0
        panel = pg.locator(f"{PANEL}[data-tool='to3d']")
        await panel.wait_for()
        await pg.wait_for_timeout(400)
        assert await pg.locator(PANEL).count() == 1
        assert await pg.locator(".ca-toolbar--swap").count() == 0
        assert await panel.locator(".ca-seg__btn[data-model='trellis2']").get_attribute("aria-selected") == "true"
        assert await pg.locator(MORE_POP).count() == 0
        await browser.close()


async def test_h2_second_image_in_same_canvas_resets_panel(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url)
        await _launch(pg, "to3d")
        panel = pg.locator(f"{PANEL}[data-tool='to3d']")
        await panel.wait_for()
        await panel.locator(".ca-seg__btn[data-model='pixal3d']").click()
        await pg.evaluate("""() => { const e = window.__caEditor
          const a = e.getAssets().find((a) => a.type === 'image')
          e.createShape({ type: 'image', x: 2000, y: 0, props: { assetId: a.id, w: 64, h: 64 } })
          const s = e.getCurrentPageShapes().filter((s) => s.type === 'image').pop(); e.select(s.id) }""")
        await pg.wait_for_timeout(300)
        assert await pg.locator(PANEL).count() == 0
        await browser.close()


def _shot_png() -> bytes:
    """512×512 beige with a blue square, same subject as the 570/main/ shots."""
    import io
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (512, 512), (230, 222, 206))
    ImageDraw.Draw(im).rectangle([128, 160, 320, 352], fill=(80, 130, 200))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.skipif(not SHOTS, reason="screenshots only with TO3D_570_SHOTS")
@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_shots_570(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        for tool, sel in (("to3d", f"{PANEL}[data-tool='to3d']"), ("upscale", f"{PANEL}[data-tool='upscale']"), ("transform", ".ca-toolbar--swap")):
            browser, pg = await _open(p, app_url, lang, theme)
            await _launch(pg, tool, _shot_png())
            await pg.locator(sel).wait_for()
            await _shot(pg, f"home-{tool}-{lang}-{theme}")
            if tool == "to3d":
                for mid in ("trellis2", "pixal3d"):
                    await pg.locator(f".ca-seg__btn[data-model='{mid}']").click()
                    await _shot(pg, f"to3d-panel-{mid}-{lang}-{theme}")
                await pg.locator(PANEL).get_by_role("button", name="取消" if lang == "zh" else "Cancel").click()
                await _open_more(pg, lang)
                await _shot(pg, f"more-menu-{lang}-{theme}")
                await pg.locator(".ca-menu__sub").hover()
                await pg.locator(".ca-menu__flyout").wait_for()
                await _shot(pg, f"more-tools-{lang}-{theme}")
            await browser.close()
