"""#806 opt-in e2e: push a small real png through the motion dialog's source_image upload
(uploadSkillImage → ComfyUI POST /api/upload/image). No generation, no paid API.
The reference-video field is gone. Run: QA687_REAL_URL=http://127.0.0.1:8188/comfyart/ Skipped otherwise."""
from __future__ import annotations

import base64
import hashlib
import os
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
URL = os.environ.get("QA687_REAL_URL")
SHOTS = os.environ.get("QA687_SHOTS")
pytestmark = pytest.mark.skipif(not URL, reason="needs QA687_REAL_URL (app in front of a real ComfyUI)")
# 1×1 png
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


async def test_motion_source_image_real_upload_806(tmp_path):
    png = tmp_path / "qa806_src.png"
    data = base64.b64decode(PNG_B64)
    png.write_bytes(data)
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','en');localStorage.setItem('comfyart.theme','light')")
        posts: list[tuple[str, int]] = []
        pg.on("response", lambda r: posts.append((r.url, r.status)) if "/upload/image" in r.url else None)
        await pg.goto(URL)
        await pg.get_by_test_id("rail-skills").click()
        card = pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="motion-poster-generator"]')
        await card.scroll_into_view_if_needed()
        await card.hover()
        await card.get_by_test_id("skills-card-try").click()
        dlg = pg.locator('[data-testid="skill-run-dialog"][data-skill="motion-poster-generator"]')
        await dlg.wait_for(timeout=10000)
        box = dlg.locator('[data-testid="skill-run-field"][data-key="source_image"]')
        await box.locator("input[type=file]").set_input_files(str(png))
        img = box.locator("img")
        try:
            await img.wait_for(timeout=15000)
        except Exception:
            print("DEBUG", posts, await box.inner_html())
            raise
        src = await img.get_attribute("src")
        assert await dlg.get_by_test_id("skill-run-upload-error").count() == 0
        ok = await img.evaluate("el => el.naturalWidth || el.width")
        if SHOTS:
            await pg.wait_for_timeout(1200)
            await pg.screenshot(path=str(Path(SHOTS) / "skill-fields-motion-source-image-upload-en-light.png"))
        await browser.close()
    assert posts and all(s == 200 for _, s in posts), posts
    assert ok == 1, ok
    full = urllib.request.urlopen(urllib.parse.urljoin(URL, src)).read()
    assert hashlib.sha256(full).hexdigest() == hashlib.sha256(data).hexdigest()
    print("UPLOAD", posts, src, len(full))
