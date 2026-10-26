"""#337 remaining 1:1 pixel locks (post-#338 baseline)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "src/styles/base.css").read_text()
OVER = (ROOT / "src/styles/overlays.css").read_text()
SHELL = (ROOT / "src/styles/shell.css").read_text()
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()


def test_block_gap_8() -> None:
    assert "--ca-block-gap: 8px;" in BASE
    assert "--ca-block-gap: 10px;" not in BASE


def test_local_q_shadow_not_global_float() -> None:
    assert "--ca-q-shadow: 0 1px 2px rgba(0,0,0,.04), 0 2px 8px rgba(0,0,0,.05);" in BASE
    assert "--ca-q-shadow: 0 2px 10px rgba(0,0,0,.45);" in BASE
    # .ca-q uses local shadow token
    assert "box-shadow: var(--ca-q-shadow" in OVER
    # do not change global float stack for other floats
    assert "--ca-shadow-float: var(--ca-shadow);" in BASE


def test_header_footer_optical() -> None:
    assert ".ca-q__label" in OVER and "font-weight: 500" in OVER.split(".ca-q__label")[1].split("{")[1].split("}")[0]
    assert "width: 18px; height: 18px" in OVER.split(".ca-q__chev {")[1].split("}")[0]
    assert ".ca-q__chev-icon { width: 12px; height: 12px; }" in OVER
    assert ".ca-q__chev:disabled { opacity: .3;" in OVER
    foot = OVER.split(".ca-q__foot {")[1].split("}")[0]
    assert "gap: 6px" in foot
    submit = OVER.split(".ca-q__submit {")[1].split("}")[0]
    assert "font: 600 12px/16px" in submit
    skip = OVER.split(".ca-q__skip {")[1].split("}")[0]
    assert "font: 400 12px/16px" in skip


def test_flat_unselected_still_transparent() -> None:
    opt = OVER.split("/* Unselected A–D")[1].split(".ca-q__opt[data-on]")[0]
    assert "background: transparent" in opt
    assert "--ca-field" not in opt.split(".ca-q__opt {")[1].split("}")[0]


def test_opt_h_28_locked() -> None:
    assert "--ca-opt-h: 28px;" in BASE


def test_next_submit_text_glyphs() -> None:
    # Next uses text →; Submit uses text ↵ — not oversized SVG key-icon
    assert 'ca-q__key">→</span>' in CHAT
    assert 'ca-q__key">↵</span>' in CHAT
    assert "ca-q__key-icon" not in CHAT


def test_multi_hint_class() -> None:
    assert 'className="ca-q__hint"' in CHAT
    assert ".ca-q__hint" in OVER


def test_chat_pad_optional_tighten() -> None:
    # optional pad-inline 12–16 (landed 14)
    assert "padding: 8px 14px 16px" in SHELL


def test_no_entrance_animation_on_q() -> None:
    q = OVER.split(".ca-q {")[1].split(".ca-q__head")[0]
    assert "animation" not in q and "@keyframes" not in OVER.split("/* #328/#335/#337 Question")[1].split(".ca-memory")[0]


def test_letter_tokens_340_lock() -> None:
    """#340: soft letter-on (.55) + dark fg; unselected --ca-letter/.06 + .45; ban #1a1a1a+white."""
    assert "--ca-letter: rgba(0,0,0,.06);" in BASE
    assert "--ca-letter-fg: rgba(0,0,0,.45);" in BASE
    assert "--ca-letter-on: rgba(0,0,0,.55);" in BASE
    assert "--ca-letter-on-fg: var(--ca-text);" in BASE
    assert "--ca-opt-on: #ebebeb;" in BASE
    # dark
    assert "--ca-letter: rgba(255,255,255,.08);" in BASE
    assert "--ca-letter-fg: rgba(255,255,255,.45);" in BASE
    assert "--ca-letter-on: rgba(255,255,255,.22);" in BASE
    assert "--ca-letter-on-fg: var(--ca-text);" in BASE
    assert "--ca-opt-on: rgba(255,255,255,.12);" in BASE

    letter = OVER.split(".ca-q__letter {")[1].split("}")[0]
    assert "background: var(--ca-letter)" in letter
    assert "color: var(--ca-letter-fg)" in letter
    assert "var(--ca-active)" not in letter
    assert "var(--ca-muted)" not in letter

    on = OVER.split(".ca-q__opt[data-on] .ca-q__letter")[1].split("}")[0]
    assert "background: var(--ca-letter-on)" in on
    assert "color: var(--ca-letter-on-fg)" in on
    # ban white-on-#1a1a1a selected letter
    assert "#1a1a1a" not in on
    assert "#fff" not in on and "white" not in on.lower()
    assert "color: #fff" not in OVER.split("/* #328/#335/#337 Question")[1].split(".ca-memory")[0]

    # selected row soft only via --ca-opt-on; no --ca-strong border
    on_row = OVER.split(".ca-q__opt[data-on] {")[1].split("}")[0]
    assert "background: var(--ca-opt-on)" in on_row
    assert "--ca-strong" not in on_row


def test_multi_block_page_chrome() -> None:
    """#340 Scope B: questions[] → multiple .ca-q__block + pager + mid-page Next."""
    assert "onPage.map((q) => (" in CHAT
    assert 'className="ca-q__block"' in CHAT
    assert "showPager" in CHAT and "ca-q__page" in CHAT
    assert "chatMessage.next" in CHAT
    assert "chatMessage.submit" in CHAT
    assert "isLast ?" in CHAT
