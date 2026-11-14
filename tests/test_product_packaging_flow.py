"""product-to-packaging flow (Lovart e304e2fa7d22fc6c560d3ba1cb628423f03ebc46, skill 2q60dfulue4g).

Lovart's Product to Packaging System on one product photo (「用这张产品图做一套包装。」): one ask card
of three questions (1 of 3, nothing preselected, free-text last row, question 3 multi-select), then
GPT Image 2.6 Sunburst delivers 4 images: the anchor (3:4) and three extensions of it (4:3).

Question 1's product noun and the options of questions 1 and 2 are written from the product photo
(Lovart: 「这瓶滴管产品」, 护肤精华油 / 口服酊剂 / 香氛, 琥珀棕 / 琥珀为主 / 深墨绿); the server keeps them and
locks everything else.

$0: no WaveSpeed call. submit_command and the run approval are mocked. Pins and the untouched
files are locked by literal sha256 values (no historical git objects, so a depth-1 clone works);
bot/skill_output.py is pinned to the #905 revision.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from pathlib import Path

import pytest

from ComfyArt.api import bot_asks, paid_guard
from ComfyArt.api import product_packaging as pk
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import GUARD_CHAT_ID

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"
SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"

# Lovart e304e2fa card (question-card-1-*.png; notes.txt Q&A log), verbatim. Live parts as Lovart wrote them
# for the dropper bottle.
LOVART_Q1 = "这瓶滴管产品具体是什么？品牌名/产品名怎么定（直接决定包装上的文案与必要信息版面）"
LOVART_Q1_OPTS = ["护肤精华油 / Serum（30ml 滴管瓶）", "口服酊剂 / 保健滴剂", "香氛 / 身体护理油"]
LOVART_Q2 = "包装的主色方向选哪个？"
LOVART_Q2_OPTS = ["琥珀棕 ＋ 暖沙白，延续产品照片", "琥珀为主 ＋ 蓝色品牌色点缀", "深墨绿 ＋ 暖沙白"]
LOVART_Q3 = "这套包装要交付到哪个范围？（可多选）"
LOVART_Q3_OPTS = ["核心三件：外盒 ＋ 瓶标 ＋ 内托", "延伸件：运输箱 ＋ 手提袋 ＋ 封条/感谢卡",
                  "变体家族：同系列多支 / 多香型陈列", "技术件：标注尺寸的结构的构图纸 ＋ 平面刀版稿"]
PLACEHOLDERS = {
    "zh": ["自己填：品类 ＋ 品牌名 ＋ 产品名（不给的话我会先提案一版）...", "其它方向...", "其它，请直接输入..."],
    "en": ["Write your own: category + brand name + product name (if not, I'll propose one first)...",
           "Another direction...", "Other, type it here..."],
}
# en UI only (Lovart showed zh): our translation, locked the same way.
EN_Q1 = ("What exactly is this dropper product? How should the brand name / product name be set "
         "(it decides the copy and the required-info layout on the packaging)")
EN_Q2 = "Which main color direction for the packaging?"
EN_Q3 = "Which scope should this packaging set cover? (multi-select)"
EN_Q3_OPTS = ["Core three: outer box + bottle label + inner tray",
              "Extensions: shipping carton + tote bag + seal / thank-you card",
              "Variant family: several in the same line / multi-scent display",
              "Technical: dimensioned structural drawing + flat dieline"]
# Default / missing-noun fallback (product #930: not Lovart's dropper-bottle noun).
FALLBACK_Q1 = "这款产品具体是什么？品牌名/产品名怎么定（直接决定包装上的文案与必要信息版面）"
FALLBACK_Q1_EN = ("What exactly is this product? How should the brand name / product name be set "
                  "(it decides the copy and the required-info layout on the packaging)")
FIXED = {"zh": (LOVART_Q1, LOVART_Q2, LOVART_Q3, LOVART_Q3_OPTS), "en": (EN_Q1, EN_Q2, EN_Q3, EN_Q3_OPTS)}
IDS = ["pk_product", "pk_color", "pk_scope"]


def _opts(labels):
    return [{"id": "ABCD"[i], "label": lb} for i, lb in enumerate(labels)]


# What Lovart's own card would look like as an ask_user call.
LOVART_CALL = {
    "questions": [
        {"id": "pk_product", "prompt": LOVART_Q1, "options": _opts(LOVART_Q1_OPTS), "page": 1, "allow_other": True},
        {"id": "pk_color", "prompt": LOVART_Q2, "options": _opts(LOVART_Q2_OPTS), "page": 1, "allow_other": True},
        {"id": "pk_scope", "prompt": LOVART_Q3, "options": _opts(LOVART_Q3_OPTS), "page": 1, "allow_other": True,
         "min_selections": 1, "max_selections": 4},
    ],
    "page_count": 3, "allow_skip": True,
}
EN_LIVE = {
    "pk_product": ["Skincare serum oil / Serum (30ml dropper bottle)", "Oral tincture / wellness drops", "Fragrance / body oil"],
    "pk_color": ["Amber brown + warm sand white, from the product photo", "Mostly amber + a blue brand accent",
                 "Deep ink green + warm sand white"],
}
EN_CALL = {
    "questions": [
        {"id": "pk_product", "prompt": EN_Q1, "options": _opts(EN_LIVE["pk_product"])},
        {"id": "pk_color", "prompt": EN_Q2, "options": _opts(EN_LIVE["pk_color"])},
        {"id": "pk_scope", "prompt": EN_Q3, "options": _opts(EN_Q3_OPTS), "max_selections": 4},
    ],
    "page_count": 3, "allow_skip": True,
}
LIVE = {"zh": {"pk_product": LOVART_Q1_OPTS, "pk_color": LOVART_Q2_OPTS}, "en": EN_LIVE}
CALL = {"zh": LOVART_CALL, "en": EN_CALL}


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("WAVESPEED_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def _instructions() -> str:
    m = re.search(r"\{ id: 'product-to-packaging', name: t\('skills.productToPackaging'\), instructions: '((?:\\.|[^'\\])*)'", SKILLS)
    assert m, "product-to-packaging instructions did not parse"
    return m.group(1).replace("\\n", "\n").replace("\\'", "'").replace("\\\\", "\\")


def _with_lang(lang: str | None, goal_text: str, fn):
    chat = paid_guard.noturn_key(f"pk-{uuid.uuid4().hex}")
    token = GUARD_CHAT_ID.set(chat)
    try:
        if lang is not None:
            paid_guard.begin_turn(chat, text=goal_text, provider_text="", lang=lang)
        return fn()
    finally:
        GUARD_CHAT_ID.reset(token)
        paid_guard.TURNS.pop(chat, None)


def _assert_card(spec: dict, lang: str, q1: str | None = None, live: dict | None = None, scope_labels: list | None = None) -> None:
    p1, p2, p3, scope = FIXED[lang]
    assert spec["page_count"] == 3
    assert spec["allow_skip"] is True
    assert "defaults" not in spec
    qs = spec["questions"]
    assert [q["id"] for q in qs] == IDS
    assert [q["prompt"] for q in qs] == [q1 or p1, p2, p3]
    assert spec["prompt"] == qs[0]["prompt"]
    for q, placeholder in zip(qs, PLACEHOLDERS[lang]):
        assert q["page"] == 1 and q["allow_other"] is True, q["id"]
        assert q["placeholder"] == placeholder, q["id"]
        assert "defaults" not in q, q["id"]
        assert not any(o.get("recommended") for o in q["options"]), q["id"]
        assert not any("推荐" in o["label"] or "ecommended" in o["label"] for o in q["options"]), q["id"]
    assert [o["label"] for o in qs[2]["options"]] == (scope_labels or scope)
    assert [o["id"] for o in qs[2]["options"]] == ["A", "B", "C", "D"]
    assert qs[2]["min_selections"] == 1 and qs[2]["max_selections"] == 4  # 可多选
    for q in qs[:2]:
        if live is not None:
            assert [o["label"] for o in q["options"]] == live[q["id"]], q["id"]
        if q["options"]:
            assert [o["id"] for o in q["options"]] == ["A", "B", "C"][:len(q["options"])]
            assert q["min_selections"] == 1 and q["max_selections"] == 1, q["id"]


# --- card ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["zh", "en"])
def test_lovart_card_goes_through_unchanged(lang):
    """Lovart's own card (as an ask_user call) is the card we show: titles, options, placeholders."""
    spec = _with_lang(lang, "", lambda: bot_asks.validate_spec(json.loads(json.dumps(CALL[lang]))))
    _assert_card(spec, lang, live=LIVE[lang])


