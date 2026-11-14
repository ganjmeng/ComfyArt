"""#934 — youtube-channel-banner card 2: shared board thumbnails, visible
descriptions, one question per page, no default selection.

Locks the product rulings in issuecomment-6844291499:
1. Direction options reuse the selection-board image already generated in this
   run (the same image_url on A/B/C). No unique crops, no extra generation.
2. Every text option's description is present on the option (card 1 and card 2),
   not dropped.
3. One question per screen (page 1, 2, …); page_count equals the question count.
   Card 1 stays one ask with all three questions; card 2 is completed the same way.
4. Nothing is preselected; input placeholders stay the locked content (cleaned).

$0: mock / fake only. No WaveSpeed, no real LLM, no paid call.
"""
from __future__ import annotations

import pytest

from ComfyArt.api import bot_asks
from ComfyArt.api import chat_store
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID

BOARD = "/api/view?filename=yt-board.png&subfolder=comfyart&type=output"
OTHER = "/api/view?filename=other-crop.png&subfolder=comfyart&type=output"

CARD2 = {
    "questions": [
        {
            "id": "yt_direction",
            "prompt": "选哪个方向做 2560×1440 终稿？",
            "allow_other": True,
            "placeholder": "想调整（说哪里改）或让我直接定...",
            "options": [
                {"id": "A", "label": "方向 A：品牌主导·大留白",
                 "description": "（推荐）选择板顶部：最干净、缩到移动端也不丢信息，教程类频道辨识度高",
                 "image_url": BOARD},
                {"id": "B", "label": "方向 B：全画幅叙事场景",
                 "description": "选择板中部：画面最丰富，TV 全屏下最有氛围，文字密度需要严控",
                 "image_url": OTHER},
                {"id": "C", "label": "方向 C：模块化工作流网格",
                 "description": "选择板底部：最贴“工作流”主题，理性又活泼，适合做系列延伸"},
            ],
        },
        {
            "id": "yt_text_mode",
            "prompt": "终稿的文字怎么上？（中文＋三行信息，精度差异较大）",
            "allow_other": True,
            "placeholder": "其它要求...",
            "options": [
                {"id": "A", "label": "精确排版（推荐）"},
                {"id": "B", "label": "图像模型直出"},
            ],
        },
    ],
    "allow_skip": True,
    "page_count": 2,
}

