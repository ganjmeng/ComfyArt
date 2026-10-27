"""#371/#378: Arti mascot play animation + placement, asserted on resolved values in headless Chrome.

Runs the built dist/ (so rebuild after editing src). Guards against: animation:none on
play/typing/hover, wrong steps() count, wrong duration (must be 17 x 250ms = 4250ms),
keyframes not ending on the full strip, .arti-mascot--play dropped from the selector,
Lv.1/2/3 -> sheet mapping swaps, hover lift and top:-29px peek.
"""
from __future__ import annotations

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: E402,F401

FRAMES, FRAME_MS = 17, 250
DURATION_MS = FRAMES * FRAME_MS  # 4250
FRAME_W = 50  # px per sprite frame
M = "[data-testid=arti-mascot]"

READ = """(cls) => {
  const m = document.querySelector('[data-testid=arti-mascot]');
  if (cls) { m.classList.remove('arti-mascot--hover','arti-mascot--typing','arti-mascot--play'); m.classList.add(cls); }
  const cs = getComputedStyle(m);
  const a = m.getAnimations().find(x => x.animationName === 'arti-mascot-play');
  const out = { names: cs.animationName, durations: cs.animationDuration, timing: cs.animationTimingFunction,
                bgSize: cs.backgroundSize, width: m.getBoundingClientRect().width, anim: !!a };
  if (a) {
    a.pause();
    a.currentTime = FRAME_MS + 1; out.pos1 = getComputedStyle(m).backgroundPosition;
    a.currentTime = DURATION; out.endPos = getComputedStyle(m).backgroundPosition;
    const t = a.effect.getComputedTiming(); out.animDuration = t.duration; out.steps = []; for (let k = 0; k <= FRAMES; k++) { a.currentTime = Math.min(k * FRAME_MS + 1, DURATION); out.steps.push(getComputedStyle(m).backgroundPosition); }
  }
  return out;
}""".replace("FRAMES", str(FRAMES)).replace("FRAME_MS", str(FRAME_MS)).replace("DURATION", str(DURATION_MS))


async def _open(p, url, level=1, theme="dark"):
    browser = await p.chromium.launch(channel="chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2, reduced_motion="no-preference")
    pg = await ctx.new_page()
    await pg.add_init_script("localStorage.setItem('comfyart.lang','zh')")
    await pg.add_init_script(f"localStorage.setItem('comfyart.theme','{theme}')")
    await pg.goto(url + f"?project=p371anim{level}{theme}&new=1&artiLevel={level}")
    await pg.locator(M).wait_for(timeout=20000)
    await pg.wait_for_timeout(500)
    return browser, pg


def _px(s: str) -> float:
    return float(s.split()[0].replace("px", ""))


def _assert_play(st, label):
    assert st["anim"], f"{label}: no arti-mascot-play animation ({st['names']})"
    assert "arti-mascot-play" in st["names"].split(", ")[0], label
    assert st["durations"].split(", ")[0] == "4.25s", f"{label}: duration {st['durations']}"
    assert st["animDuration"] == DURATION_MS, f"{label}: {st['animDuration']}"
    assert st["timing"].split(", ")[0] in ("steps(17)", "steps(17, end)"), f"{label}: {st['timing']}"
    # full strip end only: -(17 x 50px) = -850px, so every step is exactly one 50px frame
    w = st["width"]
    assert w == 50, f"{label}: width {w}"
    assert st["endPos"].split()[0] == "-850px", f"{label}: end {st['endPos']}"
    xs = [_px(p) for p in st["steps"]]
    assert xs == [-FRAME_W * k for k in range(FRAMES)] + [-FRAME_W * FRAMES], f"{label}: steps {st['steps']}"
    assert all(xs[k] - xs[k + 1] == FRAME_W for k in range(FRAMES)), f"{label}: step sizes {xs}"
    assert st["pos1"].split()[0] not in ("0%", "0px"), f"{label}: frame 1 did not advance ({st['pos1']})"


async def test_371_play_typing_hover_animate_17x250(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, app_url)
        except Exception as e:
            pytest.skip(f"chromium: {e}")
        try:
            idle = await pg.evaluate(READ, None)
            assert not idle["anim"] and idle["names"] == "none", f"idle must be static: {idle['names']}"
            assert idle["bgSize"] == f"{FRAMES * 100}% 100%"
            for cls in ("arti-mascot--play", "arti-mascot--typing", "arti-mascot--hover"):
                _assert_play(await pg.evaluate(READ, cls), cls)
            # real hover + real typing, not just forced classes
            await pg.evaluate(READ, "")  # noop class reset handled below
            await pg.goto(pg.url)
            await pg.locator(M).wait_for()
            await pg.hover(M)
            await pg.wait_for_timeout(50)
            assert await pg.locator(M).get_attribute("data-trigger") == "hover"
            _assert_play(await pg.evaluate(READ, None), "real hover")
            await pg.mouse.move(700, 200)
            await pg.locator(".ca-composer__input").first.click()
            await pg.keyboard.type("hi")
            await pg.wait_for_timeout(50)
            assert await pg.locator(M).get_attribute("data-trigger") == "typing"
            st = await pg.evaluate(READ, None)
            _assert_play(st, "real typing")
            assert "arti-mascot-fade" in st["names"]
        finally:
            await browser.close()


async def test_371_level_sheet_mapping(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="chrome", args=["--no-sandbox"])
        except Exception as e:
            pytest.skip(f"chromium: {e}")
        try:
            for lv in (1, 2, 3):
                pg = await browser.new_page()
                await pg.goto(app_url + f"?project=p371lv{lv}&new=1&artiLevel={lv}")
                await pg.locator(M).wait_for(timeout=20000)
                assert await pg.locator(M).get_attribute("data-level") == str(lv)
                bg = await pg.evaluate("() => getComputedStyle(document.querySelector('[data-testid=arti-mascot]')).backgroundImage")
                assert f"/mascot-lv{lv}-dna-a" in bg, f"Lv.{lv} -> {bg}"
                await pg.close()
        finally:
            await browser.close()


async def test_371_peek_top_29_and_hover_lift(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, app_url, theme="light")
        except Exception as e:
            pytest.skip(f"chromium: {e}")
        try:
            geo = """() => { const w = document.querySelector('[data-testid=arti-mascot-wrap]');
              const m = document.querySelector('[data-testid=arti-mascot]'); const c = w.closest('.ca-composer');
              return { wrapTop: getComputedStyle(w).top, dw: w.getBoundingClientRect().top - c.getBoundingClientRect().top - c.clientTop, off: w.offsetTop,
                       dm: m.getBoundingClientRect().top - c.getBoundingClientRect().top - c.clientTop, tf: getComputedStyle(m).transform }; }"""
            g = await pg.evaluate(geo)
            assert g["wrapTop"] == "-29px", g
            assert g["off"] == -29 and round(g["dw"]) == -29 and round(g["dm"]) == -29, g
            await pg.hover(M)
            await pg.wait_for_timeout(400)  # 160ms transform transition
            h = await pg.evaluate(geo)
            assert h["tf"] == "matrix(1, 0, 0, 1, 0, -11)", h
            assert round(h["dm"]) == -40, h  # -29 - 11 lift (relative to composer padding edge)
        finally:
            await browser.close()