def test_zh_fixed_text_is_lovart_e304e2fa_verbatim():
    zh = {q["id"]: q for q in pk.CARD["zh"]}
    # Q1 noun is live from the photo; the locked default is the generic fallback.
    assert zh["pk_product"]["prompt"] == FALLBACK_Q1
    assert pk.FALLBACK_SUBJECT["zh"] + pk.PRODUCT_REST["zh"] == FALLBACK_Q1
    assert pk.LOVART_SUBJECT["zh"] + pk.PRODUCT_REST["zh"] == LOVART_Q1
    assert zh["pk_color"]["prompt"] == LOVART_Q2
    assert zh["pk_scope"]["prompt"] == LOVART_Q3
    assert [o["label"] for o in zh["pk_scope"]["options"]] == LOVART_Q3_OPTS
    assert [zh[i]["placeholder"] for i in IDS] == PLACEHOLDERS["zh"]
    assert zh["pk_product"]["options"] is None and zh["pk_color"]["options"] is None  # live, from the photo
    assert pk.PAGE_COUNT == 3


@pytest.mark.parametrize("lang,ui,goal", [("zh", "zh", ""), ("en", "en", ""), ("zh", "en", "用这张产品图做一套包装。"),
                                          ("en", "zh", "Make a packaging set from this product photo.")])
def test_model_card_is_rewritten_to_the_locked_skeleton_in_the_ask_card_language(lang, ui, goal):
    # A sloppy model card: short titles, pages 1/2/3, a default, a recommended flag, 4 options,
    # invented question-3 options, an extra invented question, allow_skip false.
    raw = {
        "questions": [
            {"id": "q1", "prompt": "这瓶滴管产品具体是什么？品牌名/产品名怎么定",
             "options": [{"id": "1", "label": "护肤精华油（推荐）", "recommended": True}, {"id": "2", "label": "口服酊剂"},
                         {"id": "3", "label": "香氛"}, {"id": "4", "label": "发油"}], "defaults": ["1"], "page": 1},
            {"id": "pk_color", "prompt": "主色？", "options": [{"id": "a", "label": "琥珀棕"}, {"id": "b", "label": "深墨绿"}], "page": 2},
            {"id": "pk_scope", "prompt": "交付范围？", "options": [{"id": "a", "label": "只要外盒"}, {"id": "b", "label": "全套"}],
             "page": 3, "max_selections": 1},
            {"id": "q4", "prompt": "要不要烫金？", "options": [{"id": "a", "label": "要"}, {"id": "b", "label": "不要"}], "page": 3},
        ],
        "page_count": 4,
        "allow_skip": False,
    }
    spec = _with_lang(ui, goal, lambda: bot_asks.validate_spec(raw))
    # Q3 wording is live per letter (matched by position here); wrong language -> reference wording.
    # The raw Q1 noun is zh (这瓶滴管产品); kept on a zh card, generic fallback on an en card.
    scope = ["只要外盒", "全套"] + LOVART_Q3_OPTS[2:] if lang == "zh" else EN_Q3_OPTS
    q1 = LOVART_Q1 if lang == "zh" else FALLBACK_Q1_EN
    _assert_card(spec, lang, q1=q1, scope_labels=scope)
    qs = spec["questions"]
    assert [o["label"] for o in qs[0]["options"]] == ["护肤精华油", "口服酊剂", "香氛"]  # live, cut to 3, no 推荐
    assert [o["label"] for o in qs[1]["options"]] == ["琥珀棕", "深墨绿"]
    assert "要不要烫金" not in json.dumps(spec, ensure_ascii=False)


