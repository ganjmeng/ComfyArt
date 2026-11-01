"""#509 PR3: WorkflowsDialog video+3D (zh light, assigned filename) + ImageToolbar 3D full window (en dark). Mocks only."""
from __future__ import annotations

from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

SHOTS = Path(__file__).resolve().parent.parent / "artifacts" / "509-3"
WF_3D = SHOTS / "demo-3d.json"
WF_EXT = SHOTS / "extend-demo.json"

MAKE_IMAGE = """() => {
  const ed = window.__caEditor
  const c = document.createElement('canvas'); c.width = 64; c.height = 64
  const g = c.getContext('2d'); g.fillStyle = '#6ac'; g.fillRect(0, 0, 64, 64)
  const assetId = 'asset:e5093d'
  ed.createAssets([{ id: assetId, typeName: 'asset', type: 'image', meta: {},
    props: { name: 'e2e.png', src: c.toDataURL('image/png'), w: 640, h: 480, mimeType: 'image/png', isAnimated: false } }])
  ed.createShape({ type: 'image', x: 80, y: 120, props: { assetId, w: 640, h: 480 } })
  const s = ed.getCurrentPageShapes().find((s) => s.type === 'image')
  ed.select(s.id); ed.zoomToSelection()
}"""


async def _dismiss(pg):
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(300)


async def test_workflows_dialog_video_assigned_filename_zh_light(app_url, fake_tools, monkeypatch):  # noqa: F811
    """Design HOLD: assigned video custom must show workflow filename in dropdown (like #525 speech-demo)."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    assert WF_EXT.is_file()
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh');localStorage.setItem('comfyart.theme','light')")
        await pg.goto(app_url + "?project=e509vidAssign&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        await _dismiss(pg)
        await pg.locator(".ca-head__logo").click()
        await pg.locator(".ca-menu__item", has_text="自定义工作流").click()
        await pg.locator(".ca-modal").wait_for()
        row = pg.locator(".ca-workflows__row").filter(has=pg.locator("span", has_text="视频延长")).first
        await row.scroll_into_view_if_needed()
        await row.wait_for()
        async with pg.expect_file_chooser() as fc:
            await row.locator("button.ca-panel__icon").click()
        chooser = await fc.value
        await chooser.set_files(str(WF_EXT))
        await pg.wait_for_timeout(2500)
        row_text = await row.inner_text()
        assert "extend-demo" in row_text, f"extend not assigned: {row_text!r}"
        assert "内置" not in (await row.locator(".ca-fieldselect__text").inner_text()), row_text
        # also assert video+3D groups still present
        video = pg.locator(".ca-workflows__group").filter(has=pg.locator(".ca-gen__label", has_text="视频"))
        assert await video.locator(".ca-workflows__row", has_text="视频放大").count() == 1
        assert await video.locator(".ca-workflows__row", has_text="视频去背景").count() == 1
        model = pg.locator(".ca-workflows__group").filter(has=pg.locator(".ca-gen__label", has_text="3D"))
        await model.scroll_into_view_if_needed()
        assert await model.locator(".ca-workflows__row", has_text="图生 3D").count() == 1
        SHOTS.mkdir(parents=True, exist_ok=True)
        await row.scroll_into_view_if_needed()
        await pg.wait_for_timeout(200)
        await pg.screenshot(path=str(SHOTS / "workflows-extend-assigned-zh-light.png"))
        # categories overview (scroll so video group visible)
        await video.scroll_into_view_if_needed()
        await pg.wait_for_timeout(150)
        await pg.screenshot(path=str(SHOTS / "workflows-video-3d-zh-light.png"))
        await browser.close()


async def test_image_toolbar_custom_3d_full_window_en_dark(app_url, fake_tools, monkeypatch):  # noqa: F811
    """Design HOLD: full app window shot of Image-to-3D menu with 3rd custom item (en dark)."""
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    assert WF_3D.is_file()
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        await pg.add_init_script("""
          localStorage.setItem('comfyart.lang','en');
          localStorage.setItem('comfyart.theme','dark');
          localStorage.setItem('comfyart.toolbar', JSON.stringify({
            pinned: ['quick','chat','upscale','cutout','erase','to3d'],
            names: true,
            seen: ['quick','chat','upscale','cutout','erase','inpaint','expand','text','crop','style','adjust','layers','animate','angles','regenerate','remix','copyPrompt','export','effects','elements','move','mockup','to3d','transform','vectorize','ocr','smudge','preview','info']
          }));
        """)
        await pg.goto(app_url + "?project=e509tb3dFull&new=1")
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1500)
        await _dismiss(pg)
        await pg.locator(".ca-head__logo").click()
        await pg.locator(".ca-menu__item", has_text="Custom workflows").click()
        await pg.locator(".ca-modal").wait_for()
        row = pg.locator(".ca-workflows__row").filter(has=pg.locator("span", has_text="Image to 3D")).first
        await row.scroll_into_view_if_needed()
        async with pg.expect_file_chooser() as fc:
            await row.locator("button.ca-panel__icon").click()
        await (await fc.value).set_files(str(WF_3D))
        await pg.wait_for_timeout(2500)
        assert "demo-3d" in await row.inner_text()
        await pg.locator(".ca-modal .ca-panel__primary").click()
        await pg.wait_for_timeout(400)
        await pg.wait_for_function("!!window.__caEditor")
        await pg.evaluate(MAKE_IMAGE)
        bar = pg.locator(".ca-toolbar--image")
        await bar.wait_for()
        btn = bar.locator(".ca-bar__btn").filter(has_text="3D")
        assert await btn.count() >= 1
        await btn.first.click()
        await pg.wait_for_timeout(300)
        # #570: the 3D button opens the 转 3D panel; models are its segmented switch (custom = third option)
        menu = pg.locator(".ca-toolpanel[data-tool='to3d']")
        await menu.wait_for()
        items = await menu.locator(".ca-seg__btn").all_inner_texts()
        flat = " ".join(items)
        assert "TRELLIS.2" in flat and "Pixal3D" in flat and "demo-3d" in flat, items
        SHOTS.mkdir(parents=True, exist_ok=True)
        # FULL window (design HOLD) — not a narrow strip
        await pg.screenshot(path=str(SHOTS / "image-toolbar-3d-en-dark.png"), full_page=False)
        await browser.close()
