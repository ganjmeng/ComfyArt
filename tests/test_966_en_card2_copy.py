"""#966 — youtube-channel-banner card 2 follows the ask-card language (zh / en).

Card 2 (direction + how the final text is set) is locked by the same server path as card 1
(`api/bot_asks.py`). Before #966 the card-2 skeleton was zh-only, so the en UI got Chinese
prompts, the Chinese 「（推荐）」 marker and the Chinese text-mode labels. The two skeletons now
share one definition per language with identical question / option ids.

Fixed copy translated here: the two prompts, the two placeholders, the two text-mode option
labels and the recommended marker. The three yt_direction options stay live (agent-authored
from the board + the user's words): they are kept verbatim, never translated by the server.

$0: mock / fake only. No WaveSpeed, no real LLM, no paid call.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ComfyArt.api import banner_compose, bot_asks

CJK = re.compile(r"[\u4e00-\u9fff]")
ROOT = Path(__file__).resolve().parents[1]

# What a locale-consistent agent sends in the en UI: fixed en text + en live directions.
CARD2_EN = {
    "questions": [
        {"id": "yt_direction", "prompt": "Which direction should become the 2560×1440 final?",
         "options": [
             {"id": "A", "label": "Direction A: Brand-led with generous white space",
              "description": "Top of the board: the cleanest, still readable on mobile", "recommended": True},
             {"id": "B", "label": "Direction B: Full-frame narrative scene (Recommended)",
              "description": "Middle of the board: the richest image"},
             {"id": "C", "label": "Direction C: Modular workflow grid",
              "description": "Bottom of the board: closest to the workflow theme"},
         ]},
        {"id": "yt_text_mode", "prompt": "How should the final's text be set?",
         "options": [{"id": "A", "label": "Exact layout", "recommended": True},
                     {"id": "B", "label": "Image model draws it"}]},
    ],
    "allow_skip": True,
    "page_count": 2,
}
# The same card in zh (verbatim reference copy).
CARD2_ZH = {
    "questions": [
        {"id": "yt_direction", "prompt": "选哪个方向做 2560×1440 终稿？",
         "options": [
             {"id": "A", "label": "方向 A：品牌主导·大留白（推荐）",
              "description": "选择板顶部：最干净，缩到移动端也不丢信息", "recommended": True},
             {"id": "B", "label": "方向 B：全画幅叙事场景（推荐）",
              "description": "选择板中部：画面最丰富"},
             {"id": "C", "label": "方向 C：模块化工作流网格",
              "description": "选择板底部：最贴工作流主题"},
         ]},
        {"id": "yt_text_mode", "prompt": "终稿的文字怎么上？",
         "options": [{"id": "A", "label": "精确排版", "recommended": True},
                     {"id": "B", "label": "模型直出"}]},
    ],
    "allow_skip": True,
    "page_count": 2,
}
EN_LOCKED = {
    "yt_direction": (
        "Which direction should become the 2560×1440 final?",
        None,  # live options
        "Want changes (say what to adjust), or let me decide...",
    ),
    "yt_text_mode": (
        "How should the final's text be set? (Chinese + three lines of info; accuracy varies a lot)",
        ["Exact layout (Recommended)", "Image model renders the text"],
        "Any other requirements...",
    ),
}
ZH_LOCKED = {
    "yt_direction": (
        "选哪个方向做 2560×1440 终稿？",
        None,
        "想调整（说哪里改）或让我直接定...",
    ),
    "yt_text_mode": (
        "终稿的文字怎么上？（中文＋三行信息，精度差异较大）",
        ["精确排版（推荐）", "图像模型直出"],
        "其它要求...",
    ),
}
ZH_DIRECTION_LABELS = ["方向 A：品牌主导·大留白", "方向 B：全画幅叙事场景", "方向 C：模块化工作流网格"]
ZH_DIRECTION_DESCRIPTIONS = [
    "（推荐）选择板顶部：最干净，缩到移动端也不丢信息",
    "选择板中部：画面最丰富",
    "选择板底部：最贴工作流主题",
]


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


# --- en: prompt, text-mode options, placeholders and marker come back in English ---------------

def test_en_card2_prompt_options_and_placeholders_are_english(monkeypatch) -> None:
    spec = _spec(monkeypatch, "en", CARD2_EN)
    assert spec["page_count"] == 2 and spec["allow_skip"] is True
    assert [q["id"] for q in spec["questions"]] == ["yt_direction", "yt_text_mode"]
    for q in spec["questions"]:
        prompt, labels, placeholder = EN_LOCKED[q["id"]]
        assert q["prompt"] == prompt, q["id"]
        assert not CJK.search(q["prompt"]), q["prompt"]
        assert q["placeholder"] == placeholder, q["id"]
        assert not CJK.search(q["placeholder"]), q["placeholder"]
        assert q["page"] == (1 if q["id"] == "yt_direction" else 2) and q["allow_other"] is True
        if labels is not None:
            assert [o["label"] for o in q["options"]] == labels
        for o in q["options"]:
            assert not CJK.search(o["label"]), o["label"]
    # Top-level mirrors used by notify / legacy readers are English too.
    assert spec["prompt"] == EN_LOCKED["yt_direction"][0]
    assert not CJK.search(spec["prompt"])


def test_en_recommended_marker_is_english_and_only_a_description_prefix(monkeypatch) -> None:
    spec = _spec(monkeypatch, "en", CARD2_EN)
    directions = spec["questions"][0]["options"]
    assert sum(o["description"].startswith("(Recommended)") for o in directions) == 1
    assert not any("(Recommended)" in o["label"] for o in directions)
    assert not any("（推荐）" in str(o) for o in directions)
    assert not any(o.get("recommended") for o in directions)
    # The fixed text-mode label carries the en marker, not the zh one.
    assert spec["questions"][1]["options"][0]["label"] == "Exact layout (Recommended)"


def test_en_live_direction_options_keep_the_agents_live_copy(monkeypatch) -> None:
    """Only fixed copy is translated; the board's live labels/descriptions are not rewritten."""
    spec = _spec(monkeypatch, "en", CARD2_EN)
    directions = spec["questions"][0]["options"]
    assert [o["label"] for o in directions] == [
        "Direction A: Brand-led with generous white space",
        "Direction B: Full-frame narrative scene",  # marker moved out, nothing else changed
        "Direction C: Modular workflow grid",
    ]
    assert directions[0]["description"] == "Top of the board: the cleanest, still readable on mobile"
    assert directions[2]["description"] == "Bottom of the board: closest to the workflow theme"
    # A zh live card in the en UI stays zh live copy; only the fixed skeleton + marker localize.
    mixed = _spec(monkeypatch, "en", CARD2_ZH)
    mixed_dirs = mixed["questions"][0]["options"]
    assert [o["label"] for o in mixed_dirs] == ZH_DIRECTION_LABELS
    assert mixed["questions"][0]["prompt"] == EN_LOCKED["yt_direction"][0]
    assert sum(o["description"].startswith("(Recommended)") for o in mixed_dirs) == 1


