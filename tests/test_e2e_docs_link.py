"""#211: the settings menu 「使用指南」/User Guide opens the live Mintlify site in the UI language (mock only, $0)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("DOCS_LINK_SHOTS")


@pytest.mark.parametrize("lang,want", [("zh", "https://ghhsdob.mintlify.site/zh"), ("en", "https://ghhsdob.mintlify.site")])
async def test_settings_guide_opens_docs(app_url, lang, want):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        pg = await ctx.new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');"
                                 "window.__opened=[];window.open=(u)=>{window.__opened.push(String(u));return null}")
        await pg.goto(app_url)
        await pg.wait_for_timeout(1500)
        await pg.get_by_role("button", name="设置" if lang == "zh" else "Settings").first.click()
        item = pg.get_by_test_id("settings-guide")
        await item.wait_for()
        await item.hover()
        if SHOTS:
            await pg.evaluate("""u => { const d=document.createElement('div'); d.id='__url';
              d.textContent='→ '+u; Object.assign(d.style,{position:'fixed',left:'8px',bottom:'8px',padding:'4px 10px',
              background:'#202124',color:'#fff',font:'13px sans-serif',borderRadius:'4px',zIndex:99999});
              document.body.appendChild(d) }""", want)
            await pg.screenshot(path=f"{SHOTS}/settings-guide-{lang}.png")
        await item.click()
        assert await pg.evaluate("window.__opened") == [want]
        await browser.close()
