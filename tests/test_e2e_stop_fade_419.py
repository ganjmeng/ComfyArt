"""#419 e2e (Chromium): the post-stop grey hits only the streamed text, never the #391 stop card.

The DOM is the real recovered case-a bot message captured from the running app on main 7e9058f (#391 card with
「继续」, zh, light and dark). It is rendered with main's built CSS (pinned as a tests/fixtures copy, sha256 literal,
so a shallow clone needs no git object) and with ours (dist/), then the computed styles are compared: while
`.ca-chat__bot--stopping` is on, only `.ca-md` (the streamed text) turns grey; the card, the 继续 button and the
billing note keep main's colour and opacity, and after recovery (class removed) they match main."""
import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAIN = "7e9058f"
# #935: main's three built CSS files, concatenated in sorted-name order and captured
# once. The sha256 literal pins the snapshot; no historical git object is opened.
MAIN_CSS = (ROOT / "tests/fixtures/stop_fade_419_main.css").read_text(encoding="utf-8")
MAIN_CSS_SHA256 = "a3ff2904af0613a149e4976d595080ac55c817422efcb77988cd034cb15cf657"
apw = pytest.importorskip("playwright.sync_api")
NOTE = '<div class="ca-chat__hint" data-stopped="submitted">已提交的生成仍会完成并计费</div>'
TEXT = '<div class="ca-md"><p>正在为你生成橘猫海报</p></div>'
PROBE = """() => { const q = (s) => document.querySelector(s); const st = (e) => { const c = getComputedStyle(e);
  return [c.color, c.backgroundColor, c.opacity, c.borderColor] };
  return { card: st(q('.ca-run')), head: st(q('.ca-run__head')), btn: st(q('.ca-run .ca-panel__primary')),
           note: q('[data-stopped]') ? st(q('[data-stopped]')) : null, text: st(q('.ca-md p')),
           muted: getComputedStyle(q('.ca-chat__bot')).getPropertyValue('--ca-muted').trim() } }"""


def css_at(rev):
    """All built stylesheets of a revision (rev=None: the working tree's dist/, else the pinned main copy)."""
    if rev is None:
        return "\n".join(f.read_text() for f in sorted((ROOT / "dist/assets").glob("*.css")))
    assert hashlib.sha256(MAIN_CSS.encode()).hexdigest() == MAIN_CSS_SHA256
    return MAIN_CSS


def page_html(fx, css, cls):
    bot = fx["bot"].replace('class="ca-chat__bot"', f'class="{cls}"', 1)
    bot = re.sub(r'<div class="ca-chat__hint">[^<]*</div>', "", bot)  # main's grey 已终止 line is gone in ours
    bot = bot.replace('<div class="ca-run"', TEXT + '<div class="ca-run"', 1).replace('<div class="ca-chat__acts', NOTE + '<div class="ca-chat__acts', 1)
    for tag, attrs in reversed(fx["anc"]):
        a = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        bot = f"<{tag} {a}>{bot}</{tag}>"
    h = " ".join(f'{k}="{v}"' for k, v in fx["html"].items())
    return f"<!doctype html><html {h}><meta charset=utf-8><style>{css}</style><body>{bot}</body></html>"


@pytest.fixture(scope="module")
def browser():
    with apw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # browsers not installed
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


def probe(browser, html):
    pg = browser.new_page()
    pg.set_content(html)
    r = pg.evaluate(PROBE)
    pg.close()
    return r


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_grey_only_hits_streamed_text_and_card_matches_main(browser, theme):
    fx = json.loads((ROOT / f"tests/fixtures/stop_card_dom_419_{theme}.json").read_text())
    main = probe(browser, page_html(fx, css_at(MAIN), "ca-chat__bot"))
    ours_css = css_at(None)
    after = probe(browser, page_html(fx, ours_css, "ca-chat__bot"))
    fading = probe(browser, page_html(fx, ours_css, "ca-chat__bot ca-chat__bot--stopping"))
    # after recovery: the #391 card and its 继续 button look exactly like main
    for k in ("card", "head", "btn"):
        assert after[k] == main[k], (k, after[k], main[k])
    # while fading: the card, 继续 and the billing note are untouched …
    for k in ("card", "head", "btn", "note"):
        assert fading[k] == after[k], (k, fading[k], after[k])
    # … and only the streamed text is grey
    assert fading["text"][0] != after["text"][0]
    assert after["btn"][0] != after["btn"][1]  # 继续 is never colour-on-same-colour