# --- zh: byte-for-byte the reference card, no regression --------------------------------------

def test_zh_card2_keeps_the_reference_text(monkeypatch) -> None:
    spec = _spec(monkeypatch, "zh", CARD2_ZH)
    assert spec["page_count"] == 2 and spec["allow_skip"] is True
    for q in spec["questions"]:
        prompt, labels, placeholder = ZH_LOCKED[q["id"]]
        assert q["prompt"] == prompt
        assert q["placeholder"] == placeholder
        assert q["page"] == (1 if q["id"] == "yt_direction" else 2) and q["allow_other"] is True
        if labels is not None:
            assert [o["label"] for o in q["options"]] == labels
    directions = spec["questions"][0]["options"]
    assert [o["label"] for o in directions] == ZH_DIRECTION_LABELS
    assert [o["description"] for o in directions] == ZH_DIRECTION_DESCRIPTIONS
    assert sum(o["description"].startswith("（推荐）") for o in directions) == 1


def test_zh_marker_localizes_when_the_agent_sends_an_en_card(monkeypatch) -> None:
    spec = _spec(monkeypatch, "zh", CARD2_EN)
    directions = spec["questions"][0]["options"]
    assert spec["questions"][0]["prompt"] == ZH_LOCKED["yt_direction"][0]
    assert not any("(Recommended)" in str(o) for o in directions)
    assert sum(o["description"].startswith("（推荐）") for o in directions) == 1