@pytest.mark.parametrize("prompt,lang,expected", [
    (LOVART_Q1, "zh", LOVART_Q1),
    ("这罐面霜具体是什么？品牌名/产品名怎么定（直接决定包装上的文案与必要信息版面）", "zh",
     "这罐面霜具体是什么？品牌名/产品名怎么定（直接决定包装上的文案与必要信息版面）"),
    ("这款蓝牙耳机具体是什么？品牌名/产品名怎么定", "zh",
     "这款蓝牙耳机具体是什么？品牌名/产品名怎么定（直接决定包装上的文案与必要信息版面）"),
    ("What exactly is this jar of face cream? How should the brand name / product name be set", "en",
     "What exactly is this jar of face cream? How should the brand name / product name be set "
     "(it decides the copy and the required-info layout on the packaging)"),
    ("", "zh", FALLBACK_Q1),  # no noun written: generic fallback, not the dropper-bottle noun
    ("", "en", FALLBACK_Q1_EN),
    ("What exactly is this jar of face cream? How should the brand name / product name be set", "zh", FALLBACK_Q1),  # other language
    ("这罐面霜具体是什么？品牌名/产品名怎么定", "en", FALLBACK_Q1_EN),
])
def test_question_1_keeps_the_product_noun_from_the_photo(prompt, lang, expected):
    raw = {"questions": [{"id": "pk_product", "prompt": prompt or "x", "options": _opts(["a", "b", "c"])}]}
    spec = pk.card_spec(raw["questions"], lang)
    assert spec["questions"][0]["prompt"] == expected


def test_live_options_need_two_else_the_question_is_free_text():
    spec = bot_asks.validate_spec(pk.card_spec([{"id": "pk_color", "prompt": LOVART_Q2, "options": [{"id": "a", "label": "only"}]}], "zh"))
    q = spec["questions"][1]
    assert q["options"] == [] and q["allow_other"] is True and q["placeholder"] == "其它方向..."
    assert spec["questions"][0]["options"] == []  # question 1 was not sent: free text with its placeholder


def test_legacy_single_question_call_becomes_the_full_card():
    raw = {"prompt": LOVART_Q2, "options": _opts(LOVART_Q2_OPTS), "defaults": ["A"]}
    spec = _with_lang("zh", "", lambda: bot_asks.validate_spec(raw))
    _assert_card(spec, "zh", q1=FALLBACK_Q1)
    assert [o["label"] for o in spec["questions"][1]["options"]] == LOVART_Q2_OPTS


def test_unknown_ui_language_defaults_to_zh():
    spec = _with_lang(None, "", lambda: bot_asks.validate_spec({"questions": [{"id": "pk_scope", "prompt": "x", "allow_other": True}]}))
    _assert_card(spec, "zh", q1=FALLBACK_Q1)


def test_other_skill_cards_are_untouched():
    raw = {"questions": [{"id": "look", "prompt": "模特长相方向选哪一档？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}],
                          "defaults": ["A"]}], "page_count": 3}
    assert pk.normalize_card(dict(raw)) == raw
    spec = bot_asks.validate_spec(dict(raw))
    assert spec["questions"][0]["prompt"] == "模特长相方向选哪一档？"
    assert spec["questions"][0]["defaults"] == ["A"]
    from ComfyArt.api import portrait_studio as ps
    portrait = _with_lang("zh", "", lambda: bot_asks.validate_spec(ps.card_spec("zh")))
    assert [q["id"] for q in portrait["questions"]] == ["ps_shots", "ps_outfit", "ps_scene"]


def _visible(payload: dict) -> list[str]:
    out: list[str] = [str(payload.get("prompt") or "")]
    for q in payload.get("questions") or []:
        for key in ("prompt", "placeholder", "title"):
            if q.get(key):
                out.append(str(q[key]))
        for opt in q.get("options") or []:
            for key in ("label", "description"):
                if opt.get(key):
                    out.append(str(opt[key]))
    return out


_DEBUG = ("pk_product", "pk_color", "pk_scope", "e304e2fa", "review-assets", "Lovart", "lovart",
          "product-to-packaging", "dry-run", "skill", "debug", "id ")


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_card_is_one_language_and_has_no_debug_copy(lang):
    other = "en" if lang == "zh" else "zh"
    card = _with_lang(lang, "", lambda: bot_asks.validate_spec(json.loads(json.dumps(CALL[lang]))))
    visible = "\n".join(_visible(card))
    p1, p2, p3, scope = FIXED[other]
    for text in (p1, p2, p3, *scope, *PLACEHOLDERS[other]):
        assert text not in visible
    assert bool(re.search(r"[\u4e00-\u9fff]", visible)) is (lang == "zh")
    for needle in _DEBUG:
        assert needle not in visible, needle


