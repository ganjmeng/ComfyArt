"""#364 Agent「审核」toggle + Done post-image review thought (mock)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = (ROOT / "api/settings.py").read_text()
BOT_SETTINGS = (ROOT / "src/ui/BotSettings.tsx").read_text()
GUIDE = (ROOT / "bot/guide.py").read_text()
BOT_SEND = (ROOT / "api/bot_send.py").read_text()
BOT = (ROOT / "api/bot.py").read_text()
CHAT = (ROOT / "src/ui/ChatMessage.tsx").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
AGENT = (ROOT / "src/ui/AgentPanel.tsx").read_text()
OVERLAYS = (ROOT / "src/styles/overlays.css").read_text()


def test_default_review_on_in_settings_spec() -> None:
    assert '"bot-enable-review": True' in SETTINGS


def test_botsettings_has_review_toggle_row() -> None:
    assert 'data-testid="botsettings-review"' in BOT_SETTINGS
    assert 'data-testid="bot-enable-review"' in BOT_SETTINGS
    assert "bot-enable-review" in BOT_SETTINGS
    assert "botSettings.review" in BOT_SETTINGS
    # Default ON: checked when value is not false
    assert "draft['bot-enable-review'] !== false" in BOT_SETTINGS
    # Match existing Agent settings switch row styling
    assert 'className="ca-notice__push"' in BOT_SETTINGS


def test_i18n_review_keys() -> None:
    assert '"botSettings.review": "Review"' in EN
    assert '"botSettings.reviewDesc"' in EN
    assert '"botSettings.review": "审核"' in ZH
    assert '"botSettings.reviewDesc"' in ZH


def test_guide_review_on_off_paths() -> None:
    assert "Review (审核)" in GUIDE or "[Review: ON]" in GUIDE
    assert "实质审图" in GUIDE
    assert "When Review is OFF" in GUIDE
    assert "skip that post-image review thinking block" in GUIDE
    assert "prose next-step" in GUIDE
    assert "suggestion chips" in GUIDE
    assert "never call ask_user" in GUIDE


def test_compose_injects_review_flag() -> None:
    assert "review: bool | None = None" in BOT_SEND
    assert "[Review:" in BOT_SEND and "'ON' if review else 'OFF'" in BOT_SEND
    assert "get_setting" in BOT
    assert 'get_setting("bot-enable-review")' in BOT
    assert "review=review_on" in BOT


def test_compose_provider_text_review_on_off() -> None:
    """Exec compose_provider_text alone — avoid full ComfyArt import (sqlalchemy)."""
    import re
    src = BOT_SEND
    m = re.search(r"^def compose_provider_text\(.*?(?=^def )", src, re.M | re.S)
    assert m, "compose_provider_text not found"
    ns: dict = {}
    exec(m.group(0), ns)  # noqa: S102 — test harness
    compose_provider_text = ns["compose_provider_text"]
    on = compose_provider_text("draw a cat", review=True)
    off = compose_provider_text("draw a cat", review=False)
    bare = compose_provider_text("draw a cat")
    assert on.startswith("[Review: ON]")
    assert off.startswith("[Review: OFF]")
    assert "[Review:" not in bare
    assert "draw a cat" in on and "draw a cat" in off


def test_on_path_supports_post_media_review_thought() -> None:
    """ProcessTimeline already stacks thought → image → thought; guide steers LLM."""
    assert "ProcessTimeline" in CHAT
    assert "function DoneFeedback" in CHAT
    assert "isMediaDoneMessage" in CHAT
    assert "m.status === 'done' && isMediaDoneMessage(m)" in CHAT
    # Thought + image kinds both exist on the rail
    assert "kind === 'thought'" in CHAT
    assert "IMAGE_PROCESS_TOOLS" in CHAT


def test_off_keeps_prose_and_thumbs_no_chips() -> None:
    """#360 prose+👍 always stands — toggle only controls review thought."""
    ab = CHAT.split("export function AssistantBlocks")[1].split("\nexport function ")[0]
    assert "DoneFeedback" in ab
    assert "ca-chat__feedback" in CHAT
    assert "ca-panel__chips" not in ab
    assert "suggestionChips" not in ab
    assert "done-suggest" not in AGENT
    assert "Icons.thumbsUp" in CHAT


def test_media_hero_361_362_untouched() -> None:
    """Out of scope: media hero, #361 refusal, #362 @ menu."""
    assert "ca-media-hero" in CHAT
    assert "mediaHero" in CHAT
    # #361 How I created / refusal stay present if already on tip base
    # (soft check — do not require specific #361 strings beyond not deleting media hero)
    hero = OVERLAYS.split(".ca-media-hero {")[1].split("}")[0]
    assert "calc(var(--ca-process-col)" not in hero
