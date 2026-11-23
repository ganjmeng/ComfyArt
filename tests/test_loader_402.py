"""#402 FU(#399): loader default 1200ms + hard cut must be asserted (mutations go red)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "public" / "brand" / "loomi-loader.js"
CSS = ROOT / "public" / "brand" / "loomi-loader.css"


def assert_loader_duration_and_hard_cut(js: str, css: str) -> None:
    """Contract: default play ~1200ms; finish hard-cuts (node remove, no fade-out)."""
    # default duration — JS fallback and CSS variable
    assert re.search(r"durationMs\s*\|\|\s*1200\b", js), "default durationMs must be 1200"
    assert re.search(r"--lm-dur:\s*1200ms\b", css), "CSS --lm-dur default must be 1200ms"
    assert "800" not in re.findall(r"durationMs\s*\|\|\s*(\d+)", js)
    # setTimeout uses that duration (full play before cut)
    assert "setTimeout(" in js and re.search(r"Math\.min\(dur,\s*400\)\s*:\s*dur\)", js), (
        "timer must wait full dur (or min(dur,400) when reduced-motion)"
    )
    # hard cut: remove the node; no fade-out / opacity exit on the overlay
    assert "el.remove()" in js, "hard cut must remove the loader node"
    assert "loomi:loader-done" in js
    finish = re.search(r"function finish\(\)\{([^}]*)\}", js)
    assert finish, "finish() missing"
    body = finish.group(1)
    assert "el.remove()" in body
    assert "opacity" not in body and "fade" not in body.lower()
    # loader root itself must not animate opacity / transition out
    assert not re.search(r"\.lm-loader\{[^}]*\bopacity\b", css)
    assert not re.search(r"\.lm-loader\{[^}]*\btransition\b", css)


def test_loader_default_duration_1200ms_and_hard_cut():
    assert_loader_duration_and_hard_cut(JS.read_text(), CSS.read_text())


def test_mutation_duration_800ms_goes_red():
    """Would go green incorrectly if we only checked asset presence (soft note from #401)."""
    js = JS.read_text().replace("1200", "800")
    css = CSS.read_text().replace("1200", "800")
    with pytest.raises(AssertionError):
        assert_loader_duration_and_hard_cut(js, css)


def test_mutation_removing_hard_cut_goes_red():
    js = JS.read_text().replace("el.remove();", "el.style.opacity='0';")
    css = CSS.read_text()
    with pytest.raises(AssertionError):
        assert_loader_duration_and_hard_cut(js, css)


LOADER_DOM = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const nodes = [];
function makeEl() {
  return {
    removed: false,
    className: '',
    innerHTML: '',
    dataset: {},
    style: { pointerEvents: '', setProperty() {} },
    setAttribute() {},
    addEventListener(type, fn) { this['on' + type] = fn; },
    remove() { this.removed = true; },
  };
}
global.document = {
  createElement: makeEl,
  body: { appendChild(el) { nodes.push(el); } },
  querySelectorAll(sel) {
    return nodes.filter((n) => !n.removed && n.className === 'lm-loader');
  },
};
global.matchMedia = () => ({ matches: false });
global.window = {
  BRAND_CONFIG: { name: 'Loomi', logoSvg: '<svg></svg>' },
  dispatchEvent() {},
};
let now = 5000;
Date.now = () => now;
const timers = [];
global.setTimeout = (fn) => { timers.push(fn); return timers.length; };
eval(src);
const mode = process.argv[3];
const handle = window.LoomiLoader.mount({ waitForReady: true });
const live = () => nodes.filter((n) => !n.removed);
if (mode === 'lost-timer') {
  now += 1200;
  handle.ready();
  if (live().length) process.exit(2);
} else if (mode === 'early-ready') {
  handle.ready();
  if (live().length !== 1) process.exit(3);
  timers.forEach((fn) => fn());
  if (live().length) process.exit(5);
} else {
  process.exit(6);
}
console.log('ok');
"""


def test_ready_cuts_a_lost_timer_and_releases_clicks_early(tmp_path):
    """QA 940 en: the composer was filled, but lm-loader still intercepted clicks for 30s.

    ready() is the app-ready signal. If the animation timer never runs after the
    1200ms window, the overlay must hard-cut. If ready() arrives during the
    animation, clicks pass through and the timer still removes the node.
    """
    import subprocess
    script = tmp_path / "loader-dom.js"
    script.write_text(LOADER_DOM, encoding="utf-8")
    for mode in ("lost-timer", "early-ready"):
        run = subprocess.run(
            ["node", str(script), str(JS), mode],
            capture_output=True, text=True, timeout=20,
        )
        assert run.returncode == 0, (mode, run.returncode, run.stdout, run.stderr)


def test_loomic_mark_leftover_gone():
    """Soft ask from #401 / #402: unused loomic-mark.svg must not ship."""
    assert not (ROOT / "public" / "brand" / "loomic-mark.svg").exists()
    assert not (ROOT / "dist" / "brand" / "loomic-mark.svg").exists()
    # no lingering references outside historical docs
    brand_ts = (ROOT / "src" / "brand.ts").read_text()
    assert "loomic-mark" not in brand_ts