def test_no_reference_brand_name_in_shared_ask_and_bot_files():
    for path in ("api/ask_store.py", "api/bot_asks.py", "src/bot.ts"):
        assert "lovart" not in (ROOT / path).read_text(encoding="utf-8").lower(), path


# --- skill text ----------------------------------------------------------------------------------

def test_skill_text_carries_the_card_and_default_4():
    instr = _instructions()
    for qid, prompt, placeholder in zip(IDS, (FALLBACK_Q1, LOVART_Q2, LOVART_Q3), PLACEHOLDERS["zh"]):
        assert f'id "{qid}"' in instr and prompt in instr and placeholder in instr, qid
    assert "这款产品 is only the fallback when it cannot be identified" in instr
    assert "as is for a dropper bottle" not in instr
    assert 'prompt "这瓶滴管产品具体是什么' not in instr
    for label in LOVART_Q3_OPTS:  # the reference wording, as the example for a dropper bottle
        assert f'label:"{label}"' in instr, label
    assert "exactly four options in this order: A 核心三件, B 延伸件, C 变体家族, D 技术件" in instr
    assert "a box or pouch has no 瓶标 or 多香型" in instr
    assert "round-robin in A-D order" in instr and "pk_scope skipped or not answered: A." in instr
    assert "image_plan" in instr and "This image shows:" in instr
    assert LOVART_Q1_OPTS[0] in instr and LOVART_Q2_OPTS[0] in instr  # examples of live options
    assert instr.index('id "pk_product"') < instr.index('id "pk_color"') < instr.index('id "pk_scope"')
    assert "page_count 3, so the header is 1 of 3" in instr
    assert "min_selections 1, max_selections 4" in instr
    assert "Do not set defaults or recommended" in instr and "none is marked 推荐" in instr
    assert "default 4 images" in instr and "one generate_image call per image with count 1" in instr
    assert "Image 1 is the anchor" in instr and "image 1 3:4, images 2-4 4:3" in instr
    assert 'skill: "product-to-packaging"' in instr
    for needle in ("recommended: true", '"recommended"', "defaults: ["):
        assert needle not in instr
    # The original lines 1)-4) are kept as they were on main.
    for line in ("1) Intake: require productImage; optional packNotes.",
                 "2) Deliver: structure/dieline logic, front hero, and shelf row when asked (box/bottle/pouch presets).",
                 "3) Identity: keep product silhouette and label cues honest to the upload.",
                 "4) Cross-link: this starts from product truth; brief-only packaging stays on packaging."):
        assert line in instr
    assert "5) Refs: pass product shape id in refs on every generate_image call." not in instr


def test_default_output_is_4_images_anchor_then_extensions():
    assert pk.DEFAULT_IMAGES == 4
    assert pk.RATIOS == ("3:4", "4:3", "4:3", "4:3")
    assert [pk.ratio_for(i) for i in range(4)] == list(pk.RATIOS)
    assert paid_guard.DEFAULT_CAP >= pk.DEFAULT_IMAGES  # the 4 calls fit the default turn cap


# --- one call per image: anchor 3:4 then 4:3, Sunburst, 2k ----------------------------------------

SENT: list = []
APPROVALS: list = []


@pytest.fixture
def relay(monkeypatch):
    SENT.clear()
    APPROVALS.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        return {"ids": [f"shape:g{len(SENT)}"], "model": args.get("edit_model") or args.get("model")}

    async def approval(label):
        APPROVALS.append(label)
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", approval)


def _run_turn(lang, calls):
    async def go():
        return [await canvas.TOOLS["generate_image"]["handler"](dict(a)) for a in calls]
    return _with_lang(lang, "", lambda: asyncio.run(go()))


def _call(prompt, refs=None, **extra):
    a = {"prompt": prompt, "skill": "product-to-packaging", "count": 1, **extra}
    if refs is not None:
        a["refs"] = refs
    return a


def test_with_product_photo_4_calls_anchor_3x4_then_4x3_sunburst_edit_2k(relay):
    calls = [_call("anchor: box + bottle key visual", ["shape:product"]),
             _call("outer box multi-angle board", ["shape:product", "shape:anchor"]),
             _call("bottle label close-ups", ["shape:anchor"]),  # model dropped the product photo
             _call("unboxing with inner tray", ["shape:product", "shape:anchor"])]
    _run_turn("zh", calls)
    assert [a for a, _ in SENT] == ["generate_image"] * 4
    reqs = [r for _, r in SENT]
    assert [r["ratio"] for r in reqs] == ["3:4", "4:3", "4:3", "4:3"]
    for r in reqs:
        assert r["edit_model"] == SUNBURST_EDIT and r.get("model") != SUNBURST_T2I
        assert r["edit_resolution"] == "2k"
        assert r["count"] == 1
        assert "width" not in r and "height" not in r and "size_lock" not in r
        assert r["refs"][0] == "shape:product"  # the turn's product photo stays first
    assert reqs[0]["refs"] == ["shape:product"]
    assert all(r["refs"] == ["shape:product", "shape:anchor"] for r in reqs[1:])
    assert [r["prompt"] for r in reqs] == [c["prompt"] for c in calls]  # prompts are the model's


