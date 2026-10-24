"""#249: at 1280×800 the multi-angle panel matches main and Generate is fully visible. Mock only, $0.

Sliders, presets and the 4-angle button are on screen without scrolling. The generate
button sits above the bottom dock.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

pw = pytest.importorskip("playwright.async_api")

from test_e2e_comment_edit import app_url, mock_ws  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*.html")) and not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("ANGLE_SHOTS")


def _png() -> bytes:
    img = Image.new("RGB", (480, 360), (232, 222, 205))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((70, 50, 410, 310), radius=24, fill=(80, 130, 200))
    d.ellipse((180, 110, 300, 230), fill=(250, 210, 90))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.parametrize("lang,more,tool,generate,back,four", [
    ("zh", "更多", "多角度", "生成", "背面", "一次生成 4 个角度"),
    ("en", "More", "Multi-Angle", "Generate", "Back", "Generate 4 angles at once"),
])
async def test_generate_visible_at_1280x800(app_url, tmp_path, lang, more, tool, generate, back, four):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
        except Exception as e:
            pytest.skip(f"chrome not available: {e}")
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN" if lang == "zh" else "en-US")
        pg = await ctx.new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
        src = tmp_path / "src.png"
        src.write_bytes(_png())
        await pg.goto(app_url)
        await pg.wait_for_timeout(800)
        await pg.get_by_role("button", name="新建项目" if lang == "zh" else "New Project").click()
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(800)
        if await pg.locator(".ca-modal").count():
            await pg.locator(".ca-modal button").nth(-2).click()
        await pg.locator(".ca-dock input[type=file][multiple]").set_input_files(str(src))
        await pg.locator(".tl-image").first.wait_for()
        await pg.wait_for_timeout(400)
        await pg.locator(".tl-image").first.click()
        await pg.locator(".ca-toolbar").get_by_role("button", name=more).click()
        await pg.get_by_role("button", name=tool, exact=True).click()
        panel = pg.locator(".ca-panel")
        await panel.wait_for()
        await pg.wait_for_timeout(400)
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            await pg.screenshot(path=f"{SHOTS}/angle-{lang}.png")
        assert await panel.get_attribute("data-scroll") is None
        assert await pg.get_by_text("最大 90°" if lang == "zh" else "Up to 90°").count() == 0
        scrolled = await panel.evaluate("el => el.scrollHeight > el.clientHeight + 1")
        assert scrolled is False
        ranges = panel.locator("input[type=range]")
        assert await ranges.count() == 3
        assert await ranges.nth(0).get_attribute("min") == "0" and await ranges.nth(0).get_attribute("max") == "360"
        assert await ranges.nth(1).get_attribute("min") == "-30" and await ranges.nth(1).get_attribute("max") == "60"
        assert await ranges.nth(2).get_attribute("min") == "0" and await ranges.nth(2).get_attribute("max") == "10"
        back_btn = panel.get_by_role("button", name=back, exact=True)
        four_btn = panel.get_by_role("button", name=four, exact=True)
        btn = panel.locator(".ca-panel__primary", has_text=generate)
        await btn.wait_for()
        dock = await pg.locator(".ca-dock").bounding_box()
        vp = pg.viewport_size
        assert dock and vp

        async def fully_visible(locator):
            box = await locator.bounding_box()
            assert box and box["width"] > 8 and box["height"] > 8
            assert box["x"] >= -0.5 and box["y"] >= -0.5
            assert box["x"] + box["width"] <= vp["width"] + 0.5
            assert box["y"] + box["height"] <= vp["height"] + 0.5
            assert box["y"] + box["height"] <= dock["y"] + 0.5
            hit = await pg.evaluate(
                """(b) => {
                  const el = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2)
                  const panel = document.querySelector('.ca-panel')
                  return !!(el && panel && panel.contains(el))
                }""",
                box,
            )
            assert hit
            return box

        for locator in (ranges.nth(0), ranges.nth(1), ranges.nth(2), back_btn, four_btn):
            await fully_visible(locator)
        box = await fully_visible(btn)
        covered = await pg.evaluate(
            """(b) => {
              const btn = document.querySelector('.ca-panel .ca-panel__primary')
              const pts = [[b.x+3,b.y+3],[b.x+b.width-3,b.y+3],[b.x+3,b.y+b.height-3],[b.x+b.width-3,b.y+b.height-3],[b.x+b.width/2,b.y+b.height/2]]
              return pts.filter(([x,y]) => { const el = document.elementFromPoint(x,y); return !(el && btn && (el === btn || btn.contains(el))) })
            }""",
            box,
        )
        assert covered == []
        await btn.click()
        await panel.wait_for(state="hidden")
        await browser.close()
