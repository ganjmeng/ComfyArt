"""#145: the cost confirm opened from a reference-mode popover sits on top of it and its buttons are clickable.

Real src/ui/Popover + RefControls + Confirm + src/styles CSS in Chromium; control_preview is mocked (409 -> confirm),
nothing reaches WaveSpeed. Every mode with an extract button is checked (structure + colour).
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")

MODES = ["canny", "lineart", "mlsd", "scribble", "softedge", "depth", "normal", "pose", "seg", "tile", "recolor", "color", "shuffle", "brightness"]
HIT = """() => [...document.querySelectorAll('.ca-modal .ca-panel__foot button')].map((b) => {
  const r = b.getBoundingClientRect(); const e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)
  return { text: b.innerText, hit: !!e && b.contains(e), x: r.x + r.width / 2, y: r.y + r.height / 2 }
})"""


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    d = tmp_path_factory.mktemp("layer")
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/layer/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(f"<!doctype html><style>{css}</style><div id=root></div><script src=app.js></script>")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # browsers not installed
            pytest.skip(f"no chromium: {e}")
        pg = b.new_page(viewport={"width": 1000, "height": 900})
        pg.goto((d / "index.html").as_uri())
        pg.wait_for_selector(".ca-pop .ca-refctl")
        yield pg
        b.close()


def test_every_structure_mode_has_extract(page):
    assert page.evaluate("window.__modes") == MODES


@pytest.mark.parametrize("mode", MODES)
def test_confirm_on_top_of_popover_and_clickable(page, mode):
    page.evaluate(f"window.__calls = []; window.__setMode({mode!r})")
    page.locator(".ca-pop .ca-refctl button.ca-menu__item").click()
    page.wait_for_selector(".ca-modal")
    # the popover is still open underneath and overlaps the dialog
    assert page.locator(".ca-pop").count() == 1
    hits = page.evaluate(HIT)
    assert len(hits) == 2 and all(h["hit"] for h in hits), hits
    assert page.evaluate("window.__calls.filter(c => c.confirmed).length") == 0  # nothing submitted before the answer
    # cancel by a real mouse click at the button's centre: closes the dialog, popover stays, still nothing confirmed
    cancel = hits[0]
    page.mouse.click(cancel["x"], cancel["y"])
    page.wait_for_selector(".ca-modal", state="detached")
    assert page.locator(".ca-pop").count() == 1
    assert page.evaluate("window.__calls.filter(c => c.confirmed).length") == 0
    # extract again and confirm: one confirmed request, preview shown in the still-open popover
    page.locator(".ca-pop .ca-refctl button.ca-menu__item").click()
    page.wait_for_selector(".ca-modal")
    ok = page.evaluate(HIT)[1]
    page.mouse.click(ok["x"], ok["y"])
    page.wait_for_selector(".ca-pop img.ca-refctl__preview")
    assert page.evaluate("window.__calls.filter(c => c.confirmed).length") == 1
