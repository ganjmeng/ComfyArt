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


def test_loomic_mark_leftover_gone():
    """Soft ask from #401 / #402: unused loomic-mark.svg must not ship."""
    assert not (ROOT / "public" / "brand" / "loomic-mark.svg").exists()
    assert not (ROOT / "dist" / "brand" / "loomic-mark.svg").exists()
    # no lingering references outside historical docs
    brand_ts = (ROOT / "src" / "brand.ts").read_text()
    assert "loomic-mark" not in brand_ts