CARD1 = {
    "questions": [
        {
            "id": "yt_delivery",
            "prompt": "这次横幅想怎么交付？（影响后续步骤与文字精度）",
            "allow_other": True,
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


# --- thumbnails reuse one board image ----------------------------------------------------------

def test_card2_direction_options_share_one_board_image_url(monkeypatch) -> None:
    spec = _spec(monkeypatch, "zh", CARD2)
    directions = spec["questions"][0]["options"]
    urls = [o.get("image_url") for o in directions]
    assert urls == [BOARD, BOARD, BOARD]
    assert len(set(urls)) == 1
    # Q2 is text-only — no thumbnails.
    assert all("image_url" not in o for o in spec["questions"][1]["options"])


def test_card2_attaches_board_from_this_run_when_agent_omits_image_url(monkeypatch) -> None:
    chat = chat_store.create_chat(user="default", project="p934", provider="local-llm")
    chat_store.create_message(
        chat_id=chat["id"], role="assistant", status="done",
        blocks=[
            {"type": "tool_use", "name": "generate_image", "id": "g1",
             "input": {"skill": "youtube-channel-banner", "banner_stage": "board"}},
            {"type": "tool_result", "name": "wait_generation", "id": "w1", "status": "success",
             "text": f"placed {BOARD}"},
        ],
    )
    token = BOT_CHAT_ID.set(chat["id"])
    try:
        raw = {
            "questions": [{
                "id": "yt_direction",
                "prompt": "选哪个方向做 2560×1440 终稿？",
                "allow_other": True,
                "options": [
                    {"id": "A", "label": "方向 A：品牌主导·大留白", "description": "选择板顶部：干净"},
                    {"id": "B", "label": "方向 B：全画幅叙事场景", "description": "选择板中部：丰富"},
                    {"id": "C", "label": "方向 C：模块化工作流网格", "description": "选择板底部：网格"},
                ],
            }],
            "allow_skip": True,
            "page_count": 2,
        }
        spec = _spec(monkeypatch, "zh", raw)
        urls = [o["image_url"] for o in spec["questions"][0]["options"]]
        assert urls == [BOARD, BOARD, BOARD]
        assert [q["id"] for q in spec["questions"]] == ["yt_direction", "yt_text_mode"]
    finally:
        BOT_CHAT_ID.reset(token)


def test_mutation_unique_thumbnails_fails_the_shared_board_lock(monkeypatch) -> None:
    """If each direction keeps its own image_url, the #934 thumbnail lock must go red."""
    real = bot_asks._yt_apply_board_thumbnails

    def keep_unique(questions, board_url=None):
        # Revert: leave whatever the model sent, including unique URLs.
        return None

    monkeypatch.setattr(bot_asks, "_yt_apply_board_thumbnails", keep_unique)
    red = False
    try:
        spec = bot_asks.validate_spec(dict(CARD2))
        urls = [o.get("image_url") for o in spec["questions"][0]["options"]]
        assert urls == [BOARD, BOARD, BOARD]
        assert len(set(u for u in urls if u)) == 1
    except AssertionError:
        red = True
    assert red, "leaving unique per-option thumbnails must fail the shared-board lock"
    monkeypatch.setattr(bot_asks, "_yt_apply_board_thumbnails", real)


# --- descriptions are on the options (card 1 and card 2) --------------------------------------

def test_card1_and_card2_text_options_carry_visible_descriptions(monkeypatch) -> None:
    one = _spec(monkeypatch, "zh", CARD1)
    assert [q["page"] for q in one["questions"]] == [1, 1, 1]
    delivery = one["questions"][0]["options"]
    assert delivery[0]["description"].startswith("推荐：一张板上放 3 个结构不同的方向")
    assert delivery[1]["description"]
    assert delivery[2]["description"]
    assets = one["questions"][2]["options"]
    assert all(o.get("description") for o in assets)

    two = _spec(monkeypatch, "zh", CARD2)
    directions = two["questions"][0]["options"]
    assert all(o.get("description") for o in directions)
    assert "选择板顶部" in directions[0]["description"]
    modes = two["questions"][1]["options"]
    assert modes[0]["description"].startswith("先生成无字底图")
    assert "出错字" in modes[1]["description"]

    en = _spec(monkeypatch, "en", CARD1)
    for q in en["questions"]:
        if q["id"] == "yt_banner_text":
            continue
        for o in q["options"]:
            assert o.get("description"), o
            assert not __import__("re").search(r"[\u4e00-\u9fff]", o["description"]), o["description"]


def test_mutation_dropping_descriptions_fails_the_lock(monkeypatch) -> None:
    real = bot_asks._yt_question

    def strip_desc(raw, locked, lang, page=1):
        q = real(raw if raw else {}, locked, lang, page=page)
        for o in q.get("options") or []:
            o.pop("description", None)
        return q

    monkeypatch.setattr(bot_asks, "_yt_question", strip_desc)
    red = False
    try:
        spec = bot_asks.validate_spec(dict(CARD1))
        assert all(o.get("description") for o in spec["questions"][0]["options"])
    except AssertionError:
        red = True
    assert red, "dropping option descriptions must fail the #934 description lock"


# --- pagination: one question per page, one ask, no empty pages, no defaults ------------------

def test_card1_is_one_scrolling_page_with_all_three_questions(monkeypatch) -> None:
    """HOLD #998: card 1 stays one scrolling card; only card 2 is 1/2 + Next."""
    spec = _spec(monkeypatch, "zh", CARD1)
    assert [q["id"] for q in spec["questions"]] == [
        "yt_delivery", "yt_banner_text", "yt_brand_assets",
    ]
    assert [q["page"] for q in spec["questions"]] == [1, 1, 1]
    assert spec["page_count"] == 3
    assert len({q["page"] for q in spec["questions"]}) == 1
    # Descriptions under titles are still present (the #934 card-1 increment).
    assert all(o.get("description") for o in spec["questions"][0]["options"])
    assert all(o.get("description") for o in spec["questions"][2]["options"])


def test_mutation_paginating_card1_fails_the_scroll_lock(monkeypatch) -> None:
    """Putting card 1 back on pages 1/2/3 must fail the scrolling-card lock."""
    real = bot_asks.normalize_youtube_banner_card

    def paged(args, lang=None):
        out = real(args, lang)
        qs = list(out.get("questions") or [])
        if qs and qs[0].get("id") == "yt_delivery":
            out = dict(out)
            out["questions"] = [{**q, "page": i} for i, q in enumerate(qs, start=1)]
        return out

    monkeypatch.setattr(bot_asks, "normalize_youtube_banner_card", paged)
    red = False
    try:
        spec = bot_asks.validate_spec(dict(CARD1))
        assert [q["page"] for q in spec["questions"]] == [1, 1, 1]
        assert len({q["page"] for q in spec["questions"]}) == 1
    except AssertionError:
        red = True
    assert red, "paginating card 1 as 1/3, 2/3, 3/3 must fail the scroll-card lock"


def test_card2_is_one_ask_with_one_question_per_page(monkeypatch) -> None:
    spec = _spec(monkeypatch, "zh", CARD2)
    assert [q["id"] for q in spec["questions"]] == ["yt_direction", "yt_text_mode"]
    assert [q["page"] for q in spec["questions"]] == [1, 2]
    assert spec["page_count"] == 2
    assert "defaults" not in spec
    for q in spec["questions"]:
        assert "defaults" not in q
        assert not any(o.get("recommended") for o in q["options"])
        assert q["placeholder"]
        assert q["allow_other"] is True


def test_card2_en_locked_copy_and_pages(monkeypatch) -> None:
    spec = _spec(monkeypatch, "en", CARD2)
    assert spec["questions"][0]["prompt"] == "Which direction should become the 2560×1440 final?"
    assert spec["questions"][1]["prompt"].startswith("How should the final's text be set?")
    assert [q["page"] for q in spec["questions"]] == [1, 2]
    modes = spec["questions"][1]["options"]
    assert [o["label"] for o in modes] == ["Exact layout (Recommended)", "Image model renders the text"]
    assert modes[0]["description"].startswith("Generate a text-free base first")
    assert "image_url" not in modes[0] and "image_url" not in modes[1]


# --- #911-style repeatable mock contract for card 2 --------------------------------------------

EXPECTED_CARD2_ZH = {
    "ids": ["yt_direction", "yt_text_mode"],
    "pages": [1, 2],
    "page_count": 2,
    "prompts": [
        "选哪个方向做 2560×1440 终稿？",
        "终稿的文字怎么上？（中文＋三行信息，精度差异较大）",
    ],
    "placeholders": [
        "想调整（说哪里改）或让我直接定...",
        "其它要求...",
    ],
    "text_mode_labels": ["精确排版（推荐）", "图像模型直出"],
}


def test_card2_structure_is_the_repeatable_mock_contract(monkeypatch) -> None:
    """Same skeleton on every normalize: ids, pages, prompts, placeholders, text-mode labels."""
    spec = _spec(monkeypatch, "zh", CARD2)
    exp = EXPECTED_CARD2_ZH
    assert [q["id"] for q in spec["questions"]] == exp["ids"]
    assert [q["page"] for q in spec["questions"]] == exp["pages"]
    assert spec["page_count"] == exp["page_count"]
    assert [q["prompt"] for q in spec["questions"]] == exp["prompts"]
    assert [q["placeholder"] for q in spec["questions"]] == exp["placeholders"]
    assert [o["label"] for o in spec["questions"][1]["options"]] == exp["text_mode_labels"]
    # Live direction labels stay agent-authored.
    assert [o["label"] for o in spec["questions"][0]["options"]] == [
        "方向 A：品牌主导·大留白",
        "方向 B：全画幅叙事场景",
        "方向 C：模块化工作流网格",
    ]


def test_skill_instructions_describe_card2_thumbnails_and_pagination() -> None:
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src/skills.ts").read_text(encoding="utf-8")
    m = re.search(
        r"\{ id: 'youtube-channel-banner', name: t\('skills.youtubeChannelBanner'\), instructions: '((?:\\.|[^'\\])*)'",
        src,
    )
    assert m, "youtube-channel-banner instructions did not parse"
    instr = m.group(1).replace("\\n", "\n").replace("\\'", "'").replace("\\\\", "\\")
    assert "One question per page" in instr  # card 2 only
    assert "the same full board image" in instr
    assert "do not crop" in instr.lower() or "not a crop" in instr
    assert "选择板顶部/中部/底部：理由" in instr
    assert "page 1 and page 2, page_count 2, so the header is 1 of 2" in instr
    assert "all page 1, page_count 3, so the header is 1 of 3" in instr
    assert "do not paginate with 下一步" in instr  # card 1 scrolling card
    assert "page 1 / 2 / 3" not in instr