def test_without_product_photo_anchor_is_text_to_image(relay):
    _run_turn("en", [_call("anchor"), _call("box board", ["shape:anchor"])])
    first, second = SENT[0][1], SENT[1][1]
    assert first["model"] == SUNBURST_T2I and "edit_model" not in first and "refs" not in first
    assert (first["ratio"], first["edit_resolution"]) == ("3:4", "2k")
    assert second["edit_model"] == SUNBURST_EDIT and second["refs"] == ["shape:anchor"]
    assert (second["ratio"], second["edit_resolution"]) == ("4:3", "2k")


def test_model_size_args_are_replaced(relay):
    _run_turn("zh", [_call("anchor", ["shape:p"], width=1024, height=1024, ratio="1:1", resolution="4k", edit_resolution="1k"),
                     _call("ext", ["shape:p"], ratio="3:4", width=1536, height=2048)])
    a, b = SENT[0][1], SENT[1][1]
    assert (a["ratio"], a["edit_resolution"]) == ("3:4", "2k") and "resolution" not in a and "width" not in a
    assert (b["ratio"], b["edit_resolution"]) == ("4:3", "2k") and "width" not in b


def test_a_new_turn_starts_a_new_set(relay):
    _run_turn("zh", [_call("anchor", ["shape:p1"]), _call("ext", ["shape:p1"])])
    _run_turn("zh", [_call("anchor 2", ["shape:p2"])])
    assert [r["ratio"] for _, r in SENT] == ["3:4", "4:3", "3:4"]
    assert SENT[2][1]["refs"] == ["shape:p2"]


def test_a_fallback_retry_keeps_the_image_place():
    def go():
        a = pk.lock_request(_call("anchor", ["shape:p"]))
        b = pk.lock_request({**_call("anchor", ["shape:p"]), "fallback_for": "x/y"})
        c = pk.lock_request(_call("ext", ["shape:p"]))
        return a, b, c
    a, b, c = _with_lang("zh", "", go)
    assert (a["ratio"], b["ratio"], c["ratio"]) == ("3:4", "3:4", "4:3")
    assert a["count"] == b["count"] == c["count"] == 1


def test_count_is_one_per_call():
    out = _with_lang("zh", "", lambda: pk.lock_request(_call("anchor", ["shape:p"], count=3)))
    assert out["count"] == 1 and out["ratio"] == "3:4"


@pytest.mark.parametrize("skill", [None, "studio-model", "portrait-studio", "packaging-design-director", "ai-model"])
def test_other_skills_are_not_locked(relay, skill):
    args = {"prompt": "x", "count": 1, "refs": ["shape:a"], "ratio": "1:1"}
    if skill:
        args["skill"] = skill
    before = dict(pk._LOCKS)
    _run_turn("zh", [args, args])
    assert pk._LOCKS == before
    if skill in (None, "studio-model", "packaging-design-director"):
        assert all(r.get("ratio") == "1:1" for _, r in SENT), SENT


# --- goal self-check: counts the 4 images like any delivery (#926 rules) -------------------------

def _blocks(*results):
    out = []
    for n, (tool, data, status) in enumerate(results):
        out.append({"type": "tool_use", "id": f"t{n}", "name": f"mcp__comfyart__{tool}", "input": {"skill": "product-to-packaging"}})
        res = {"type": "tool_result", "id": f"t{n}", "name": f"mcp__comfyart__{tool}", "text": json.dumps(data, ensure_ascii=False)}
        if status:
            res["status"] = status
        out.append(res)
    return out


def _delivery(n):
    steps = [("generate_image", {"ids": [f"j{i}"]}, None) for i in range(n)]
    steps += [("wait_generation", {"results": [{"id": f"j{i}", "status": "done", "shapes": [{"id": f"shape:{i}"}]}
                                               for i in range(n)]}, None)]
    return _blocks(*steps)


@pytest.mark.parametrize("goal,expected", [("帮我做 4 张包装图", 4), ("Make 4 packaging images from this product photo", 4)])
def test_self_check_counts_the_set(goal, expected):
    from ComfyArt.bot import self_check
    sc = self_check.check(goal, _delivery(4))
    assert sc.applies and sc.goal.count == expected and sc.generated == 4 and sc.passed
    short = self_check.check(goal, _delivery(3))
    assert short.applies and short.generated == 3 and not short.passed


def test_self_check_on_the_reference_request_passes_the_4_image_set():
    from ComfyArt.bot import self_check
    for goal in ("用这张产品图做一套包装。", "Make a packaging set from this product photo."):
        sc = self_check.check(goal, _delivery(4))
        assert sc.applies and (sc.goal.kind, sc.goal.count) == ("image", 1)  # no number in the request: at least 1
        assert sc.generated == 4 and sc.passed
        assert not self_check.check(goal, _delivery(0)).passed


@pytest.mark.parametrize("lang,goal,warn", [("zh", "帮我做 4 张包装图", "目标核对未通过"), ("en", "Make 4 packaging images", "Goal check failed")])
def test_self_check_still_reports_a_failed_set(lang, goal, warn):
    from ComfyArt.bot import self_check
    blocks = _blocks(("generate_image", {"ids": ["j1"], "submitted": True}, None),
                     ("wait_generation", {"results": [{"id": "j1", "status": "error", "error": "content filter"}]}, "error"))
    blocks.append({"type": "text", "text": "完成。" if lang == "zh" else "Done."})
    out, info = self_check.apply_to_blocks(goal, blocks, lang)
    assert info["self_check"] == "fail" and info["generated"] == 0 and info["expected"] == 4, info
    notes = [b for b in out if b.get("type") == "notice"]
    assert len(notes) == 1 and notes[0]["text"].startswith(warn)


# --- untouched -----------------------------------------------------------------------------------

