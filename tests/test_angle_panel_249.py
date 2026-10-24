"""#249: at 1280×800 the multi-angle Generate button is fully visible and clickable. Mock only, $0."""
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


@pytest.mark.parametrize("lang,more,tool,generate,note", [
    ("zh", "更多", "多角度", "生成", "最大 90°，不支持背面"),
    ("en", "More", "Multi-Angle", "Generate", "Up to 90°, back view not supported"),
])
async def test_generate_visible_at_1280x800(app_url, tmp_path, lang, more, tool, generate, note):  # noqa: F811
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
        panel = pg.locator(".ca-panel[data-scroll]")
        await panel.wait_for()
        await pg.get_by_text(note, exact=True).wait_for()
        h = panel.locator("input[type=range]").nth(0)
        v = panel.locator("input[type=range]").nth(1)
        assert await h.get_attribute("min") == "-90" and await h.get_attribute("max") == "90"
        assert await v.get_attribute("min") == "-30" and await v.get_attribute("max") == "60"
        btn = panel.locator(".ca-panel__primary", has_text=generate)
        await btn.wait_for()
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            await pg.screenshot(path=f"{SHOTS}/angle-{lang}.png")
        box = await btn.bounding_box()
        assert box and box["height"] >= 30 and box["width"] >= 40
        vp = pg.viewport_size
        assert box["x"] >= -0.5 and box["y"] >= -0.5
        assert box["x"] + box["width"] <= vp["width"] + 0.5
        assert box["y"] + box["height"] <= vp["height"] + 0.5
        dock = await pg.locator(".ca-dock").bounding_box()
        assert dock and box["y"] + box["height"] <= dock["y"] + 0.5
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
