"""#509 PR3: WorkflowsDialog video+3D categories (zh light) and ImageToolbar 3rd 3D item (en dark). Mocks only."""
from __future__ import annotations

from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

SHOTS = Path(__file__).resolve().parent.parent / "artifacts" / "509-3"
WF = SHOTS / "demo-3d.json"

MAKE_IMAGE = """() => {
  const ed = window.__caEditor
  const c = document.createElement('canvas'); c.width = 64; c.height = 64
  const g = c.getContext('2d'); g.fillStyle = '#6ac'; g.fillRect(0, 0, 64, 64)
  const assetId = 'asset:e5093d'
  ed.createAssets([{ id: assetId, typeName: 'asset', type: 'image', meta: {},
    props: { name: 'e2e.png', src: c.toDataURL('image/png'), w: 640, h: 480, mimeType: 'image/png', isAnimated: false } }])
  ed.createShape({ type: 'image', x: 0, y: 0, props: { assetId, w: 640, h: 480 } })
  const s = ed.getCurrentPageShapes().find((s) => s.type === 'image')
  ed.select(s.id); ed.zoomToSelection()
}"""


async def _dismiss(pg):
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)


async def test_workflows_dialog_video_3d_categories_zh_light(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','light')")
        await pg.goto(app_url + "?project=e509vid3d&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        await _dismiss(pg)
        await pg.locator(".ca-head__logo").click()
        await pg.locator(".ca-menu__item", has_text="自定义工作流").click()
        await pg.locator(".ca-modal").wait_for()
        # scroll video group into view then assert rows
        video = pg.locator(".ca-workflows__group").filter(has=pg.locator(".ca-gen__label", has_text="视频"))
        await video.wait_for()
        for label in ("视频延长", "视频放大", "视频去背景"):
            assert await video.locator(".ca-workflows__row", has_text=label).count() == 1, label
        model = pg.locator(".ca-workflows__group").filter(has=pg.locator(".ca-gen__label", has_text="3D"))
        await model.scroll_into_view_if_needed()
        assert await model.locator(".ca-workflows__row", has_text="图生 3D").count() == 1
        SHOTS.mkdir(parents=True, exist_ok=True)
        # scroll so video + 3D are both visible for the shot
        await video.scroll_into_view_if_needed()
        await pg.wait_for_timeout(200)
        # enlarge modal content scroll to show video+model: scroll the modal body
        await pg.evaluate("""() => {
          const m = document.querySelector('.ca-modal .ca-panel, .ca-modal');
          const body = m && (m.querySelector('.ca-panel__body') || m);
          if (body) {
            const g = [...document.querySelectorAll('.ca-workflows__group')].find(el => el.querySelector('.ca-gen__label')?.textContent?.trim() === '视频');
            if (g) g.scrollIntoView({block:'start'});
          }
        }""")
        await pg.wait_for_timeout(200)
        await pg.locator(".ca-modal").screenshot(path=str(SHOTS / "workflows-video-3d-zh-light.png"))
        # also a focused shot of model group after scrolling it into view
        await model.scroll_into_view_if_needed()
        await pg.wait_for_timeout(150)
        await pg.locator(".ca-modal").screenshot(path=str(SHOTS / "workflows-3d-group-zh-light.png"))
        await browser.close()


async def test_image_toolbar_custom_3d_en_dark(app_url, fake_tools, monkeypatch):  # noqa: F811
    """Assign model3d workflow then open ImageToolbar 3D menu (en dark) showing TRELLIS.2 / Pixal3D / demo-3d."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    assert WF.is_file()
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        # pin to3d on the image toolbar so the 3D menu is one click away
        await pg.add_init_script("""
          localStorage.setItem('comfyart.lang','en');
          localStorage.setItem('comfyart.theme','dark');
          localStorage.setItem('comfyart.toolbar', JSON.stringify({
            pinned: ['quick','chat','upscale','cutout','erase','to3d'],
            names: true,
            seen: ['quick','chat','upscale','cutout','erase','inpaint','expand','text','crop','style','adjust','layers','animate','angles','regenerate','remix','copyPrompt','export','effects','elements','move','mockup','to3d','transform','vectorize','ocr','smudge','preview','info']
          }));
        """)
        await pg.goto(app_url + "?project=e509tb3d&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        await _dismiss(pg)
        # open WorkflowsDialog and upload model3d
        await pg.locator(".ca-head__logo").click()
        await pg.locator(".ca-menu__item", has_text="Custom workflows").click()
        await pg.locator(".ca-modal").wait_for()
        row = pg.locator(".ca-workflows__row").filter(has=pg.locator("span", has_text="Image to 3D")).first
        await row.scroll_into_view_if_needed()
        await row.wait_for()
        async with pg.expect_file_chooser() as fc:
            await row.locator("button.ca-panel__icon").click()
        chooser = await fc.value
        await chooser.set_files(str(WF))
        await pg.wait_for_timeout(2500)
        row_text = await row.inner_text()
        assert "demo-3d" in row_text, f"model3d not assigned: {row_text!r}"
        await pg.locator(".ca-modal .ca-panel__primary").click()
        await pg.wait_for_timeout(400)
        # place image and open 3D menu
        await pg.wait_for_function("!!window.__caEditor")
        await pg.evaluate(MAKE_IMAGE)
        bar = pg.locator(".ca-toolbar--image")
        await bar.wait_for()
        btn = bar.locator(".ca-bar__btn").filter(has_text="3D")
        assert await btn.count() >= 1, "to3d not pinned on toolbar"
        await btn.first.click()
        await pg.wait_for_timeout(300)
        menu = pg.locator(".ca-menu").filter(has=pg.locator(".ca-menu__item", has_text="TRELLIS.2"))
        await menu.wait_for()
        items = await menu.locator(".ca-menu__item").all_inner_texts()
        flat = " ".join(items)
        assert "TRELLIS.2" in flat and "Pixal3D" in flat, items
        assert "demo-3d" in flat, items
        SHOTS.mkdir(parents=True, exist_ok=True)
        # capture toolbar + open menu
        await pg.locator(".ca-toolbar--image").screenshot(path=str(SHOTS / "image-toolbar-3d-en-dark-bar.png"))
        # full-ish shot of bar+menu via bounding box union
        box_bar = await bar.bounding_box()
        box_menu = await menu.bounding_box()
        if box_bar and box_menu:
            x = min(box_bar["x"], box_menu["x"]) - 8
            y = min(box_bar["y"], box_menu["y"]) - 8
            w = max(box_bar["x"] + box_bar["width"], box_menu["x"] + box_menu["width"]) - x + 8
            h = max(box_bar["y"] + box_bar["height"], box_menu["y"] + box_menu["height"]) - y + 8
            await pg.screenshot(path=str(SHOTS / "image-toolbar-3d-en-dark.png"), clip={"x": max(0, x), "y": max(0, y), "width": w, "height": h})
        else:
            await menu.screenshot(path=str(SHOTS / "image-toolbar-3d-en-dark.png"))
        await browser.close()
