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


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("zh", "dark"), ("en", "light"), ("en", "dark")])
async def test_generate_visible_at_1280x800(app_url, tmp_path, lang, theme):  # noqa: F811
    zh = lang == "zh"
    more, tool, generate = ("更多", "多角度", "生成") if zh else ("More", "Multi-Angle", "Generate")
    back, four = ("背面", "一次生成 4 个角度") if zh else ("Back", "Generate 4 angles at once")
    read = "右前 · 平视 · 中景" if zh else "Front Right · Level · Medium"
    subject, camera = ("主体", "摄像头") if zh else ("Subject", "Camera")
    chosen = "右前" if zh else "Front-R"
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
        except Exception as e:
            pytest.skip(f"chrome not available: {e}")
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, locale="zh-CN" if zh else "en-US", device_scale_factor=2)
        pg = await ctx.new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
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
        await panel.locator(".ca-angle__view canvas").wait_for()
        await pg.wait_for_timeout(700)
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            await panel.screenshot(path=f"{SHOTS}/angle-{lang}-{theme}-subject.png")
            if (lang, theme) == ("zh", "light"):
                await panel.get_by_role("tab", name=camera).click()
                await pg.wait_for_timeout(500)
                await panel.screenshot(path=f"{SHOTS}/angle-zh-light-camera.png")
                await panel.get_by_role("tab", name=subject).click()
            if (lang, theme) == ("en", "dark"):
                await pg.screenshot(path=f"{SHOTS}/angle-en-dark.png")
                await panel.screenshot(path=f"{SHOTS}/angle-en-dark-panel.png")
        assert await panel.get_attribute("data-scroll") is None
        assert await pg.get_by_text("最大 90°" if zh else "Up to 90°").count() == 0
        scrolled = await panel.evaluate("el => el.scrollHeight > el.clientHeight + 1")
        assert scrolled is False
        assert await panel.locator(".ca-angle__read").inner_text() == read
        assert await panel.get_by_role("tab", name=subject).get_attribute("aria-selected") == "true"
        assert await panel.get_by_role("button", name="正面" if zh else "Front", exact=True).count() == 0
        on = panel.locator(".ca-angle__chip[data-on]")
        assert await on.count() == 1 and await on.inner_text() == chosen
        chips = panel.locator(".ca-angle__chip")
        assert await chips.count() == 10
        overflow = await chips.evaluate_all("els => els.filter(el => el.scrollWidth > el.clientWidth + 1).map(el => el.textContent)")
        assert overflow == []
        view_box = await panel.locator(".ca-angle__view").bounding_box()
        chip_box = await panel.locator(".ca-angle__chips").bounding_box()
        panel_box = await panel.bounding_box()
        assert view_box and chip_box and panel_box
        assert abs(view_box["x"] - chip_box["x"]) <= 1
        assert abs((view_box["x"] + view_box["width"]) - (chip_box["x"] + chip_box["width"])) <= 1
        assert abs((view_box["x"] - panel_box["x"]) - 13) <= 2
        vals = panel.locator(".ca-angle__val")
        assert await vals.nth(0).inner_text() == "45"
        assert await vals.nth(1).inner_text() == "0"
        assert await vals.nth(2).inner_text() == "5"
        ranges = panel.locator("input[type=range]")
        assert await ranges.count() == 3
        assert await ranges.nth(0).get_attribute("min") == "0" and await ranges.nth(0).get_attribute("max") == "359"
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
