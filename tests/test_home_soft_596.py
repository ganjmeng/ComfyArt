"""#596 soft FU — lock tab/chip row geometry + inactive fg .55 (not global --ca-muted)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src/styles/home.css").read_text(encoding="utf-8")


def _rgba(r: int, g: int, b: int, a: str) -> str:
    """Flexible whitespace around commas / alpha for rgba assertions."""
    return rf"rgba\(\s*{r}\s*,\s*{g}\s*,\s*{b}\s*,\s*{a}\s*\)"


def test_tabs_py_and_homechips_top_locked():
    assert re.search(r"--ca-tabs-py:\s*11px\b", CSS)
    assert re.search(r"--ca-homechips-top:\s*44px\b", CSS)


def test_light_inactive_tab_chip_skilltabs_fg_point55():
    light = _rgba(0, 0, 0, r"\.55")
    for tok in ("--ca-tabs-fg", "--ca-chip-fg", "--ca-skilltabs-fg"):
        assert re.search(rf"{re.escape(tok)}:\s*{light}", CSS), tok


def test_dark_host_overrides_inactive_fg_point55():
    block = re.search(
        r':root\[data-theme=["\']dark["\']\]\s*\{([^}]*)\}',
        CSS,
    )
    assert block, "missing :root[data-theme=\"dark\"] host override for #596"
    dark_css = block.group(1)
    # Prefer the early #596 soft-FU block (tabs/chip/skilltabs only); scan all dark
    # host blocks if the first match is unrelated.
    dark_fg = _rgba(255, 255, 255, r"\.55")
    found = {tok: False for tok in ("--ca-tabs-fg", "--ca-chip-fg", "--ca-skilltabs-fg")}
    for m in re.finditer(r':root\[data-theme=["\']dark["\']\]\s*\{([^}]*)\}', CSS):
        body = m.group(1)
        for tok in found:
            if re.search(rf"{re.escape(tok)}:\s*{dark_fg}", body):
                found[tok] = True
    missing = [t for t, ok in found.items() if not ok]
    assert not missing, f"dark host missing .55 for: {missing}"


def test_does_not_require_global_muted_bump():
    """Scoped soft FU: must not rewrite global --ca-muted in home.css for this change."""
    # home.css may *use* var(--ca-muted); it must not *define* --ca-muted to .55.
    assert not re.search(r"--ca-muted:\s*" + _rgba(0, 0, 0, r"\.55"), CSS)
    assert not re.search(r"--ca-muted:\s*" + _rgba(255, 255, 255, r"\.55"), CSS)
