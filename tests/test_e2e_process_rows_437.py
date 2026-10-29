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


@pytest.mark.parametrize("lang,theme", CASES)
def test_search_card_reference_values(browser, bundle, lang, theme):
    page = _open(browser, bundle, lang, theme)
    card = page.evaluate(CS, "#search .ca-process__card")
    assert card["h"] == 58 and card["minH"] == "56px"
    assert (card["pl"], card["pr"], card["pt"]) == ("12px", "0px", "0px")
    assert card["radius"] == "12px" and card["bw"] == "1px"
    assert card["bc"] == ("rgba(0, 0, 0, 0.1)" if theme == "light" else "rgba(255, 255, 255, 0.1)")
    assert card["bg"] == "rgba(0, 0, 0, 0)" and card["ov"] == "hidden"
    assert card["mt"] == "12px" and card["gap"] == "20px"
    title = page.evaluate(CS, "#search .ca-process__cardtitle")
    assert (title["fs"], title["lh"], title["fw"], title["op"], title["clamp"]) == ("12px", "18px", "400", "0.9", "2")
    assert (title["mt"], title["mb"]) == ("10px", "10px")
    art = page.evaluate(CS, "#search .ca-process__cardart")
    assert (art["w"], art["h"]) == (56, 56)
    assert abs(art["right"] - (card["right"] - 1)) < 0.5  # flush against the right border
    assert abs(art["left"] - page.evaluate("document.querySelector('#search .ca-process__cardtitle').getBoundingClientRect().right")) >= 20 - 0.5
    folder = page.locator("#search .ca-process__cardart svg path").last
    assert folder.get_attribute("fill") == "#fff" and folder.get_attribute("stroke") == "rgba(0,0,0,.1)" and folder.get_attribute("stroke-width") == ".5"
    # favicon blocked → globe only, no empty slot, no broken image
    assert page.locator("[data-testid=search-favicon]").count() == 0
    assert page.evaluate("[...document.images].filter(i => !i.naturalWidth).length") == 0
    assert page.locator("#search .ca-process__row[data-kind=search_pages] .ca-process__icon svg").count() == 1
    # #442 rail: one real 1px element per group, centred on the icon column, 20px below the group top, to the card bottom
    rails = page.locator("#search [data-testid=process-rail]")
    vis = [i for i in range(rails.count()) if rails.nth(i).is_visible()]
    assert len(vis) == 1
    row = page.evaluate(CS, "#search .ca-process__row[data-kind=search_pages]")
    rail = page.evaluate(CS, "#search .ca-process__row[data-kind=search_pages] > [data-testid=process-rail]")
    icon = page.evaluate(CS, "#search .ca-process__row[data-kind=search_pages] .ca-process__icon")
    assert rail["w"] == 1 and abs((rail["left"] + 0.5) - (icon["left"] + icon["w"] / 2)) < 0.01 and icon["w"] == 16
    assert abs(rail["top"] - (row["top"] + 20)) < 0.5 and abs(rail["bottom"] - card["bottom"]) < 0.5
    assert abs(rail["bottom"] - row["bottom"]) < 0.5
    assert page.evaluate("getComputedStyle(document.querySelector('#search [data-testid=process-rail]:not([hidden])')).backgroundColor") == page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--ca-border')").replace(",", ", ").replace("  ", " ").replace(", .", ", 0.")
    # no line above the first row; content column: pt 8, row gap 8, icon 16 + gap 6
    steps = page.evaluate(CS, "#search .ca-process__steps")
    first = page.evaluate(CS, "#search .ca-process__row")
    assert steps["pt"] == "8px" and page.evaluate("getComputedStyle(document.querySelector('#search .ca-process__steps')).rowGap") == "8px"
    assert abs(first["top"] - steps["top"] - 8) < 0.5

    lab = page.evaluate(CS, "#search .ca-process__row[data-kind=search_pages] .ca-process__label")
    assert abs(lab["left"] - icon["right"] - 6) < 0.5
    assert abs(card["left"] - lab["left"]) < 0.5  # card sits in the content column, rail runs beside it
    page.close()


@pytest.mark.parametrize("lang,theme", CASES)
def test_model_row_reference_values(browser, bundle, lang, theme):
    page = _open(browser, bundle, lang, theme)
    row = '#gen .ca-process__row[data-kind=image]'
    icon = page.evaluate(CS, f"{row} .ca-process__icon .ca-icon")
    assert (icon["w"], icon["h"], icon["op"]) == (16, 16, "0.55")
    assert page.locator(f"{row} .ca-process__icon svg").get_attribute("fill") == "currentColor"
    label = page.evaluate(CS, f"{row} .ca-process__label")
    assert (label["fs"], label["fw"]) == ("13px", "400")
    assert abs(label["left"] - icon["right"] - 6) < 0.5
    assert page.locator(row).inner_text().strip() == "GPT Image Flare"
    assert page.locator(f"{row} [data-testid=process-rail]").count() == 0  # no line beside the model-name row
    page.close()