# #935: a shallow (depth-1) clone has no e8c4a855 object. These locks used to run
# read e8c4a855:<path> from history and compared bytes; they are now literal sha256 values
# computed once from those same pinned bytes. A one-byte edit still fails.
PINNED_SHA256 = {
    "api/auto_models.json": "9ef106b6133d427f04347d0c31c31931e641e1cd47d2a86c0d0769cde48c5d7b",
    "api/skill_size.py": "43c130b1aa05cd6736d28564e743feaa41e0ce26e61ea2ad0960ada01203c3df",
    "api/curated_models.json": "fb5c6a1acd2782cb3d7da42837bef92bd4485fe90abd84dd272de1170f9fe04b",
    "api/wavespeed_models.json": "8be944b91aeaf2f4fc24fb5099e36664d2136004dc828737c95ff7943a7363fb",
    "bot/skill_output.py": "5bddf4a22f1971d1de6da7395fa88a3a2ac3643205cab07ca0a5d14e960789ec",  # #905 size-notice; #974 multi-angle; #978 template block is not user intent
    "api/portrait_studio.py": "61257848a9e23d13c066d01c103c565d6804e58c926d3905c6ed8b0890569224",
    "bot/self_check.py": "1a9b4f7eda7e915adf83df42ff31ccf3c27e83253d9636ba5c85aead447993b6",
}


@pytest.mark.parametrize("path", ["api/auto_models.json", "api/skill_size.py", "api/curated_models.json",
                                  "api/wavespeed_models.json"])
def test_pins_sizes_and_model_tables_match_pinned_sha256(path):
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == PINNED_SHA256[path], path


@pytest.mark.parametrize("path", ["api/portrait_studio.py", "bot/self_check.py", "bot/skill_output.py"])
def test_portrait_studio_and_self_check_match_pinned_sha256(path):
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == PINNED_SHA256[path], path


# Locales are compared as JSON so a sibling skill can add its own keys. product-to-packaging
# still adds none. Allowed extras only:
# - youtube-channel-banner: bot.composeBannerText
# - portrait-studio redo/follow-up (#927): bot.portraitStudioPlan / Done / Redo
# - #943: runStop.stillGenerating
BANNER_LOCALE = {"zh": "排版横幅文字", "en": "Set banner text"}
PORTRAIT_LOCALE = {
    "zh": {
        "bot.portraitStudioPlan": "形象照方案",
        "bot.portraitStudioDone": "形象照小结",
        "bot.portraitStudioRedo": "重做一张",
    },
    "en": {
        "bot.portraitStudioPlan": "Portrait plan",
        "bot.portraitStudioDone": "Portrait summary",
        "bot.portraitStudioRedo": "Redo one image",
    },
}
RUN_STOP_LOCALE = {
    "zh": "图片还在生成，生成好后会自动出现在画布上，不会重复扣费。",
    "en": "The image is still generating. It will appear on the canvas when it's ready, with no extra charge.",
}
LOCALE_EXTRAS = {
    lang: {"bot.composeBannerText": BANNER_LOCALE[lang], **PORTRAIT_LOCALE[lang],
           "runStop.stillGenerating": RUN_STOP_LOCALE[lang]}
    for lang in ("zh", "en")
}
# sha256 of the canonical JSON of main e8c4a855's locale files (minus the extras above).
LOCALE_BASE_SHA256 = {
    "src/locales/zh.json": "4a96ca4d146ccb8c8a336c643ebd9e1d830ebee5d843d5f5719062209472755a",
    "src/locales/en.json": "887b52a29e5a337c54d2ca86e650971eea7e78a7acb71cafd78ac984eca4369e",
}


def _canonical_json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


@pytest.mark.parametrize("path,lang", [("src/locales/zh.json", "zh"), ("src/locales/en.json", "en")])
def test_locales_match_pinned_sha256_except_allowed_extras(path, lang):
    ours = json.loads((ROOT / path).read_text(encoding="utf-8"))
    extras = LOCALE_EXTRAS[lang]
    assert {k: ours.get(k) for k in extras} == extras, path
    base = {k: v for k, v in ours.items() if k not in extras}
    assert hashlib.sha256(_canonical_json(base)).hexdigest() == LOCALE_BASE_SHA256[path], path


# --- question 3: live wording per letter, locked skeleton (Product, final) ----------------------

BOX_Q3 = ["核心三件：外盒 ＋ 内衬 ＋ 封口贴", "延伸件：快递箱 ＋ 手提袋 ＋ 感谢卡",
          "变体家族：同系列多口味 / 礼盒装", "技术件：标注尺寸的结构图 ＋ 平面刀版稿"]


def _q3(options, lang="zh"):
    spec = pk.card_spec([{"id": "pk_scope", "prompt": LOVART_Q3, "options": options}], lang)
    return _with_lang(lang, "", lambda: bot_asks.validate_spec(spec))["questions"][2]


def test_q3_model_wording_is_used():
    q = _q3(_opts(BOX_Q3))
    assert [o["label"] for o in q["options"]] == BOX_Q3
    assert q["prompt"] == LOVART_Q3 and q["placeholder"] == "其它，请直接输入..."
    assert (q["min_selections"], q["max_selections"]) == (1, 4) and q["allow_other"] is True
    assert not any("瓶标" in o["label"] or "多香型" in o["label"] for o in q["options"])
    en = _q3(_opts(["Core three: pouch + label + mailer", "Extensions: carton + bag + card",
                    "Variant family: flavors", "Technical: dieline + drawing"]), "en")
    assert [o["label"] for o in en["options"]][0] == "Core three: pouch + label + mailer"


