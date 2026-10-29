"""#437: reference DOM values for the 联网搜索结果 card and the model-name row, asserted with computed style.
Real AssistantBlocks + the app CSS; the favicon request is blocked, so nothing leaves the box ($0)."""
import os
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install")

CASES = [("zh", "light"), ("en", "dark")]


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("process437")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/process437/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0}}{css}</style>"
        f"<div id=root></div><script src=app.js></script>")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


def _open(browser, bundle, lang, theme):
    page = browser.new_page(viewport={"width": 420, "height": 700}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(300)
    return page


CS = """(sel) => { const e = document.querySelector(sel); const c = getComputedStyle(e); const r = e.getBoundingClientRect();
  return { h: r.height, w: r.width, right: r.right, top: r.top, bottom: r.bottom, left: r.left,
    minH: c.minHeight, pl: c.paddingLeft, pr: c.paddingRight, pt: c.paddingTop, radius: c.borderTopLeftRadius,
    bw: c.borderTopWidth, bc: c.borderTopColor, bg: c.backgroundColor, ov: c.overflow, mt: c.marginTop, mb: c.marginBottom,
    fs: c.fontSize, lh: c.lineHeight, fw: c.fontWeight, op: c.opacity, clamp: c.webkitLineClamp, gap: c.columnGap } }"""


def _rows(page, scope):
    return page.evaluate("""(s) => [...document.querySelectorAll(s + ' .ca-process__row')].map(r => {
      const b = r.getBoundingClientRect(), c = getComputedStyle(r), i = r.querySelector('.ca-process__icon').getBoundingClientRect();
      const sp = r.querySelector('[data-testid=process-rail]');
      const sr = sp && getComputedStyle(sp).display !== 'none' ? sp.getBoundingClientRect() : null;
      return { kind: r.dataset.kind, top: b.top, bottom: b.bottom, h: b.height, display: c.display, ai: c.alignItems, gap: c.columnGap,
               il: i.left, iw: i.width, it: i.top, ib: i.bottom, rail: sr && { l: sr.left, w: sr.width, t: sr.top, b: sr.bottom },
               railBg: sp ? getComputedStyle(sp).backgroundColor : null } })""", scope)


@pytest.mark.parametrize("lang,theme", CASES)
def test_rows_and_rail_stubs(browser, bundle, lang, theme):
    page = _open(browser, bundle, lang, theme)
    rows = _rows(page, "#search")
    assert len(rows) >= 2
    for r in rows:
        assert (r["h"], r["display"], r["ai"], r["gap"]) == (24, "flex", "center", "6px")
    steps = page.evaluate(CS, "#search .ca-process__steps")
    assert steps["pt"] == "8px" and abs(rows[0]["top"] - steps["top"] - 8) < 0.5
    plain = [r for r in rows if r["kind"] != "search_pages"]
    for a, b in zip(plain, plain[1:]):
        assert abs((b["it"] - a["it"]) - 32) < 0.5  # 24px row + 8px column gap
    border = page.evaluate("getComputedStyle(document.querySelector('.ca-process__card')).borderTopColor")
    for k, r in enumerate(rows):
        nxt = rows[k + 1] if k + 1 < len(rows) else None
        if r["kind"] == "search_pages" or nxt is None:
            assert r["rail"] is None  # no rail beside the card, none after the last group
            continue
        st = r["rail"]
        assert st is not None and st["w"] == 1
        assert abs((st["l"] + 0.5) - (r["il"] + r["iw"] / 2)) < 0.01 and r["iw"] == 16
        assert abs(st["t"] - (r["top"] + 20)) < 0.5 and st["t"] >= r["ib"] - 0.5  # starts below its icon
        assert abs(st["b"] - nxt["top"]) < 0.5  # stops at the next group's top
        assert r["railBg"] == ("rgba(0, 0, 0, 0.07)" if theme == "light" else "rgba(255, 255, 255, 0.1)")
    page.close()


@pytest.mark.parametrize("lang,theme", CASES)
def test_search_card_reference_values(browser, bundle, lang, theme):
    page = _open(browser, bundle, lang, theme)
    card = page.evaluate(CS, "#search .ca-process__card")
    row = page.evaluate(CS, "#search .ca-process__row[data-kind=search_pages]")
    icon = page.evaluate(CS, "#search .ca-process__row[data-kind=search_pages] .ca-process__icon")
    assert card["h"] == 58 and card["minH"] == "56px" and card["w"] == 349
    assert abs(card["left"] - icon["left"]) < 0.5  # same x as the row icons
    assert abs(card["top"] - row["bottom"] - 12) < 0.5  # 12px above the card
    assert (card["pl"], card["pr"], card["pt"]) == ("12px", "0px", "0px")
    assert card["radius"] == "12px" and card["bw"] == "1px"
    assert card["bc"] == ("rgba(0, 0, 0, 0.1)" if theme == "light" else "rgba(255, 255, 255, 0.1)")
    assert card["bg"] == "rgba(0, 0, 0, 0)" and card["ov"] == "hidden" and card["gap"] == "20px"
    title = page.evaluate(CS, "#search .ca-process__cardtitle")
    assert (title["fs"], title["lh"], title["fw"], title["op"], title["clamp"]) == ("12px", "18px", "400", "0.9", "2")
    assert (title["mt"], title["mb"]) == ("10px", "10px")
    # was ≈.27: the title inherited --ca-muted (alpha .3) under its .9 opacity. Ink is now solid, so .9 is the only alpha.
    ink = page.evaluate("getComputedStyle(document.querySelector('#search .ca-process__cardtitle')).color")
    assert ink == ("rgb(0, 0, 0)" if theme == "light" else "rgb(255, 255, 255)")
    eff = page.evaluate("""(() => { let e = document.querySelector('#search .ca-process__cardtitle'), a = 1;
      for (; e; e = e.parentElement) a *= +getComputedStyle(e).opacity; return a })()""")
    assert abs(eff - 0.9) < 0.001
    art = page.evaluate(CS, "#search .ca-process__cardart")
    assert (art["w"], art["h"]) == (56, 56) and abs(art["right"] - (card["right"] - 1)) < 0.5
    tr = page.evaluate("document.querySelector('#search .ca-process__cardtitle').getBoundingClientRect().right")
    assert art["left"] - tr >= 20 - 0.5
    fills = page.evaluate("[...document.querySelectorAll('#search .ca-process__cardart svg > *')].map(e => getComputedStyle(e).fill)")
    if theme == "dark":
        assert "rgb(255, 255, 255)" not in fills and "rgb(250, 250, 250)" not in fills and "rgb(212, 212, 216)" not in fills
        assert fills[0] == "rgb(38, 38, 38)" and fills[4] == "rgb(44, 44, 44)"
    else:
        assert fills[4] == "rgb(255, 255, 255)"
    # favicon blocked → globe only, no broken image
    assert page.locator("[data-testid=search-favicon]").count() == 0
    assert page.evaluate("[...document.images].filter(i => !i.naturalWidth).length") == 0
    page.close()


@pytest.mark.parametrize("lang,theme", CASES)
def test_model_row_reference_values(browser, bundle, lang, theme):
    page = _open(browser, bundle, lang, theme)
    row = '#gen .ca-process__row[data-kind=image]'
    icon = page.evaluate(CS, f"{row} .ca-process__icon .ca-icon")
    assert (icon["w"], icon["h"], icon["op"]) == (16, 16, "0.55")
    svg = page.locator(f"{row} .ca-process__icon svg")
    assert svg.get_attribute("viewBox") == "0 0 24 24" and svg.get_attribute("fill") == "none"
    assert (svg.get_attribute("stroke"), svg.get_attribute("stroke-width")) == ("currentColor", "1.5")
    assert (svg.get_attribute("stroke-linecap"), svg.get_attribute("stroke-linejoin")) == ("round", "round")
    solids = page.evaluate(f"[...document.querySelectorAll('{row} .ca-process__icon svg > *')].filter(e => getComputedStyle(e).fill !== 'none').length")
    assert solids == 1 and page.locator(f"{row} [data-solid=star]").count() == 1
    label = page.evaluate(CS, f"{row} .ca-process__label")
    assert (label["fs"], label["fw"]) == ("13px", "400")
    assert abs(label["left"] - icon["right"] - 6) < 0.5
    assert page.locator(row).inner_text().strip() == "GPT Image Flare"
    assert page.locator(f"{row} [data-testid=process-rail]").count() == 0
    page.close()