# --- option ids / order / semantics match one to one ------------------------------------------

def test_zh_en_option_ids_and_semantics_match_one_to_one(monkeypatch) -> None:
    en = _spec(monkeypatch, "en", CARD2_EN)
    zh = _spec(monkeypatch, "zh", CARD2_ZH)
    for en_q, zh_q in zip(en["questions"], zh["questions"]):
        assert en_q["id"] == zh_q["id"]
        assert [o["id"] for o in en_q["options"]] == [o["id"] for o in zh_q["options"]]
    en_opts = en["questions"][1]["options"]
    zh_opts = zh["questions"][1]["options"]
    assert banner_compose._map_text_mode(["A"], "", en_opts) == "base"
    assert banner_compose._map_text_mode(["A"], "", zh_opts) == "base"
    assert banner_compose._map_text_mode(["B"], "", en_opts) == "direct"
    assert banner_compose._map_text_mode(["B"], "", zh_opts) == "direct"
    # Free text that repeats the visible label maps the same way on both sides.
    assert banner_compose._map_text_mode([], "Exact layout (Recommended)", en_opts) == "base"
    assert banner_compose._map_text_mode([], "精确排版", zh_opts) == "base"


@pytest.mark.parametrize("lang,text_mode,expected", [("en", "A", "base"), ("en", "B", "direct"),
                                                    ("zh", "A", "base"), ("zh", "B", "direct")])
def test_stage_from_answered_card2_same_in_both_languages(monkeypatch, lang, text_mode, expected) -> None:
    card = CARD2_EN if lang == "en" else CARD2_ZH
    spec = _spec(monkeypatch, lang, card)
    block = {
        "type": "ask", "status": "answered", **spec,
        "answers": {
            "yt_direction": {"selected": ["A"], "other_text": ""},
            "yt_text_mode": {"selected": [text_mode], "other_text": ""},
        },
    }
    assert banner_compose._is_card2_block(block) is True
    assert banner_compose.stage_from_card2(block) == expected


def test_locked_tables_cover_both_languages() -> None:
    assert set(bot_asks.YT_CARD_2_BY_LANG) == {"zh", "en"}
    assert len(bot_asks.YT_CARD_2) == 4
    assert [q["id"] for q in bot_asks.YT_TEXT_MODES] == ["yt_text_mode", "yt_text_mode"]
    for lang in ("zh", "en"):
        assert [q["id"] for q in bot_asks.YT_CARD_2_BY_LANG[lang]] == ["yt_direction", "yt_text_mode"]


# --- the skill tells the agent how card 2's live labels follow the locale ----------------------

def test_skill_text_has_locale_guidance_for_card2() -> None:
    from test_youtube_banner_flow import _instructions

    instr = _instructions()
    assert "the server locks this fixed card-2 text in the card language" in instr
    assert 'en label "Direction A: <short name>"' in instr
    assert 'In the en UI use "(Recommended)" for that marker instead of "（推荐）"' in instr
    # The zh reference copy and the zh marker rule are untouched.
    assert 'prompt "选哪个方向做 2560×1440 终稿？"' in instr
    assert 'label:"精确排版（推荐）"' in instr
