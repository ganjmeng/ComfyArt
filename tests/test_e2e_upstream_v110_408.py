"""#408: upstream v1.1.0 (285fd93 / 515d36e / c1e976a) ported to WaveSpeed, end to end in the built app (mock only, $0).

(1) Stop on a running generator card drops the WaveSpeed task; the card shows 「已停止」/Stopped with the quoted charge.
(2) Settings 「卸载模型」 clears the loaded model list + price table, 「清缓存」 clears the local generation cache +
    thumbnails; each shows a toast saying what was cleared.
(3) The upstream 「Back to ComfyUI」 button (same place, same icon) opens the WaveSpeed console task history in a new
    tab, and its tooltip says so.
Set PR408_SHOTS=<dir> to also write the zh/en x dark/light screenshots."""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

from ComfyArt.api import wavespeed
from test_e2e_comment_edit import EDIT, app_url, mock_ws  # noqa: F401  (fixtures)

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
LOC = {l: json.loads((ROOT / f"src/locales/{l}.json").read_text()) for l in ("zh", "en")}
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("PR408_SHOTS")
HISTORY = "https://wavespeed.ai/predictions"


async def _open(p, url, lang, theme):
    try:
        browser = await p.chromium.launch()
    except Exception as e:
        pytest.skip(f"chromium not available: {e}")
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
    pg = await ctx.new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}');"
                             "window.__opened=[];window.open=(u,n,f)=>{window.__opened.push([String(u),String(n)]);return null}")
    await pg.goto(url)
    await pg.wait_for_timeout(1500)
    return browser, pg


async def _until(fn, timeout=15.0):
    for _ in range(int(timeout * 10)):
        v = await fn()
        if v:
            return v
        await asyncio.sleep(0.1)
    return await fn()


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.screenshot(path=f"{SHOTS}/{name}.png")


LANGS = [("zh", "dark"), ("zh", "light"), ("en", "dark"), ("en", "light")]


@pytest.mark.parametrize("lang,theme", LANGS)
async def test_stop_running_card_shows_stopped_with_charge(app_url, mock_ws, lang, theme):  # noqa: F811
    # one WaveSpeed task already submitted (charged at submit) and still processing; no new submit is ever made
    mock_ws["submits"].append((EDIT, {}))
    mock_ws["status"] = "processing"
    wavespeed._jobs["task1"] = {"model": EDIT, "feature": "edit", "started": time.time(), "next_poll": 0.0, "inputs": {}}
    L = LOC[lang]
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        await pg.mouse.click(28, 83)  # home: new project
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(1200)
        if await pg.locator(".ca-modal").count():
            await pg.locator(".ca-modal button").nth(-2).click()
        await pg.evaluate("""() => { const ed = window.__caEditor; const c = ed.getViewportPageBounds().center;
          ed.createShape({ type: 'generator', x: c.x - 200, y: c.y - 200, props: { w: 400, h: 400 },
            meta: { job: { id: 'ws:task1', node: '1', name: 'mock', kind: 'image' } } }) }""")
        await pg.wait_for_timeout(2500)  # autosave
        await pg.reload()  # resumeJobs picks the running card up, like after a page reload mid-generation
        stop = pg.get_by_test_id("gen-stop")
        await stop.wait_for(timeout=15000)
        assert await stop.get_attribute("title") == L["jobs.stop"]
        await stop.hover()
        await pg.wait_for_timeout(300)
        await _shot(pg, f"stop-button-{lang}-{theme}")
        await stop.click()
        stopped = pg.get_by_test_id("gen-stopped")
        await stopped.wait_for(timeout=10000)
        want = L["wsErr.stopped"].replace("{0}", "4")  # mock quote $0.039 -> 4 credits, truthfully shown
        assert (await stopped.inner_text()).strip() == want
        assert await pg.get_by_test_id("gen-stop").count() == 0
        assert await pg.locator(".tl-toast").count() == 0  # a stop is not an error toast
        assert len(mock_ws["submits"]) == 1  # nothing new submitted or charged
        assert wavespeed._jobs["task1"]["stopped"] is True
        await _shot(pg, f"stopped-{lang}-{theme}")
        await browser.close()


