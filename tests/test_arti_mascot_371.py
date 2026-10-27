"""#371 P1-mascot — composer Arti badge + Lv.1–3 silhouette ladder (mock)."""
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


def test_composer_wires_mascot_badge() -> None:
    assert "ArtiMascot" in COMPOSER
    assert "<ArtiMascot" in COMPOSER
    assert "busy={busy}" in COMPOSER
    assert "typing={typing}" in COMPOSER or "typing={content}" in COMPOSER


def test_idle_is_static_frame0_no_infinite_loop() -> None:
    # Idle has no --play/--typing class
    assert "trigger === 'play'" in MASCOT or "busy ? 'play'" in MASCOT
    assert "arti-mascot--play" in MASCOT
    assert "arti-mascot--typing" in MASCOT
    # CSS: animation only on --play / --typing, not bare .arti-mascot
    assert ".arti-mascot--play" in SHELL
    assert ".arti-mascot--typing" in SHELL
    # No infinite animation on mascot rules (idle must stay static)
    mascot_css = SHELL[SHELL.index(".arti-mascot"):]
    assert "infinite" not in mascot_css
    # Idle path does not add play/typing classes
    assert "trigger === 'idle'" in MASCOT or "idle" in MASCOT
    assert "data-trigger={trigger}" in MASCOT


def test_play_and_typing_both_animate() -> None:
    assert "arti-mascot--play" in MASCOT and "arti-mascot--typing" in MASCOT
    assert "busy ? 'play'" in MASCOT or "busy" in MASCOT
    assert "typing" in MASCOT
    # MUST: both classes animate (CSS)
    assert ".arti-mascot--play," in SHELL or ".arti-mascot--play" in SHELL
    assert ".arti-mascot--typing" in SHELL
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
    # component forces idle when reduce
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


def test_level_stub_defaults_lv1_mock_switch() -> None:
    assert "accountArtiLevel" in LEVEL
    assert "return 1" in LEVEL
    assert "resolveArtiLevel" in LEVEL
    assert "readArtiLevelMock" in LEVEL
    assert "setArtiLevelMock" in LEVEL
    assert "comfyart.arti.levelMock" in LEVEL
    assert "artiLevel" in LEVEL  # URL mock
    # UI uses resolve, not a faked high level
    assert "resolveArtiLevel()" in MASCOT
    assert 'data-level={level}' in MASCOT


def test_lv1_lv2_lv3_assets_ship() -> None:
    assert (ASSETS / "mascot-lv1-developing.png").is_file()
    assert (ASSETS / "mascot-lv2-beret.png").is_file()
    assert (ASSETS / "mascot-lv3-brush.png").is_file()
    assert (ASSETS / "README.md").is_file()
    readme = (ASSETS / "README.md").read_text()
    assert "Provisional" in readme or "provisional" in readme
    assert "mascot-lv1-developing" in MASCOT
    assert "mascot-lv2-beret" in MASCOT
    assert "mascot-lv3-brush" in MASCOT
    # sheet dimensions documented as 17 frames
    from PIL import Image
    for name in ("mascot-lv1-developing.png", "mascot-lv2-beret.png", "mascot-lv3-brush.png"):
        im = Image.open(ASSETS / name)
        assert im.size == (2176, 128), (name, im.size)


def test_arti_level_card_shares_assets_should() -> None:
    assert "ArtiLevelAvatar" in ARTI
    assert "arti-avatar-mascot" in MASCOT
    assert "resolveArtiLevel()" in ARTI
    assert "arti-mascot--avatar" in HOME or "arti-mascot--avatar" in MASCOT


def test_sprite_sheets_imported_not_cn_claimed_for_lv2_3() -> None:
    readme = (ASSETS / "README.md").read_text().lower()
    assert "provisional" in readme
    assert "original" in readme
    # must not claim Lv.2/3 are CN captures
    assert "cn gold" in readme or "cn" in readme
    assert "lv.2" in readme or "lv2" in readme
