"""#358 chat media-hero left edge = ProcessTimeline icon column (not label column)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
BASE = (ROOT / "src/styles/base.css").read_text()


def _hero_block() -> str:
    assert ".ca-media-hero {" in OVERLAYS
    return OVERLAYS.split(".ca-media-hero {")[1].split("}")[0]


def test_hero_not_indented_past_icon_rail() -> None:
    """AC amend: hero left = icon column left (Lovart), NOT label/text column."""
    block = _hero_block()
    # Old #356 rule indented past icon rail + spine/gutter — must be gone
    assert "calc(var(--ca-process-col) + var(--ca-process-gutter))" not in block
    assert "margin-left: 0" in block
    # Numeric AC: tip 812ea12 was +27..+28px (process-col 16 + gutter 12);
    # margin-left:0 → hero−icon = 0±2 (Lovart)
    # Status/detail still indent to label column (unchanged)
    assert "margin-left: calc(var(--ca-process-col) + var(--ca-process-gutter));" in OVERLAYS
    status = OVERLAYS.split(".ca-process__status {")[1].split("}")[0]
    assert "calc(var(--ca-process-col) + var(--ca-process-gutter))" in status


def test_hero_still_full_width_tokens() -> None:
    """Width still fills content column (100% / clamp); AR + canvas radius untouched."""
    block = _hero_block()
    assert "var(--ca-media-hero-width)" in block
    assert "var(--ca-media-hero-max-h)" in block
    assert "--ca-media-hero-ar-image: 1 / 1" in BASE
    assert "--ca-media-hero-ar-video: 1 / 1" in BASE
    assert "--ca-gen-frame-radius: 0" in BASE


def test_no_status_card_when_media_hero_untouched() -> None:
    proc = CHAT.split("function ProcessTimeline")[1].split("\nfunction ")[0]
    assert "live && !mediaHero" in proc
    assert "ca-media-hero" in proc


def test_comments_void_past_rail_ac() -> None:
    """#358 comment locks icon-column align; voids old past-rail / label-column AC."""
    idx = OVERLAYS.find("#358 chat media hero")
    assert idx >= 0
    snippet = OVERLAYS[idx : idx + 280].lower()
    assert "icon column" in snippet or "icon rail" in snippet
    assert "not label" in snippet or "not past" in snippet or "not indented" in snippet
    # hero rule itself must not reintroduce past-rail indent
    assert "calc(var(--ca-process-col) + var(--ca-process-gutter))" not in _hero_block()
