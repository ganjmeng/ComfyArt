"""#398: /arti capability card contrast — WCAG AA (text ≥4.5:1, UI ≥3:1) using existing tokens.
Static CSS checks + live Chromium computed-style contrast so disabled ≠ enabled-off.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "src/styles/home.css").read_text(encoding="utf-8")
TOKENS = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src/styles").glob("*.css"))


def _lum(c):
    f = lambda v: (v / 255) / 12.92 if v / 255 <= .03928 else (((v / 255) + .055) / 1.055) ** 2.4
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])


def _cr(rgba, bg):
    a = rgba[3]
    fg = [rgba[i] * a + bg[i] * (1 - a) for i in range(3)]
    x, y = _lum(fg), _lum(bg)
    return (max(x, y) + .05) / (min(x, y) + .05)


def _rule(sel):
    m = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", HOME)
    assert m, sel
    return m.group(1)


TEXT2 = {"light": (0, 0, 0, .6), "dark": (255, 255, 255, .6)}
BG = {"light": (255, 255, 255), "dark": (26, 26, 26)}


def test_capdesc_uses_text2_and_meets_aa():
    assert "var(--ca-text-2)" in _rule(".ca-arti__capdesc")
    for t in ("light", "dark"):
        assert _cr(TEXT2[t], BG[t]) >= 4.5


def test_enabled_off_has_text2_outline():
    """1px --ca-text-2 outline is for enabled-but-OFF only (≥3:1)."""
    body = _rule(".ca-arti__cap .ca-switch:not([data-on]):not(:disabled)")
    assert "var(--ca-text-2)" in body
    assert "box-shadow" in body
    for t in ("light", "dark"):
        assert _cr(TEXT2[t], BG[t]) >= 3


def test_disabled_is_more_muted_than_off():
    """Disabled: lower opacity, no matching outline — off ≠ disabled at a glance."""
    body = _rule(".ca-arti__cap[data-disabled] .ca-switch:disabled")
    assert "opacity: .55" in body or "opacity:.55" in body
    assert "box-shadow: none" in body or "box-shadow:none" in body
    assert "var(--ca-text-2)" not in body  # must not share the strong off outline


def test_text2_token_unchanged():
    assert re.search(r"--ca-text-2:\s*rgba\(0,\s*0,\s*0,\s*\.6\)", TOKENS)


# --- live Chromium (real app) ---
pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401

pytestmark_live = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")

MEASURE_JS = """(e) => {
  const p = (s) => { const m = String(s).match(/[\\d.]+/g); if (!m) return [0,0,0,0]; const n = m.map(Number); return [n[0], n[1], n[2], n.length > 3 ? n[3] : 1]; };
  let bgs = [];
  for (let n = e; n; n = n.parentElement) {
    const c = getComputedStyle(n).backgroundColor;
    const v = p(c);
    if (v[3] > 0) bgs.push(v);
    if (v[3] >= 1) break;
  }
  let bg = [255, 255, 255];
  for (const v of bgs.reverse()) bg = [0, 1, 2].map(i => v[i] * v[3] + bg[i] * (1 - v[3]));
  const cs = getComputedStyle(e);
  return {
    color: p(cs.color),
    bg,
    shadow: cs.boxShadow,
    opacity: parseFloat(cs.opacity),
    disabled: e.disabled === true,
  };
}"""


def _contrast(fg_rgba, bg_rgb):
    return _cr(tuple(fg_rgba), tuple(bg_rgb[:3]))


@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_live_arti_contrast_and_switch_diff(app_url, fake_tools, theme):  # noqa: F811
    """Real headless Chromium: capdesc ≥4.5:1; enabled-off outlined; disabled more muted."""
    if not any((ROOT / "dist").glob("*")):
        pytest.skip("needs built dist/")
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Shanghai")
        page = await ctx.new_page()
        await page.add_init_script(
            f"localStorage.setItem('comfyart.lang','zh');"
            f"localStorage.setItem('comfyart.theme','{theme}');"
            f"localStorage.setItem('comfyart.e2e','1');"
        )
        await page.goto(app_url.rstrip("/") + "/?view=arti")
        await page.locator("[data-testid=arti-memory-center]").wait_for(timeout=20000)
        await page.wait_for_timeout(600)

        descs = page.locator(".ca-arti__capdesc")
        assert await descs.count() >= 1
        d0 = await descs.first.evaluate(MEASURE_JS)
        assert _contrast(d0["color"], d0["bg"]) >= 4.5, d0

        offs = page.locator(".ca-arti__cap .ca-switch:not([data-on]):not(:disabled)")
        diss = page.locator(".ca-arti__cap[data-disabled] .ca-switch")
        assert await offs.count() >= 1, "need at least one enabled-off switch"
        assert await diss.count() >= 1, "need at least one disabled switch"

        off = await offs.first.evaluate(MEASURE_JS)
        dis = await diss.first.evaluate(MEASURE_JS)

        # enabled-off: strong outline present
        assert off["shadow"] and off["shadow"] != "none", off
        assert off["opacity"] >= 0.95, off

        # disabled: more muted — lower opacity, outline not matching off
        assert dis["opacity"] < 0.85, dis
        assert dis["opacity"] < off["opacity"], (dis, off)
        # either no outline, or a weaker one that is not identical to off
        assert dis["shadow"] != off["shadow"] or dis["opacity"] <= 0.6, (dis, off)

        await browser.close()
