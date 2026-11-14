"""#949 — youtube-channel-banner inquiry card: one ask for card 1, clean placeholders,
Chinese first sentence in a Chinese conversation.

Locks the three fixes from the #925 paid acceptance (issuecomment-6845366241):
1. Card 1's three questions are always in a single ask; page_count 3 does not
   leave pages 2 and 3 empty (all three stay on page 1, header 1 of 3).
2. Trailing typographic junk (`”,` / `",`) is stripped from card 1 and card 2
   placeholders.
3. In a Chinese conversation, the agent's first visible sentence is Chinese
   even when the model opens with "I'll read the skill first."

$0: mock / fake only. No WaveSpeed, no real LLM, no paid call.
"""
from __future__ import annotations

import re

import pytest

from ComfyArt.api import bot_asks
from ComfyArt.api.bot_turns import _TurnState, _apply_event
from ComfyArt.bot import TurnHandle
from ComfyArt.bot.guide import AGENT_GUIDE
from ComfyArt.bot.local_llm import (
    _REPLY_LANG_FIRST_RULE,
    _SYSTEM_PROMPT,
    _ZH_SKILL_FIRST,
    localize_first_sentence,
    system_prompt_for_turn,
)
from ComfyArt.bot.providers import BotEvent
from ComfyArt.api.bot_asks import clean_ask_placeholder

CJK = re.compile(r"[\u4e00-\u9fff]")
JUNK = "\u201d,"  # the trailing `”,` from the paid run
DIRTY = "其它想法（比如一次出多个方向终稿）..." + JUNK
CLEAN_ZH_DELIVERY = "其它想法（比如一次出多个方向终稿）..."
CLEAN_ZH_TEXT = "自己指定文案（含大小写、符号、换行）..."
CLEAN_ZH_ASSETS = "其它（比如指定参考图／配色）..."
CLEAN_ZH_DIR = "想调整（说哪里改）或让我直接定..."
CLEAN_ZH_MODE = "其它要求..."

Q1_ONLY_DIRTY = {
    "questions": [
        {
            "id": "yt_delivery",
            "prompt": "这次横幅想怎么交付？（影响后续步骤与文字精度）",
            "allow_other": True,
            "placeholder": DIRTY,
            "options": [
                {"id": "A", "label": "先出三方向选择板，再做终稿"},
                {"id": "B", "label": "直接出一张终稿，文字用精确排版渲染"},
                {"id": "C", "label": "直接出一张终稿，文字由图像模型生成"},
            ],
        }
    ],
    "allow_skip": True,
    "page_count": 3,
}

CARD2_DIRTY = {
    "questions": [
        {
            "id": "yt_direction",
            "prompt": "选哪个方向做 2560×1440 终稿？",
            "allow_other": True,
            "placeholder": CLEAN_ZH_DIR + JUNK,
            "options": [
                {"id": "A", "label": "方向 A：品牌主导·大留白", "description": "选择板顶部"},
                {"id": "B", "label": "方向 B：全画幅叙事场景", "description": "选择板中部"},
                {"id": "C", "label": "方向 C：模块化工作流网格", "description": "选择板底部"},
            ],
        },
        {
            "id": "yt_text_mode",
            "prompt": "终稿的文字怎么上？（中文＋三行信息，精度差异较大）",
            "allow_other": True,
            "placeholder": CLEAN_ZH_MODE + JUNK,
            "options": [
                {"id": "A", "label": "精确排版（推荐）"},
                {"id": "B", "label": "图像模型直出"},
            ],
        },
    ],
    "allow_skip": True,
    "page_count": 2,
}


@pytest.fixture(autouse=True)
def _clean_pending():
    bot_asks.PENDING.clear()
    bot_asks.ANSWERED_RUN_APPROVALS.clear()
    yield
    bot_asks.PENDING.clear()
    bot_asks.ANSWERED_RUN_APPROVALS.clear()


def _spec(monkeypatch, lang: str, card: dict) -> dict:
    monkeypatch.setattr(bot_asks, "card_lang", lambda: lang)
    return bot_asks.validate_spec(card)


# --- placeholders --------------------------------------------------------------------------------

