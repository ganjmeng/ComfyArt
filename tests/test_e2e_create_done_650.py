"""#650 follow-up e2e: Skill Creator creation-complete state = Lovart gold create-done.png.
Rows 「Skill ready」 → 「Skill Created」, then the skill card (name, description, Preview, Try this skill), then prose.
Optional SHOT_650_DONE=<dir> writes create-done-loomi-{en,zh}.png at the gold viewport (1280×800)."""
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

COPY = {
    "en": {"rows": ["Skill ready", "Skill Created"], "preview": "Preview", "try": "Try this skill"},
    "zh": {"rows": ["技能加载完成", "技能已创建"], "preview": "预览", "try": "试用此技能"},
}


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("createdone650")
    subprocess.run(
        [str(ROOT / "node_modules" / ".bin" / "rolldown"), "-c", "tests/js/createdone650/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0;background:#fff}}{css}</style>"
        f"<div id=root></div><script src=app.js></script>")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
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


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_creation_complete_matches_lovart(browser, bundle, lang):
    page = browser.new_page(viewport={"width": 1280, "height": 800})  # gold create-done.png viewport (1280×800, dpr 1)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    c = COPY[lang]
    rows = page.evaluate("""() => [...document.querySelectorAll('#done .ca-process__row')].map(r => [r.dataset.kind,
      (r.querySelector('.ca-process__label') || r).innerText.replace(/\\s+/g,' ').trim()])""")
    assert rows == [["skill", c["rows"][0]], ["skill_created", c["rows"][1]]], rows
    card = page.get_by_test_id("skill-created-card")
    assert card.count() == 1 and card.get_attribute("data-skill") == "zz-test-delete"
    assert page.get_by_test_id("skill-created-name").inner_text() == "zz-test-delete"
    assert page.get_by_test_id("skill-created-desc").inner_text() == "A throwaway test skill"
    assert page.get_by_test_id("skill-created-preview").inner_text() == c["preview"]
    assert page.get_by_test_id("skill-created-try").inner_text() == c["try"]
    # order: rail → card → prose (gold), and buttons sit on the card's right, Preview left of Try
    order = page.evaluate("""() => {
      const r = el => el.getBoundingClientRect()
      const rail = document.querySelector('#done .ca-process__row:last-child'), card = document.querySelector('[data-testid=skill-created-card]')
      const prose = [...document.querySelectorAll('#done *')].find(e => e.children.length === 0 && /Created the minimal/.test(e.textContent))
      const p = document.querySelector('[data-testid=skill-created-preview]'), t = document.querySelector('[data-testid=skill-created-try]')
      return [r(rail).bottom <= r(card).top, r(card).bottom <= r(prose).top, r(p).right <= r(t).left, r(t).right <= r(card).right]
    }""")
    assert order == [True, True, True, True], order
    if os.environ.get("SHOT_650_DONE"):
        page.screenshot(path=f"{os.environ['SHOT_650_DONE']}/create-done-v2-loomi-{lang}.png")
    page.close()


FB = {"en": ("Helpful", "Not helpful"), "zh": ("有帮助", "没帮助")}


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_creator_bubble_sizes_and_feedback_match_gold(browser, bundle, lang):
    """v2: creator user block full-width/left/inline 11px; rows, card, buttons and prose at the gold capture's sizes;
    👍/👎 under the prose, mutually exclusive, local state only."""
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    g = page.evaluate("""() => {
      const q = s => document.querySelector(s), r = el => el.getBoundingClientRect(), cs = el => getComputedStyle(el)
      const chat = q('[data-testid=chat]'), bub = q('[data-testid=user-bubble]'), chip = q('[data-testid=user-skill-chip]')
      const txt = q('[data-testid=user-bubble-text]'), card = q('[data-testid=skill-created-card]')
      const prose = [...document.querySelectorAll('#done .ca-md')].at(-1), fb = q('[data-testid=chat-done-feedback]')
      const cr = r(chat), br = r(bub), chr = r(chip), tr = txt.getClientRects()
      return {
        userCls: q('.ca-chat__user').className, bubW: Math.round(br.width), chatW: Math.round(cr.width - parseFloat(cs(chat).paddingLeft) - parseFloat(cs(chat).paddingRight)),
        bubLeft: Math.round(br.left - cr.left - parseFloat(cs(chat).paddingLeft)), align: cs(bub).textAlign, display: cs(bub).display,
        bubFont: cs(bub).fontSize, bubLH: cs(bub).lineHeight, txtFont: cs(txt).fontSize,
        chipInline: Math.abs(r(chip).top - tr[0].top) <= 2 && chr.right <= tr[0].left, wrapsUnderChip: [...tr].filter(x => x.width > 0 && x.top > tr[0].top + 5).every(x => Math.round(x.left) < Math.round(chr.right)), lines: tr.length,
        chipBorder: cs(chip).borderTopStyle, chipH: Math.round(chr.height),
        rowColor: [...document.querySelectorAll('#done .ca-process__label'), ...document.querySelectorAll('#done .ca-process__icon')].map(e => cs(e).color),
        descColor: cs(q('[data-testid=skill-created-desc]')).color,
        rowFont: [...document.querySelectorAll('#done .ca-process__label')].map(e => cs(e).fontSize),
        rowStep: Math.round(r(document.querySelectorAll('#done .ca-process__row')[1]).top - r(document.querySelectorAll('#done .ca-process__row')[0]).top),
        cardH: Math.round(r(card).height), thumb: [Math.round(r(q('.ca-chat__skillcard-thumb')).width), Math.round(r(q('.ca-chat__skillcard-thumb')).height)],
        name: cs(q('[data-testid=skill-created-name]')).fontSize, desc: cs(q('[data-testid=skill-created-desc]')).fontSize,
        btn: [...card.querySelectorAll('button')].map(b => [cs(b).fontSize, Math.round(r(b).height)]),
        prose: cs(prose).fontSize, proseBubSame: cs(prose).fontSize === cs(bub).fontSize,
        fbBelow: r(fb).top >= r(prose).bottom, fbLeft: Math.round(r(fb).left - r(prose).left),
        icons: [...fb.querySelectorAll('.ca-icon')].map(i => Math.round(r(i).width)),
      }
    }""")
    assert "ca-chat__user--creator" in g["userCls"]
    assert g["bubW"] == g["chatW"] and g["bubLeft"] == 0, g
    assert g["align"] == "left" and g["display"] == "block", g
    assert (g["bubFont"], g["bubLH"], g["txtFont"]) == ("11px", "19px", "11px"), g
    assert g["chipInline"] and g["wrapsUnderChip"], g
    assert g["chipBorder"] == "solid" and g["chipH"] == 19, g
    assert len(g["rowColor"]) == 4 and all(c == g["descColor"] for c in g["rowColor"]), g
    assert g["descColor"] == "rgba(0, 0, 0, 0.5)", g
    assert g["rowFont"] == ["11px", "11px"] and g["rowStep"] == 20, g
    assert g["cardH"] == 46 and g["thumb"] == [50, 36], g
    assert (g["name"], g["desc"]) == ("11px", "10px"), g
    assert g["btn"] == [["10px", 18], ["10px", 18]], g
    assert g["prose"] == "11px" and g["proseBubSame"], g
    assert g["fbBelow"] and g["fbLeft"] == 0 and g["icons"] == [12, 12], g
    up, down = page.get_by_test_id("chat-feedback-up"), page.get_by_test_id("chat-feedback-down")
    assert (up.get_attribute("aria-label"), down.get_attribute("aria-label")) == FB[lang]
    color = lambda el: el.evaluate("e => getComputedStyle(e).color")
    idle = color(up)
    assert color(down) == idle
    state = lambda: [up.get_attribute("aria-pressed"), down.get_attribute("aria-pressed")]
    assert state() == ["false", "false"]
    up.click(); assert state() == ["true", "false"] and color(up) != idle
    down.click(); assert state() == ["false", "true"] and color(up) == idle
    down.click(); assert state() == ["false", "false"]
    page.close()
