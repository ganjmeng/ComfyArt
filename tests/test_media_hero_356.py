"""#356 Generating media hero — chat ca-media-hero + canvas ca-gen-frame."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
GEN = (ROOT / "src/shapes/GeneratorShape.tsx").read_text()
BASE = (ROOT / "src/styles/base.css").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
CANVAS = (ROOT / "src/styles/canvas.css").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()


def test_tokens_light_dark() -> None:
    for tok in (
        "--ca-media-hero-bg",
        "--ca-media-hero-radius",
        "--ca-media-hero-ar-image",
        "--ca-media-hero-ar-video",
        "--ca-media-hero-max-h",
        "--ca-gen-frame-bg",
        "--ca-gen-pill-bg",
        "--ca-gen-pill-fg",
    ):
        assert tok in BASE
    assert "#E7E7E7" in BASE
    assert "#CECFD2" in BASE
    # dark overrides present
    assert BASE.count("--ca-media-hero-bg") >= 2
    assert BASE.count("--ca-gen-frame-bg") >= 2
    # video default AR is 1/1 per MEDIA-HERO.md (not 16/9)
    assert "--ca-media-hero-ar-video: 1 / 1" in BASE
    assert "--ca-media-hero-ar-image: 1 / 1" in BASE
    assert "--ca-gen-frame-radius: 0" in BASE  # Ashley: canvas Generating 无圆角


def test_chat_hero_css_flat_no_shimmer() -> None:
    assert ".ca-media-hero" in OVERLAYS
    block = OVERLAYS.split(".ca-media-hero {")[1].split("}")[0]
    assert "ca-shine" not in block
    assert "animation" not in block
    assert "var(--ca-media-hero-bg)" in block
    # #358: left = icon column — do NOT indent past rail via process-col+gutter
    assert "margin-left: calc(var(--ca-process-col)" not in block


def test_chat_hero_wired_image_video_live_only() -> None:
    proc = CHAT.split("function ProcessTimeline")[1].split("\nfunction ")[0]
    assert "ca-media-hero" in proc
    assert "live.kind === 'image'" in proc or 'live.kind === "image"' in proc
    assert "live.kind === 'video'" in proc or 'live.kind === "video"' in proc
    # not a new timeline kind
    assert "'media_hero'" not in CHAT and '"media_hero"' not in CHAT
    assert "processAspectRatio" in CHAT


def test_no_hero_on_code_plan_ask() -> None:
    proc = CHAT.split("function ProcessTimeline")[1].split("\nfunction ")[0]
    # hero gated to image|video only
    assert "mediaHero" in proc
    assert "kind === 'image' || live.kind === 'video'" in proc or "kind === \"image\"" in proc


def test_canvas_no_selection_chrome_while_generating() -> None:
    assert "hideSelectionBoundsFg" in GEN
    assert "hideResizeHandles" in GEN
    assert "hideRotateHandle" in GEN


def test_canvas_gen_frame_flat_pill() -> None:
    assert "ca-gen-frame" in GEN
    assert "ca-gen-frame__pill" in GEN
    assert "taskDetails.generating" in GEN
    assert "ca-gen-frame__pill" in CANVAS
    # no shimmer while running
    running = CANVAS.split(".ca-gen-card[data-running]")[1].split(".ca-gen-ring")[0]
    assert "ca-shine" not in running
    assert "animation: none" in running or "animation:none" in running.replace(" ", "")
    assert "var(--ca-gen-frame-bg)" in running


def test_pill_i18n() -> None:
    assert '"taskDetails.generating": "Generating"' in EN
    assert '"taskDetails.generating": "生成中"' in ZH


def test_coexist_348_shimmer_status() -> None:
    # live title still uses active label (ca-shine via CSS); spine intact
    assert "ca-process__label--active" in CHAT
    assert "ca-process__status" in CHAT
    assert "ca-process__spine" in CHAT


def test_no_status_card_when_media_hero() -> None:
    """Lovart RS/110: image/video live → title then hero; no bordered status between."""
    proc = CHAT.split("function ProcessTimeline")[1].split("\nfunction ")[0]
    assert "live && !mediaHero" in proc
    assert "ca-media-hero" in proc
