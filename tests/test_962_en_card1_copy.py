"""#962 — youtube-channel-banner card 1 follows the ask-card language (zh / en).

The server locks card 1's skeleton (`api/bot_asks.py`). Before #962 the lock was zh-only,
so the en UI got Chinese prompts/labels even when the agent sent an English card. The two
skeletons now share one definition per language with identical question / option ids.

$0: mock / fake only. No WaveSpeed, no real LLM, no paid call.
"""
from __future__ import annotations

import re

import pytest

from ComfyArt.api import banner_compose, bot_asks

CJK = re.compile(r"[\u4e00-\u9fff]")

# What the skill tells the agent to send in the en UI: English prompts + English live tiers.
CARD1_EN = {
    "questions": [
        {"id": "yt_delivery", "prompt": "How should this banner be delivered?", "allow_other": True,
         "options": [{"id": "A", "label": "Three-direction board first"},
                     {"id": "B", "label": "One final with exact text layout"},
                     {"id": "C", "label": "One final with model-rendered text"}]},
        {"id": "yt_banner_text", "prompt": "What text should appear on the banner?", "allow_other": True,
         "options": [{"id": "A", "label": "Loomi Studio + AI tutorials + Tue/Fri"},
                     {"id": "B", "label": "Loomi Studio + AI tutorials"},
                     {"id": "C", "label": "Loomi Studio only"}]},
        {"id": "yt_brand_assets", "prompt": "Any brand assets to include?", "allow_other": True,
         "options": [{"id": "A", "label": "None"},
                     {"id": "B", "label": "Logo / avatar upload"},
                     {"id": "C", "label": "Reserve a person slot"}]},
    ],
    "allow_skip": True,
    "page_count": 3,
}
# The same card in zh (verbatim reference copy), what the agent sends in the zh UI.
CARD1_ZH = {
    "questions": [
        {"id": "yt_delivery", "prompt": "这次横幅想怎么交付？（影响后续步骤与文字精度）", "allow_other": True,
         "options": [{"id": "A", "label": "先出三方向选择板，再做终稿"},
                     {"id": "B", "label": "直接出一张终稿，文字用精确排版渲染"},
                     {"id": "C", "label": "直接出一张终稿，文字由图像模型生成"}]},
        {"id": "yt_banner_text", "prompt": "横幅上实际要出现哪些文字？", "allow_other": True,
         "options": [{"id": "A", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流 ＋ 每周二/五更新"},
                     {"id": "B", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流"},
                     {"id": "C", "label": "只有 Loomi Studio"}]},
        {"id": "yt_brand_assets", "prompt": "有需要放进去的品牌资产吗？（Logo／头像／真人）", "allow_other": True,
         "options": [{"id": "A", "label": "没有，纯图形＋文字构成识别"},
                     {"id": "B", "label": "有 Logo／头像，我上传给你"},
                     {"id": "C", "label": "需要预留真人出镜位置"}]},
    ],
    "allow_skip": True,
    "page_count": 3,
}
EN_LOCKED = {
    "yt_delivery": (
        "How should this banner be delivered? (It changes the next steps and how precise the text can be)",
        ["Three-direction board first, then the final",
         "One final now, with text set by the exact-layout renderer",
         "One final now, with text drawn by the image model"],
        "Other ideas (e.g. several direction finals at once)...",
    ),
    "yt_banner_text": (
        "What text should actually appear on the banner?",
        None,  # live options
        "Your own copy (including case, symbols and line breaks)...",
    ),
    "yt_brand_assets": (
        "Any brand assets to include? (Logo / avatar / real person)",
        ["None, graphics + type only", "I have a logo / avatar to upload", "Reserve a spot for a real person"],
        "Other (e.g. a reference image / colors)...",
    ),
}
ZH_LOCKED = {
    "yt_delivery": (
        "这次横幅想怎么交付？（影响后续步骤与文字精度）",
        ["先出三方向选择板，再做终稿", "直接出一张终稿，文字用精确排版渲染", "直接出一张终稿，文字由图像模型生成"],
        "其它想法（比如一次出多个方向终稿）...",
    ),
    "yt_banner_text": ("横幅上实际要出现哪些文字？", None, "自己指定文案（含大小写、符号、换行）..."),
    "yt_brand_assets": (
        "有需要放进去的品牌资产吗？（Logo／头像／真人）",
        ["没有，纯图形＋文字构成识别", "有 Logo／头像，我上传给你", "需要预留真人出镜位置"],
        "其它（比如指定参考图／配色）...",
    ),
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


# --- en: prompt, options and placeholders come back in English -------------------------------

def test_en_card1_prompt_options_and_placeholders_are_english(monkeypatch) -> None:
    spec = _spec(monkeypatch, "en", CARD1_EN)
    assert [q["id"] for q in spec["questions"]] == ["yt_delivery", "yt_banner_text", "yt_brand_assets"]
    for q in spec["questions"]:
        prompt, labels, placeholder = EN_LOCKED[q["id"]]
        assert q["prompt"] == prompt
        assert not CJK.search(q["prompt"]), q["prompt"]
        assert q["placeholder"] == placeholder
        assert not CJK.search(q["placeholder"]), q["placeholder"]
        if labels is not None:
            assert [o["label"] for o in q["options"]] == labels
        for o in q["options"]:
            assert not CJK.search(o["label"]), o["label"]
    # Top-level mirrors used by notify / legacy readers are English too.
    assert spec["prompt"] == EN_LOCKED["yt_delivery"][0]
    assert not CJK.search(spec["prompt"])


def test_en_live_banner_text_options_keep_the_users_own_words(monkeypatch) -> None:
    """Only the fixed skeleton is translated; the three live tiers stay as the agent built them."""
    spec = _spec(monkeypatch, "en", CARD1_EN)
    q = next(q for q in spec["questions"] if q["id"] == "yt_banner_text")
    assert [o["label"] for o in q["options"]] == [o["label"] for o in CARD1_EN["questions"][1]["options"]]


# --- zh: byte-for-byte the reference card, no regression --------------------------------------

def test_zh_card1_keeps_the_reference_text(monkeypatch) -> None:
    spec = _spec(monkeypatch, "zh", CARD1_ZH)
    for q in spec["questions"]:
        prompt, labels, placeholder = ZH_LOCKED[q["id"]]
        assert q["prompt"] == prompt
        assert q["placeholder"] == placeholder
        if labels is not None:
            assert [o["label"] for o in q["options"]] == labels
    assert spec["page_count"] == 3 and spec["allow_skip"] is True
    assert all(q["page"] == 1 for q in spec["questions"])


# --- the language comes from the ask-card language, not from the agent's text ------------------

@pytest.mark.parametrize("lang,expected", [("en", EN_LOCKED), ("zh", ZH_LOCKED)])
def test_language_follows_card_lang_even_when_the_agent_sends_the_other_language(monkeypatch, lang, expected) -> None:
    other = CARD1_ZH if lang == "en" else CARD1_EN
    spec = _spec(monkeypatch, lang, other)
    for q in spec["questions"]:
        assert q["prompt"] == expected[q["id"]][0]
        assert q["placeholder"] == expected[q["id"]][2]


# --- option ids mean the same thing on both sides ----------------------------------------------

def test_zh_en_option_ids_and_semantics_match_one_to_one(monkeypatch) -> None:
    en = _spec(monkeypatch, "en", CARD1_EN)
    zh = _spec(monkeypatch, "zh", CARD1_ZH)
    for en_q, zh_q in zip(en["questions"], zh["questions"]):
        assert en_q["id"] == zh_q["id"]
        assert [o["id"] for o in en_q["options"]] == [o["id"] for o in zh_q["options"]]
    # B means 精确排版 on both sides, so an en pick cannot fall through to another zh meaning.
    en_b = next(q for q in en["questions"] if q["id"] == "yt_delivery")["options"]
    zh_b = next(q for q in zh["questions"] if q["id"] == "yt_delivery")["options"]
    assert banner_compose._map_delivery(["B"], "", en_b) == "base"
    assert banner_compose._map_delivery(["B"], "", zh_b) == "base"
    assert banner_compose._map_delivery(["A"], "", en_b) == "board"
    assert banner_compose._map_delivery(["C"], "", en_b) == "direct"
    # Free text that repeats the visible en label maps the same way.
    assert banner_compose._map_delivery([], en_b[1]["label"], en_b) == "base"


def test_zh_en_placeholders_are_not_mixed(monkeypatch) -> None:
    en = _spec(monkeypatch, "en", CARD1_EN)
    zh = _spec(monkeypatch, "zh", CARD1_ZH)
    for en_q in en["questions"]:
        assert not CJK.search(en_q["placeholder"])
    for zh_q in zh["questions"]:
        assert CJK.search(zh_q["prompt"]) and CJK.search(zh_q["placeholder"])