@pytest.mark.parametrize("bad", [None, "", "   ", "Core three: box", "（推荐）"])
def test_q3_falls_back_per_missing_option(bad):
    opts = _opts(BOX_Q3)
    if bad is None:
        opts = [o for o in opts if o["id"] != "B"]  # B missing
    else:
        opts[1]["label"] = bad  # B empty / wrong language / only a 推荐 marker
    q = _q3(opts)
    assert [o["label"] for o in q["options"]] == [BOX_Q3[0], LOVART_Q3_OPTS[1], BOX_Q3[2], BOX_Q3[3]]
    en = _q3(_opts(BOX_Q3), "en")  # all zh wording on an en card -> every option falls back
    assert [o["label"] for o in en["options"]] == EN_Q3_OPTS


def test_q3_skeleton_cannot_be_reordered_or_expanded():
    reordered = [{"id": i, "label": BOX_Q3["ABCD".index(i)]} for i in "DCBA"]
    q = _q3(reordered + [{"id": "E", "label": "其它：多一个"}, {"id": "F", "label": "再来一个"}])
    assert [o["id"] for o in q["options"]] == ["A", "B", "C", "D"]
    assert [o["label"] for o in q["options"]] == BOX_Q3  # each wording stays on its own letter
    six = _q3([{"id": str(n), "label": f"第{n}项：内容"} for n in range(6)])
    assert [o["id"] for o in six["options"]] == ["A", "B", "C", "D"]
    assert [o["label"] for o in six["options"]] == [f"第{n}项：内容" for n in range(4)]
    assert _q3([])["options"] == [{"id": i, "label": lb} for i, lb in zip("ABCD", LOVART_Q3_OPTS)]
    for o in _q3([{"id": "A", "label": "核心三件：外盒", "recommended": True}])["options"]:
        assert set(o) == {"id", "label"}


# --- images 2-4 follow the Q3 answer (Product point 4) -------------------------------------------

def _spec_with_q3(labels=LOVART_Q3_OPTS):
    return bot_asks.validate_spec(pk.card_spec([{"id": "pk_scope", "prompt": LOVART_Q3, "options": _opts(labels)}], "zh"))


def _answered_turn(answers, labels=LOVART_Q3_OPTS, calls=4):
    """ask_user answered in this turn, then `calls` generate_image calls through the per-image hook."""
    def go():
        plan = pk.record_card_answer(_spec_with_q3(labels), answers)
        reqs = [pk.lock_request(_call(f"image {n + 1}", ["shape:p"])) for n in range(calls)]
        return plan, reqs
    return _with_lang("zh", "", go)


def _shows(req):
    lines = [ln for ln in req["prompt"].split("\n") if ln.startswith(pk.SHOWS_HEAD)]
    assert len(lines) <= 1
    return lines[0][len(pk.SHOWS_HEAD):].strip().rstrip(".") if lines else None


def _sel(*letters, other=""):
    a = {"selected": list(letters)}
    if other:
        a["other_text"] = other
    return {"pk_product": {"selected": ["A"]}, "pk_color": {"selected": ["A"]}, "pk_scope": a}


@pytest.mark.parametrize("answers,expected", [
    (_sel("A"), ["外盒", "瓶标", "内托"]),
    (_sel("B"), ["运输箱", "手提袋", "封条/感谢卡"]),
    (_sel("B", "A"), ["外盒; 内托", "运输箱; 手提袋; 封条/感谢卡", "瓶标"]),  # A-D order, round-robin
    ({}, ["外盒", "瓶标", "内托"]),  # whole card skipped -> A
    (_sel(), ["外盒", "瓶标", "内托"]),  # Q3 not answered -> A
    (None, ["外盒", "瓶标", "内托"]),
    (_sel(other="金属礼盒"), ["金属礼盒", "金属礼盒", "金属礼盒"]),  # free text alone is the scope
    (_sel("A", other="金属礼盒"), ["外盒; 内托", "金属礼盒", "瓶标"]),  # free text counts after D
])
def test_extension_images_follow_the_q3_answer(answers, expected):
    plan, reqs = _answered_turn(answers)
    assert [r["ratio"] for r in reqs] == ["3:4", "4:3", "4:3", "4:3"]
    assert _shows(reqs[0]) is None  # three scopes or fewer: the anchor is the model's own prompt
    assert plan[0] == pk.ANCHOR_PLAN
    assert [_shows(r) for r in reqs[1:]] == expected
    assert plan[1:] == expected and len(plan) == 4
    for n, r in enumerate(reqs):
        assert r["prompt"].startswith(f"image {n + 1}")


def test_extension_images_use_the_wording_shown_on_the_card():
    _, reqs = _answered_turn(_sel("A"), labels=BOX_Q3)
    assert [_shows(r) for r in reqs[1:]] == ["外盒", "内衬", "封口贴"]


def test_shows_line_is_replaced_not_stacked_and_kept_on_retry():
    def go():
        pk.record_card_answer(_spec_with_q3(), _sel("B"))
        a = pk.lock_request(_call("anchor", ["shape:p"]))
        b = pk.lock_request(_call("x\nThis image shows: something else.", ["shape:p"]))
        c = pk.lock_request({**_call("x", ["shape:p"]), "fallback_for": "m"})
        return a, b, c
    a, b, c = _with_lang("zh", "", go)
    assert _shows(b) == _shows(c) == "运输箱" and b["prompt"].count(pk.SHOWS_HEAD) == 1


def test_no_card_answer_this_turn_leaves_prompts_alone():
    reqs = _with_lang("zh", "", lambda: [pk.lock_request(_call(f"p{n}", ["shape:p"])) for n in range(4)])
    assert [r["prompt"] for r in reqs] == ["p0", "p1", "p2", "p3"]