def test_clean_ask_placeholder_strips_trailing_quote_comma() -> None:
    assert clean_ask_placeholder(DIRTY) == CLEAN_ZH_DELIVERY
    assert clean_ask_placeholder('Other ideas (e.g. several direction finals at once)...",') == (
        "Other ideas (e.g. several direction finals at once)..."
    )
    assert clean_ask_placeholder(CLEAN_ZH_DELIVERY) == CLEAN_ZH_DELIVERY
    assert JUNK not in clean_ask_placeholder("其它要求..." + JUNK)


def test_card1_and_card2_placeholders_drop_trailing_junk(monkeypatch) -> None:
    one = _spec(monkeypatch, "zh", Q1_ONLY_DIRTY)
    assert [q["placeholder"] for q in one["questions"]] == [
        CLEAN_ZH_DELIVERY, CLEAN_ZH_TEXT, CLEAN_ZH_ASSETS,
    ]
    for q in one["questions"]:
        assert JUNK not in q["placeholder"]
        assert not q["placeholder"].endswith('",')
        assert not q["placeholder"].endswith("\u201d")

    two = _spec(monkeypatch, "zh", CARD2_DIRTY)
    assert [q["id"] for q in two["questions"]] == ["yt_direction", "yt_text_mode"]
    assert [q["placeholder"] for q in two["questions"]] == [CLEAN_ZH_DIR, CLEAN_ZH_MODE]


def test_mutation_passthrough_placeholders_fails_the_junk_lock(monkeypatch) -> None:
    """If placeholders are passed through uncleaned, the #949 junk lock must go red."""
    real = bot_asks._yt_question

    def dirty_question(raw, locked, lang):
        q = real(raw if raw else {}, locked, lang)
        # Revert: keep whatever the model sent, including `”,`.
        if raw and raw.get("placeholder"):
            q["placeholder"] = raw["placeholder"]
        return q

    monkeypatch.setattr(bot_asks, "_yt_question", dirty_question)
    red = False
    try:
        one = bot_asks.validate_spec(dict(Q1_ONLY_DIRTY))
        assert JUNK not in one["questions"][0]["placeholder"]
    except AssertionError:
        red = True
    assert red, "passing through a trailing ” , must fail the placeholder lock"


# --- card 1 is one ask, no empty pages ----------------------------------------------------------

def test_card1_partial_ask_is_completed_to_three_questions_on_page_1(monkeypatch) -> None:
    """The paid-run failure: first ask_user had only Q1 with page_count 3."""
    spec = _spec(monkeypatch, "zh", Q1_ONLY_DIRTY)
    assert [q["id"] for q in spec["questions"]] == [
        "yt_delivery", "yt_banner_text", "yt_brand_assets",
    ]
    assert spec["page_count"] == 3
    assert all(q["page"] == 1 for q in spec["questions"])
    # All three on one page + page_count 3 is header chrome only (no empty 2/3).
    pages = {q["page"] for q in spec["questions"]}
    assert pages == {1}


def test_card2_missing_text_mode_is_not_invented(monkeypatch) -> None:
    """#934/#940: a card-2 ask that only sent yt_direction stays a single question."""
    raw = {
        "questions": [dict(CARD2_DIRTY["questions"][0])],
        "allow_skip": True,
        "page_count": 2,
    }
    spec = _spec(monkeypatch, "zh", raw)
    assert [q["id"] for q in spec["questions"]] == ["yt_direction"]
    assert spec["page_count"] == 2


def test_mutation_keeping_only_sent_card1_questions_fails(monkeypatch) -> None:
    """Reverting to 'keep only what the model sent' must fail the one-ask lock."""
    real = bot_asks.normalize_youtube_banner_card

    def old_keep_sent(args, lang=None):
        out = real(args, lang)
        questions = (args or {}).get("questions") or []
        if not questions:
            return out
        # Old behavior: drop questions the model did not send.
        sent_ids = {str(q.get("id") or "") for q in questions if isinstance(q, dict)}
        # Match by prompt head too: the fixture only sent yt_delivery.
        kept = [q for q in out.get("questions") or [] if q.get("id") in sent_ids or q.get("id") == "yt_delivery"]
        if kept and any(q.get("id") == "yt_delivery" for q in (out.get("questions") or [])):
            out = dict(out)
            out["questions"] = [q for q in out["questions"] if q["id"] in {"yt_delivery"} or q["id"] in sent_ids]
            if len(questions) == 1:
                out["questions"] = [q for q in out["questions"] if q["id"] == "yt_delivery"]
        return out

    monkeypatch.setattr(bot_asks, "normalize_youtube_banner_card", old_keep_sent)
    red = False
    try:
        spec = bot_asks.validate_spec(dict(Q1_ONLY_DIRTY))
        assert [q["id"] for q in spec["questions"]] == [
            "yt_delivery", "yt_banner_text", "yt_brand_assets",
        ]
        assert all(q["page"] == 1 for q in spec["questions"])
    except AssertionError:
        red = True
    assert red, "keeping only Q1 must fail the card-1 one-ask lock"