@pytest.mark.parametrize("lang,theme", LANGS)
async def test_settings_unload_and_clear_cache_toasts(app_url, mock_ws, lang, theme):  # noqa: F811
    import folder_paths  # noqa: F401
    from ComfyArt.api._common import app_path
    L = LOC[lang]
    wavespeed._map_cache[("x", "depth", 1)] = b"1"
    import shutil
    shutil.rmtree(app_path("thumbs"), ignore_errors=True)  # only what this test seeds
    os.makedirs(app_path("thumbs"), exist_ok=True)
    for i in range(3):
        Path(app_path("thumbs", f"t{i}.webp")).write_bytes(b"x")
    out = Path(folder_paths.get_output_directory()) / "keep.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"png")
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        await pg.wait_for_timeout(2500)  # let the page's own model/price fetches settle, then seed what Unload clears
        wavespeed._catalog.clear()
        wavespeed._catalog.update({"at": time.time(), "models": {"a/b": {}, "c/d": {}, "e/f": {}}})
        wavespeed._quotes.clear()
        wavespeed._quotes.update({"q1": (0.01, time.time()), "q2": (0.02, time.time())})
        settings = pg.get_by_role("button", name="设置" if lang == "zh" else "Settings").first
        await settings.click()
        item = pg.get_by_test_id("settings-unload")
        assert (await item.inner_text()).strip() == L["settings.unloadModels"]
        # the page itself reloads the list afterwards (free GET /api/v3/models on the mock), so count before that
        await item.click()
        want = L["settings.unloadModelsDone"].replace("{0}", "3").replace("{1}", "2")
        toast = pg.get_by_test_id("memory-toast").filter(has_text=want)
        await toast.first.wait_for(timeout=10000)
        assert not wavespeed._quotes
        await _shot(pg, f"unload-toast-{lang}-{theme}")
        await pg.wait_for_timeout(300)
        await settings.click()
        item = pg.get_by_test_id("settings-clear-cache")
        assert (await item.inner_text()).strip() == L["settings.clearCache"]
        await item.click()
        want = L["settings.clearCacheDone"].replace("{0}", "1").replace("{1}", "3")
        toast = pg.get_by_test_id("memory-toast").filter(has_text=want)
        await toast.first.wait_for(timeout=10000)
        assert not wavespeed._map_cache and not os.listdir(app_path("thumbs"))
        assert out.read_bytes() == b"png"  # generated files are never touched
        await _shot(pg, f"clear-cache-toast-{lang}-{theme}")
        assert len(mock_ws["submits"]) == 0
        await browser.close()


@pytest.mark.parametrize("lang,theme", LANGS)
async def test_jump_button_opens_wavespeed_history(app_url, lang, theme):  # noqa: F811
    L = LOC[lang]
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        btn = pg.get_by_test_id("rail-ws-history")
        assert await btn.get_attribute("title") == L["home.backToComfyUITip"]
        assert await btn.get_attribute("aria-label") == L["home.backToComfyUI"]
        # same place as upstream: right above Settings at the bottom of the home rail
        nxt = await btn.evaluate("b => { const n = b.nextElementSibling; const x = n && (n.matches('[aria-label]') ? n : n.querySelector('[aria-label]')); return x && x.getAttribute('aria-label') }")
        assert nxt == ("设置" if lang == "zh" else "Settings")
        await btn.hover()
        if SHOTS:  # native title tooltips are not painted in headless screenshots; draw the same text next to it
            await pg.evaluate("""([t]) => { const b = document.querySelector('[data-testid=rail-ws-history]').getBoundingClientRect();
              const d = document.createElement('div'); d.textContent = t; Object.assign(d.style, { position: 'fixed',
              left: (b.right + 8) + 'px', top: (b.top + b.height / 2 - 12) + 'px', padding: '4px 10px', background: '#202124',
              color: '#fff', font: '13px sans-serif', borderRadius: '4px', zIndex: 99999, whiteSpace: 'nowrap' });
              document.body.appendChild(d) }""", [L["home.backToComfyUITip"]])
        await _shot(pg, f"jump-tooltip-{lang}-{theme}")
        await btn.click()
        assert await pg.evaluate("window.__opened") == [[HISTORY, "_blank"]]
        assert pg.url == app_url or pg.url.startswith(app_url)  # the app itself stays open
        await browser.close()