def test_other_cards_record_nothing():
    def go():
        assert pk.record_card_answer({"questions": [{"id": "ps_shots"}]}, {"ps_shots": {"selected": ["A"]}}) is None
        return pk.lock_request(_call("p", ["shape:p"]))
    assert _with_lang("zh", "", go)["prompt"] == "p"


def test_ask_user_returns_the_image_plan(monkeypatch):
    from ComfyArt.api.mcp_tools import bot_tools

    async def fake_await(chat_id, state, spec):
        return {"status": "answered", "selected": [], "other_text": "", "answers": _sel("B")}
    monkeypatch.setattr(bot_tools, "_await_ask", fake_await)
    monkeypatch.setattr(bot_tools, "bot_turn_state", lambda: ("chat-x", object()))
    out = _with_lang("zh", "", lambda: asyncio.run(bot_tools.ask_user(json.loads(json.dumps(LOVART_CALL)))))
    assert out["image_plan"][1:] == ["运输箱", "手提袋", "封条/感谢卡"]
    assert "image_plan" not in _with_lang("zh", "", lambda: asyncio.run(bot_tools.ask_user(
        {"questions": [{"id": "x", "prompt": "随便问问？", "options": _opts(["a", "b"])}]})))


# --- _LOCKS only holds live turns (Tech) ----------------------------------------------------------

def test_locks_drop_ended_and_replaced_turns():
    pk._LOCKS.clear()
    chats = [paid_guard.noturn_key(f"pk-lock-{n}") for n in range(3)]
    for c in chats:  # three turns that start, use the hook, then end
        token = GUARD_CHAT_ID.set(c)
        try:
            paid_guard.begin_turn(c, text="", provider_text="", lang="zh")
            pk.lock_request(_call("p", ["shape:p"]))
            assert c in pk._LOCKS
            paid_guard.end_turn(c)
        finally:
            GUARD_CHAT_ID.reset(token)
    _with_lang("zh", "", lambda: pk.lock_request(_call("p", ["shape:p"])))
    assert not any(c in pk._LOCKS for c in chats)  # ended turns are gone
    assert len(pk._LOCKS) <= 1
    # Same chat, new turn: the old entry is replaced, not kept beside it.
    c = paid_guard.noturn_key("pk-lock-same")
    token = GUARD_CHAT_ID.set(c)
    try:
        g1 = paid_guard.begin_turn(c, text="", provider_text="", lang="zh")
        pk.lock_request(_call("p", ["shape:p"]))
        g2 = paid_guard.begin_turn(c, text="", provider_text="", lang="zh")
        out = pk.lock_request(_call("p", ["shape:p"]))
        assert out["ratio"] == "3:4" and pk._LOCKS[c]["guard"] is g2 is not g1
        assert sum(1 for lk in pk._LOCKS.values() if lk["guard"] in (g1, g2)) == 1
    finally:
        GUARD_CHAT_ID.reset(token)
        paid_guard.TURNS.pop(c, None)


# --- more than three scopes with A: the anchor is A (Product, 22:25) ------------------------------

@pytest.mark.parametrize("answers,anchor,expected", [
    # A+B+C+D (any click order): anchor A, then B / C / D, no A+D squeeze.
    (_sel("D", "C", "B", "A"), "外盒; 瓶标; 内托",
     ["运输箱; 手提袋; 封条/感谢卡", "同系列多支 / 多香型陈列", "标注尺寸的结构的构图纸; 平面刀版稿"]),
    # A+B+C+D + free text: anchor A; B, C, D, E round-robin over images 2-4 (E shares image 2 with B).
    (_sel("A", "B", "C", "D", other="金属礼盒"), "外盒; 瓶标; 内托",
     ["运输箱; 手提袋; 封条/感谢卡; 金属礼盒", "同系列多支 / 多香型陈列", "标注尺寸的结构的构图纸; 平面刀版稿"]),
    # A+B+C + free text (4 scopes incl. E): anchor A, then B / C / E.
    (_sel("A", "B", "C", other="金属礼盒"), "外盒; 瓶标; 内托",
     ["运输箱; 手提袋; 封条/感谢卡", "同系列多支 / 多香型陈列", "金属礼盒"]),
])
def test_more_than_three_scopes_with_a_put_a_on_the_anchor(answers, anchor, expected):
    plan, reqs = _answered_turn(answers)
    assert [r["ratio"] for r in reqs] == ["3:4", "4:3", "4:3", "4:3"]
    assert _shows(reqs[0]) == anchor
    assert [_shows(r) for r in reqs[1:]] == expected
    assert plan[0] == f"{pk.ANCHOR_PLAN}; it shows {anchor}" and plan[1:] == expected
    assert reqs[0]["prompt"].startswith("image 1")


def test_more_than_three_scopes_without_a_keep_the_anchor_free():
    """B+C+D + free text: no A, so the anchor has no scope line; the four share images 2-4 round-robin."""
    plan, reqs = _answered_turn(_sel("B", "C", "D", other="金属礼盒"))
    assert _shows(reqs[0]) is None and plan[0] == pk.ANCHOR_PLAN
    assert [_shows(r) for r in reqs[1:]] == ["运输箱; 手提袋; 封条/感谢卡; 金属礼盒", "同系列多支 / 多香型陈列",
                                            "标注尺寸的结构的构图纸; 平面刀版稿"]


def test_skill_text_puts_a_on_the_anchor_for_all_four():
    instr = _instructions()
    assert "More than three scopes with A among them: image 1, the anchor, is A" in instr
    assert "A+B+C+D is A / B / C / D" in instr