# --- Chinese first sentence ---------------------------------------------------------------------

@pytest.mark.parametrize("src", [
    "I'll read the skill first.",
    "I'll read the skill first",
    "I will read the skill first.",
    "Let me read the skill first.",
    "Reading the skill first.",
])
def test_localize_first_sentence_rewrites_english_boot_in_zh(src) -> None:
    assert localize_first_sentence(src, "zh") == _ZH_SKILL_FIRST
    assert CJK.search(_ZH_SKILL_FIRST)
    # English conversations stay English.
    assert localize_first_sentence(src, "en") == src


def test_localize_first_sentence_leaves_chinese_and_other_english_alone() -> None:
    assert localize_first_sentence("我先看一下技能说明。", "zh") == "我先看一下技能说明。"
    assert localize_first_sentence("Here's a banner direction.", "zh") == "Here's a banner direction."


def test_apply_event_rewrites_first_english_sentence_in_zh_turn() -> None:
    st = _TurnState(TurnHandle(), "c", "m")
    st.lang = "zh"
    # Streamed in two chunks, as a live model often does.
    first = _apply_event(st, BotEvent(t="delta", text="I'll read the "))
    assert first is None
    assert st.blocks == []
    second = _apply_event(st, BotEvent(t="delta", text="skill first."))
    assert second == {"event": "turn_delta", "text": _ZH_SKILL_FIRST}
    texts = [b["text"] for b in st.blocks if b.get("type") == "text"]
    assert texts == [_ZH_SKILL_FIRST]
    assert "I'll read" not in "".join(texts)


def test_apply_event_keeps_rewritten_first_sentence_when_the_skill_tool_runs() -> None:
    st = _TurnState(TurnHandle(), "c", "m")
    st.lang = "zh"
    payload = _apply_event(st, BotEvent(t="delta", text="I'll read the skill first."))
    assert payload == {"event": "turn_delta", "text": _ZH_SKILL_FIRST}
    _apply_event(st, BotEvent(t="tool_use", name="skill", input={"action": "read"}, id="t1"))
    texts = [b["text"] for b in st.blocks if b.get("type") == "text"]
    assert texts == [_ZH_SKILL_FIRST]
    assert not any("I'll read" in str(b) for b in st.blocks)


def test_mutation_skipping_localization_fails_the_zh_first_sentence_lock(monkeypatch) -> None:
    monkeypatch.setattr(
        "ComfyArt.api.bot_turns.localize_first_sentence", lambda text, lang: text
    )
    st = _TurnState(TurnHandle(), "c", "m")
    st.lang = "zh"
    red = False
    try:
        _apply_event(st, BotEvent(t="delta", text="I'll read the skill first."))
        texts = [b["text"] for b in st.blocks if b.get("type") == "text"]
        assert texts == [_ZH_SKILL_FIRST]
    except AssertionError:
        red = True
    assert red, "leaving the English boot line in a zh turn must fail the first-sentence lock"


def test_system_prompt_and_guide_require_a_chinese_first_sentence() -> None:
    assert "including your first sentence" in AGENT_GUIDE
    assert "I'll read the skill first." in _REPLY_LANG_FIRST_RULE
    assert _REPLY_LANG_FIRST_RULE in _SYSTEM_PROMPT
    zh = system_prompt_for_turn("帮我做一张 YouTube 频道横幅", "en")
    assert "first visible sentence must also be Chinese" in zh
    assert "I'll read the skill first." in zh
    en = system_prompt_for_turn("Make a YouTube channel banner", "zh")
    assert "first visible sentence must also be English" in en
