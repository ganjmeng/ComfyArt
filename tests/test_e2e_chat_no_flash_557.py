"""#557 e2e (mock only, $0): in the normal canvas chat, while /bot/status (the provider list) is still pending, the
composer mode pill and reference button already show their loaded form (Loomi + icon-only reference), so nothing
flashes. A MutationObserver records every pill/reference state from first paint; all must equal the loaded state.
Set CHAT_557_SHOTS=/dir for 1280x800 PNGs (zh light + en dark, held-loading frame + loaded)."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("CHAT_557_SHOTS")

RECORD = """(() => {
  window.__seen557 = []
  const read = () => {
    const m = document.querySelector('.ca-composer__mode')
    if (!m) return
    const r = document.querySelector('.ca-composer__foot .ca-refbtn')
    const s = JSON.stringify([m.innerText.trim(), r ? r.innerText.trim() : null])
    if (window.__seen557[window.__seen557.length - 1] !== s) window.__seen557.push(s)
  }
  new MutationObserver(read).observe(document, { subtree: true, childList: true, characterData: true, attributes: true })
})()"""


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_mode_pill_and_ref_never_flash(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
        await pg.goto(app_url)
        await pg.wait_for_timeout(1500)
        await pg.mouse.click(28, 83)  # home: new project → canvas with the normal chat
        await pg.locator(".ca-composer__mode").wait_for()
        url = pg.url

        release = asyncio.Event()
        held: list[str] = []

        async def hold(route):
            held.append(route.request.url)
            await release.wait()
            try:
                await route.continue_()
            except Exception:  # page/route already gone at teardown
                pass
        await pg.route("**/comfyart/bot/status*", hold)
        await pg.add_init_script(RECORD)
        await pg.goto(url)
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(800)
        assert held, "provider list request was not held"
        loading = await pg.evaluate("window.__seen557.slice()")
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            # shots only: lift the boot loader overlay so the composer state underneath (asserted above) is visible
            await pg.add_style_tag(content=".lm-loader{display:none!important}")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=str(Path(SHOTS) / f"557-loading-{lang}-{theme}.png"))
        release.set()
        await pg.wait_for_function("document.querySelector('.ca-composer__mode')?.dataset.agent")
        await pg.wait_for_timeout(1000)
        if SHOTS:
            await pg.screenshot(path=str(Path(SHOTS) / f"557-loaded-{lang}-{theme}.png"))
        seen = await pg.evaluate("window.__seen557.slice()")
        await browser.close()
    final = seen[-1]
    assert final == '["Loomi",""]', seen  # loaded: product label + icon-only reference button
    assert loading and all(s == final for s in loading), (loading, final)  # before load: identical, no 「Agent / 参考」
    assert all(s == final for s in seen), seen
