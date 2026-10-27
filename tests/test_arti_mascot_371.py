"""#371 P1-mascot — composer Arti DNA A badge + hover/click notify + Lv.1–3 ladder (mock)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()
MASCOT = (ROOT / "src/ui/ArtiMascot.tsx").read_text()
LEVEL = (ROOT / "src/artiLevel.ts").read_text()
ARTI = (ROOT / "src/home/Arti.tsx").read_text()
SHELL = (ROOT / "src/styles/shell.css").read_text()
HOME = (ROOT / "src/styles/home.css").read_text()
ASSETS = ROOT / "src/assets/arti"
ZH = (ROOT / "src/locales/zh.json").read_text()
EN = (ROOT / "src/locales/en.json").read_text()


def test_composer_wires_mascot_badge() -> None:
    assert "ArtiMascot" in COMPOSER
    assert "<ArtiMascot" in COMPOSER
    assert "busy={busy}" in COMPOSER
    assert "typing={typing}" in COMPOSER or "typing={content}" in COMPOSER


def test_idle_is_static_frame0_no_infinite_loop() -> None:
    assert "trigger === 'play'" in MASCOT or "busy ? 'play'" in MASCOT or "busy" in MASCOT
    assert "arti-mascot--play" in MASCOT
    assert "arti-mascot--typing" in MASCOT
    assert ".arti-mascot--play" in SHELL
    assert ".arti-mascot--typing" in SHELL
    mascot_css = SHELL[SHELL.index(".arti-mascot"):]
    assert "infinite" not in mascot_css
    assert "data-trigger={trigger}" in MASCOT


def test_play_and_typing_both_animate() -> None:
    assert "arti-mascot--play" in MASCOT and "arti-mascot--typing" in MASCOT
    assert "busy" in MASCOT and "typing" in MASCOT
    assert "arti-mascot-play" in SHELL
    assert "steps(var(--mascot-frames" in SHELL or "steps(" in SHELL


def test_timing_17_frames_250ms() -> None:
    assert "MASCOT_FRAMES = 17" in LEVEL
    assert "MASCOT_FRAME_MS = 250" in LEVEL
    assert "data-frames={MASCOT_FRAMES}" in MASCOT
    assert "data-frame-ms={MASCOT_FRAME_MS}" in MASCOT
    assert "4250" in LEVEL or "MASCOT_FRAMES * MASCOT_FRAME_MS" in LEVEL


def test_reduced_motion_stays_frame0() -> None:
    assert "prefers-reduced-motion" in MASCOT or "prefers-reduced-motion" in SHELL
    assert "prefers-reduced-motion: reduce" in SHELL
    assert "animation: none" in SHELL
    assert "transform: none" in SHELL  # no hover lift under reduce
    assert "reduce ? 'idle'" in MASCOT or "useReducedMotion" in MASCOT


def test_placement_attrs_left_top_peek() -> None:
    assert "left: 12px" in SHELL
    assert "top: -22px" in SHELL or "bottom: -22px" in SHELL
    assert "width: 50px" in SHELL
    assert "height: 50px" in SHELL
    assert "image-rendering: pixelated" in SHELL
    assert "crisp-edges" in SHELL
    assert 'data-testid="arti-mascot"' in MASCOT
    assert "data-level={level}" in MASCOT


def test_hover_lift_and_play() -> None:
    assert "arti-mascot--hover" in MASCOT
    assert "arti-mascot--hover" in SHELL
    assert "translateY(-11px)" in SHELL
    assert "onMouseEnter" in MASCOT
    assert "onMouseLeave" in MASCOT
    assert "hovering" in MASCOT or "hover" in MASCOT


def test_click_opens_arti_notify_not_route() -> None:
    assert "arti-notify" in MASCOT
    assert 'data-testid="arti-notify"' in MASCOT
    assert "arti.notify.title" in MASCOT
    assert "arti.notify.empty" in MASCOT
    assert "arti.notify.emptyHint" in MASCOT
    assert "useEscape" in MASCOT
    assert "setNotifyOpen" in MASCOT
    # MUST NOT navigate to /arti on badge click
    assert "/arti" not in MASCOT or "not /arti" in MASCOT.lower() or "≠ `/arti`" in MASCOT or "not `/arti`" in MASCOT or "NOT /arti" in MASCOT or "(not /arti)" in MASCOT
    assert "openView" not in MASCOT
    assert "navigate(" not in MASCOT
    assert "href=" not in MASCOT or 'href="/arti"' not in MASCOT
    assert ".arti-notify" in SHELL


def test_notify_empty_copy_locale_keys() -> None:
    assert '"arti.notify.title": "Arti 通知"' in ZH
    assert '"arti.notify.empty": "暂无新通知"' in ZH
    assert '"arti.notify.emptyHint": "使用 Agent 创作后，解锁巡检和调研功能"' in ZH
    assert '"arti.notify.title"' in EN
    assert '"arti.notify.empty"' in EN
    assert '"arti.notify.emptyHint"' in EN
    assert "暂无新通知" in ZH
    assert "使用 Agent 创作后，解锁巡检和调研功能" in ZH


def test_level_stub_defaults_lv1_mock_switch() -> None:
    assert "accountArtiLevel" in LEVEL
    assert "return 1" in LEVEL
    assert "resolveArtiLevel" in LEVEL
    assert "readArtiLevelMock" in LEVEL
    assert "setArtiLevelMock" in LEVEL
    assert "comfyart.arti.levelMock" in LEVEL
    assert "artiLevel" in LEVEL
    assert "resolveArtiLevel()" in MASCOT
    assert "data-level={level}" in MASCOT


def test_lv1_lv2_lv3_dna_a_assets_ship() -> None:
    assert (ASSETS / "mascot-lv1-dna-a.png").is_file()
    assert (ASSETS / "mascot-lv2-dna-a.png").is_file()
    assert (ASSETS / "mascot-lv3-dna-a.png").is_file()
    assert (ASSETS / "README.md").is_file()
    # VOID ghost / provisional ghost filenames must be gone
    assert not (ASSETS / "mascot-lv1-developing.png").exists()
    assert not (ASSETS / "mascot-lv2-beret.png").exists()
    assert not (ASSETS / "mascot-lv3-brush.png").exists()
    readme = (ASSETS / "README.md").read_text()
    assert "DNA A" in readme
    assert "cream" in readme.lower() or "奶油" in readme or "dumpling" in readme.lower()
    assert "VOID" in readme or "ghost" in readme.lower()
    assert "mascot-lv1-dna-a" in MASCOT
    assert "mascot-lv2-dna-a" in MASCOT
    assert "mascot-lv3-dna-a" in MASCOT
    assert "mascot-lv1-developing" not in MASCOT
    assert "mascot-lv2-beret" not in MASCOT
    assert "mascot-lv3-brush" not in MASCOT
    from PIL import Image
    for name in ("mascot-lv1-dna-a.png", "mascot-lv2-dna-a.png", "mascot-lv3-dna-a.png"):
        im = Image.open(ASSETS / name)
        assert im.size == (2176, 128), (name, im.size)


def test_arti_level_card_shares_assets_should() -> None:
    assert "ArtiLevelAvatar" in ARTI
    assert "arti-avatar-mascot" in MASCOT
    assert "resolveArtiLevel()" in ARTI
    assert "arti-mascot--avatar" in HOME or "arti-mascot--avatar" in MASCOT


def test_no_white_ghost_claimed_as_gold() -> None:
    readme = (ASSETS / "README.md").read_text().lower()
    assert "dna a" in readme
    assert "ghost" in readme  # documented as VOID / ≠ ghost
    assert "developing-sprite" not in MASCOT
    assert "mascot-lv1-developing" not in SHELL
    # mutation: ghost filenames must not reappear under assets
    ghosts = list(ASSETS.glob("*developing*")) + list(ASSETS.glob("*beret*")) + list(ASSETS.glob("*brush*"))
    assert ghosts == [], ghosts


def _rule(sel: str) -> str:
    i = SHELL.index(sel + " {")
    return SHELL[i:SHELL.index("}", i)]


def test_371fix_mascot_behind_composer_surface() -> None:
    """Lovart parity: composer opaque surface (z1) covers mascot lower body (z0); head peeks above rim."""
    assert "isolation: isolate" in SHELL[SHELL.index(".ca-composer { overflow: visible"):][:120]
    surf = _rule(".ca-composer::before")
    assert "background: var(--ca-float)" in surf and "z-index: 1" in surf
    assert "pointer-events: none" in surf  # surface never eats mascot clicks
    wrap = _rule(".arti-mascot-wrap")
    assert "z-index: 2" not in wrap and "z-index: auto" in wrap
    assert "top: -22px" in wrap and "left: 12px" in wrap
    m = _rule(".arti-mascot")
    assert "z-index: 0" in m and "pointer-events: auto" in m
    assert ".ca-composer > :not(.arti-mascot-wrap) { position: relative; z-index: 2; }" in SHELL
    # 50px tall at top -22 → 28px below rim hidden by the surface, 22px head peeks (more on 11px hover lift)
    assert "translateY(-11px)" in SHELL
    assert "z-index: 5" in _rule(".arti-notify")  # popover stays above surface


def test_375_notify_popover_opens_above_composer() -> None:
    """Popover bottom must be <= composer top: anchored by bottom above the mascot wrap (which peeks above the rim)."""
    rule = _rule(".arti-notify")
    assert "bottom: calc(100% + 1px + 8px)" in rule
    assert "top: auto" in rule
    assert "top: calc(100%" not in rule
    assert "z-index: 5" in rule
    # wrap peeks above rim (top -22px), so wrap-top - 8px is strictly above the composer top edge
    import re
    m = re.search(r"top:\s*(-\d+)px", _rule(".arti-mascot-wrap"))
    assert m and int(m.group(1)) <= 0


def test_376_notify_panel_lovart_1to1() -> None:
    """#376: panel is a composer child spanning full composer width, 8px above top, z5, title ⚡, close ×, centered icon + 2 lines."""
    rule = _rule(".ca-composer > .arti-notify,\n.arti-notify")
    # width == composer width: absolute in composer, left 0 / right 0, border-box, auto width
    for decl in ("position: absolute", "left: -1px", "right: -1px", "width: auto", "box-sizing: border-box"):
        assert decl in rule, decl
    # bottom above composer top (8px gap), never top-anchored
    assert "bottom: calc(100% + 1px + 8px)" in rule and "top: auto" in rule
    assert "z-index: 5" in rule
    # panel rendered OUTSIDE the 50px mascot wrap (sibling in composer), so containing block is the composer
    wrap_close = MASCOT.index("</span>\n    {/* #376")
    assert MASCOT.index('data-testid="arti-notify"') > wrap_close
    # title / close / centered icon + two lines via locale keys
    assert "t('arti.notify.heading')" in MASCOT
    assert 'data-testid="arti-notify-close"' in MASCOT
    assert "onClick={() => setNotifyOpen(false)}" in MASCOT
    assert "t('arti.notify.close')" in MASCOT
    assert 'data-testid="arti-notify-icon"' in MASCOT
    assert "t('arti.notify.empty')" in MASCOT and "t('arti.notify.emptyHint')" in MASCOT
    assert '"arti.notify.heading": "Arti 通知 ⚡"' in ZH
    assert '"arti.notify.close": "关闭"' in ZH
    assert '"arti.notify.heading"' in EN and '"arti.notify.close"' in EN
    empty = _rule(".arti-notify__empty")
    assert "align-items: center" in empty and "text-align: center" in empty
    # outside-click must not treat clicks inside the panel as outside
    assert "panel.contains(tgt)" in MASCOT
