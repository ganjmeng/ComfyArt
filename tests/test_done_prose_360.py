"""#360 Done next-step: prose + 👍, no suggestion chips."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
GUIDE = (ROOT / "bot/guide.py").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()
ICONS = (ROOT / "src/ui/icons.tsx").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
AGENT = (ROOT / "src/ui/AgentPanel.tsx").read_text()


def test_guide_requires_prose_forbids_chips() -> None:
    assert "prose next-step" in GUIDE
    assert "下一步建议" in GUIDE
    assert "suggestion chips" in GUIDE
    assert "never call ask_user" in GUIDE


def test_done_feedback_wired_under_assistant_blocks() -> None:
    assert "function DoneFeedback" in CHAT
    assert "isMediaDoneMessage" in CHAT
    assert "ca-chat__feedback" in CHAT
    assert "m.status === 'done' && isMediaDoneMessage(m)" in CHAT
    assert "Icons.thumbsUp" in CHAT
    assert "Icons.thumbsDown" in CHAT


def test_icons_have_thumbs() -> None:
    assert "thumbsUp:" in ICONS
    assert "thumbsDown:" in ICONS


def test_feedback_css_quiet_outline() -> None:
    assert ".ca-chat__feedback" in OVERLAYS
    assert ".ca-chat__fb" in OVERLAYS


def test_no_suggestion_chip_row_on_done_path() -> None:
    """AssistantBlocks must not render a suggestion chip/pill row for Done."""
    ab = CHAT.split("export function AssistantBlocks")[1].split("\nexport function ")[0]
    assert "ca-panel__chips" not in ab
    assert "ca-gen__chips" not in ab
    assert "ca-composer__suggest" not in ab
    assert "done-suggest" not in ab
    assert "suggestionChips" not in ab
    assert "DoneFeedback" in ab
    assert "function DoneFeedback" in CHAT
    assert "ca-chat__feedback" in CHAT
    assert "NEVER a suggestion chip" in ab


def test_i18n_thumbs() -> None:
    assert '"chatMessage.thumbsUp": "Thumbs up"' in EN
    assert '"chatMessage.thumbsDown": "Thumbs down"' in EN
    assert '"chatMessage.thumbsUp"' in ZH
    assert '"chatMessage.thumbsDown"' in ZH


def test_media_hero_untouched() -> None:
    """#360 must not regress #356/#358 media hero."""
    assert "ca-media-hero" in CHAT
    assert "mediaHero" in CHAT
    hero = OVERLAYS.split(".ca-media-hero {")[1].split("}")[0]
    assert "calc(var(--ca-process-col)" not in hero


def test_no_composer_done_suggestion_chips() -> None:
    """Placement is chat message flow — not composer chips for Done."""
    assert "done-suggest" not in AGENT
    assert "doneSuggest" not in AGENT
    assert "下一步建议" not in AGENT
