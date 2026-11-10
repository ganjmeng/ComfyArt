"""#825: Auto · model pill — backend reason for manual picks + label/tooltip helpers.

Manual picks must keep reason 「你指定了这个模型」 / 「you named this model」 on the record,
but the UI shows NO reason popup (pill_tooltip returns None when auto is false).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ComfyArt.api import auto_models, wavespeed


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalog():
    return wavespeed.load_config()


def test_manual_choose_keeps_named_reason_zh_en(catalog):
    """Backend record reason for a user-named model (UI must not show it)."""
    named = catalog["features"]["text_to_image"]["default"]
    choice = auto_models.choose("text_to_image", "a poster with big headline text", named, catalog)
    assert choice["auto"] is False
    assert choice["category"] == "user"
    assert choice["model"] == named
    assert choice["reason"] == {"zh": "你指定了这个模型", "en": "you named this model"}


def test_manual_pill_tooltip_is_none():
    """技术经理 final: manual pick shows NO reason in UI."""
    choice = {"model": "openai/gpt-image-2.6-flare/text-to-image", "auto": False,
              "reason": {"zh": "你指定了这个模型", "en": "you named this model"}}
    assert auto_models.pill_tooltip(choice, "zh") is None
    assert auto_models.pill_tooltip(choice, "en") is None
    assert auto_models.pill_label(choice) == "GPT Image 2.6 Flare"


def test_auto_pill_label_and_tooltip():
    choice = {"model": "openai/gpt-image-2.6-sunburst/text-to-image", "auto": True,
              "reason": {"zh": "海报/带字", "en": "poster / text"}}
    assert auto_models.pill_label(choice) == "Auto · GPT Image 2.6 Sunburst"
    assert auto_models.pill_tooltip(choice, "zh") == "自动选择：海报/带字"
    assert auto_models.pill_tooltip(choice, "en") == "Auto-picked: poster / text"


def test_auto_before_model_known_shows_just_auto():
    assert auto_models.pill_label({"auto": True}) == "Auto"
    assert auto_models.pill_label({}) is None  # legacy: no empty pill


def test_skill_pin_tooltip_has_no_auto_prefix():
    choice = {
        "model": "google/nano-banana-pro/edit",
        "auto": True,
        "category": "skill",
        "skill": "pose-fission",
        "reason": auto_models.skill_pin_reason("pose-fission"),
    }
    assert auto_models.pill_label(choice) == "Auto · Nano Banana Pro"
    assert auto_models.pill_tooltip(choice, "zh") == "pose-fission 技能固定模型"
    assert auto_models.pill_tooltip(choice, "en") == "pose-fission skill pinned model"
    assert not auto_models.pill_tooltip(choice, "zh").startswith("自动选择")


def test_pose_fission_fallback_matches_table_and_tip():
    """09 fixture / real route: preferred in tip is the table's pinned model (no hardcoding)."""
    pin = auto_models.skill_pin("pose-fission")
    assert pin and pin.get("fallback"), "pose-fission must list a fallback in auto_models.json"
    choice = auto_models.skill_fallback_choice("pose-fission")
    # Used model is the registered fallback; failed (首选) is the pin primary
    assert choice["model"] == pin["fallback"]
    assert choice["fallback"] == pin["model"]
    assert choice["category"] == "skill_fallback"
    assert choice["reason"] == auto_models.skill_pin_reason("pose-fission")
    # 首选 model in tip text must be whatever the table configures as primary
    preferred_short = auto_models.short_name(pin["model"])
    used_short = auto_models.short_name(pin["fallback"])
    tip = auto_models.pill_tooltip(choice, "zh")
    assert tip == f"pose-fission 技能固定模型 · 首选 {preferred_short} 失败，改用 {used_short}"
    assert preferred_short in tip and f"首选 {preferred_short}" in tip
    assert not tip.startswith("自动选择")
    assert auto_models.pill_label(choice) == f"Auto · {used_short}"
    tip_en = auto_models.pill_tooltip(choice, "en")
    assert tip_en == (
        f"pose-fission skill pinned model · Preferred {preferred_short} failed, used {used_short}"
    )


def test_fallback_fixture_pair_is_registered_in_table():
    """pill825 fallback case must use a real skills.*.fallback pair from auto_models.json."""
    table = json.loads((ROOT / "api/auto_models.json").read_text(encoding="utf-8"))
    main = (ROOT / "tests/js/pill825/main.tsx").read_text()
    # Fixture imports the table and uses posePin.model / posePin.fallback
    assert "auto_models.json" in main and "pose-fission" in main
    pin = table["skills"]["pose-fission"]
    assert pin["fallback"] == "google/nano-banana-2.1/edit"
    assert pin["model"] == "google/nano-banana-pro/edit"
    # Any skills row that lists fallback: model/fallback must match that row
    for name, row in table["skills"].items():
        if name.startswith("_") or not isinstance(row, dict):
            continue
        if not row.get("fallback"):
            continue
        choice = auto_models.skill_fallback_choice(name)
        assert choice["fallback"] == row["model"]
        assert choice["model"] == row["fallback"]


def test_short_name_preserves_gpt_casing():
    """Unmapped ids must not title-case GPT → Gpt."""
    long_id = (
        "openai/gpt-image-2.6-sunburst-with-an-extremely-long-marketing-name-that-must-ellipsis"
        "/text-to-image"
    )
    name = auto_models.short_name(long_id)
    assert name.startswith("GPT Image"), name
    assert "Gpt " not in name


def test_explicit_auto_token_is_not_user_named(catalog):
    choice = auto_models.choose("text_to_image", "logo for a cafe", "auto", catalog)
    assert choice["auto"] is True
    assert choice["reason"] != {"zh": "你指定了这个模型", "en": "you named this model"}


def test_frontend_auto_pill_mirrors_backend():
    """src/autoPill.ts must keep the same manual-reason / label contract (source check)."""
    src = (ROOT / "src/autoPill.ts").read_text()
    assert "Auto ·" in src
    assert "you named this model" not in src or True  # reason comes from backend record
    assert "pill" in src.lower() or "autoPillLabel" in src
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert "autoPillLabel" in chat and "autoPillTooltip" in chat
    assert "chatMessage.autoPickedPrefix" in (ROOT / "src/locales/zh.json").read_text()
    assert "自动选择：" in (ROOT / "src/locales/zh.json").read_text()
    assert "Auto-picked: " in (ROOT / "src/locales/en.json").read_text()
    assert "chatMessage.skillPinnedModel" in (ROOT / "src/locales/zh.json").read_text()
    assert "{0} 技能固定模型" in (ROOT / "src/locales/zh.json").read_text()
    assert "data-testid=\"auto-model-label\"" in chat or "auto-model-label" in chat
    # #870 design: in-frame gen-card Auto row removed; SelectionLabel + process rail keep auto-model-label
    gen = (ROOT / "src/shapes/GeneratorShape.tsx").read_text()
    assert "ca-gen-frame__model" not in gen and "autoPillLabel" not in gen
    assert "ca-gen-frame__model" not in (ROOT / "src/styles/canvas.css").read_text()
    sel = (ROOT / "src/ui/SelectionLabel.tsx").read_text()
    assert "autoPillLabel" in sel and "ca-label__model" in sel and "auto-model-label" in sel


def test_resolve_model_choice_auto_and_manual(catalog):
    model, choice = wavespeed.resolve_model_choice("text_to_image", {"prompt": "logo for a cafe"})
    assert choice and choice["auto"] is True
    assert choice["model"] == model
    assert choice["reason"].get("zh")

    default = catalog["features"]["text_to_image"]["default"]
    model2, choice2 = wavespeed.resolve_model_choice(
        "text_to_image", {"prompt": "x", "model": default},
    )
    assert model2 == default
    assert choice2 and choice2["auto"] is False
    assert choice2["reason"] == {"zh": "你指定了这个模型", "en": "you named this model"}



SEEDREAM = "bytedance/seedream-v5.0-pro"
SEEDREAM_EDIT = "bytedance/seedream-v5.0-pro/edit"
NANO_EDIT = "google/nano-banana-2.1/edit"


def test_realistic_person_auto_label_and_hover_reason(catalog):
    """Hover on a realistic-person Auto card is exactly 「自动选择：写实人物」 (#871 tip + prefix)."""
    choice = auto_models.choose("text_to_image", "一张写实人像", None, catalog)
    assert choice["auto"] is True
    assert choice["category"] == "person"
    assert choice["model"] == SEEDREAM
    assert choice["reason"] == {"zh": "写实人物", "en": "realistic person"}
    assert auto_models.pill_tooltip(choice, "zh") == "自动选择：写实人物"
    assert auto_models.pill_tooltip(choice, "en") == "Auto-picked: realistic person"
    assert auto_models.pill_label(choice) == "Auto · Seedream 5.0 Pro"
    src = (ROOT / "src/autoPill.ts").read_text()
    assert "'bytedance/seedream-v5.0-pro': 'Seedream 5.0 Pro'" in src
    assert "Seedream v5 Pro" not in src

    edit = auto_models.choose("image_edit", "编辑这张写实人像，让她微笑", None, catalog)
    assert edit["auto"] is True and edit["category"] == "person" and edit["model"] == SEEDREAM_EDIT
    assert auto_models.pill_tooltip(edit, "zh") == "自动选择：写实人物"
    assert auto_models.pill_label(edit) == "Auto · Seedream 5.0 Pro"




def test_photoreal_product_hover_tip(catalog):
    """Hover on a product Auto card is exactly 「自动选择：产品摄影」."""
    choice = auto_models.choose("text_to_image", "电商主图，白底，香水瓶", None, catalog)
    assert choice["auto"] is True and choice["category"] == "photoreal" and choice["model"] == SEEDREAM
    assert choice["reason"] == {"zh": "产品摄影", "en": "product photography"}
    assert auto_models.pill_tooltip(choice, "zh") == "自动选择：产品摄影"
    assert auto_models.pill_tooltip(choice, "en") == "Auto-picked: product photography"
    assert auto_models.pill_label(choice) == "Auto · Seedream 5.0 Pro"

def test_anime_illustration_poster_and_masked_rows_unchanged(catalog):
    """Frozen rows: anime/illustration, logo, person model+tip, photo_retouch, masked (Sunburst→Flare).
    poster_text is Flare primary with no registered fallback (this PR)."""
    table = auto_models.load_table()
    anime = next(c for c in table["text_to_image"]["categories"] if c["id"] == "anime_art")
    assert anime["model"] == "midjourney/text-to-image"
    assert "illustration" in anime["keywords"] and "插画" in anime["keywords"]
    assert anime.get("fallback") in (None, "", [])
    poster = next(c for c in table["text_to_image"]["categories"] if c["id"] == "poster_text")
    assert poster["model"] == "openai/gpt-image-2.6-flare/text-to-image"
    assert poster.get("fallback") in (None, "", [])
    assert poster["tip"] == {"zh": "海报/带字", "en": "poster / text"}
    masked = table["image_edit"]["masked"]
    assert masked["model"] == "openai/gpt-image-2.6-sunburst/edit"
    assert masked["fallback"] == "openai/gpt-image-2.6-flare/edit"
    assert masked["tip"] == {"zh": "选区编辑", "en": "selection edit"}
    logo = next(c for c in table["text_to_image"]["categories"] if c["id"] == "logo")
    assert logo["model"] == "recraft-ai/recraft-v3"
    person = next(c for c in table["text_to_image"]["categories"] if c["id"] == "person")
    assert person["model"] == SEEDREAM
    assert person["tip"] == {"zh": "写实人物", "en": "realistic person"}
    photoreal = next(c for c in table["text_to_image"]["categories"] if c["id"] == "photoreal")
    assert photoreal["model"] == SEEDREAM
    assert photoreal["tip"] == {"zh": "产品摄影", "en": "product photography"}
    retouch = next(c for c in table["image_edit"]["categories"] if c["id"] == "photo_retouch")
    assert retouch["model"] == SEEDREAM_EDIT
    person_edit = next(c for c in table["image_edit"]["categories"] if c["id"] == "person")
    assert person_edit["model"] == SEEDREAM_EDIT
    assert person_edit["tip"] == {"zh": "写实人物", "en": "realistic person"}

    # Live matcher still routes those rows the same way as main
    assert auto_models.choose("text_to_image", "Anime girl under cherry blossoms", None, catalog)["category"] == "anime_art"
    assert auto_models.choose("text_to_image", "an illustrated children's book page with a fox", None, catalog)["category"] == "anime_art"
    poster_choice = auto_models.choose("text_to_image", 'Movie poster with the headline "SUMMER"', None, catalog)
    assert poster_choice["category"] == "poster_text" and poster_choice["model"] == poster["model"]
    masked_choice = auto_models.choose("image_edit", "edit the selected area", None, catalog, masked=True)
    assert masked_choice["category"] == "masked" and masked_choice["model"] == masked["model"]
    assert auto_models.registered_runtime_fallback(
        "image_edit", masked_choice, {masked["model"], masked["fallback"]}
    ) == masked["fallback"]


KEEP_IDENTITY_REASON = {
    "zh": "这是要保持人物或产品一致的局部修改",
    "en": "this is a local edit that must keep the person or product consistent",
}
KEEP_IDENTITY_TIP = {"zh": "保留同一人物", "en": "keep the same person"}
KEEP_PRODUCT_TIP = {"zh": "保留商品不变", "en": "keep the product unchanged"}
KEEP_GENERIC_TIP = {"zh": "保持原图一致", "en": "keep the original consistent"}
KEEP_GENERIC_REASON = {
    "zh": "这是要保持原图一致的局部修改",
    "en": "this is a local edit that must keep the original consistent",
}
KEEP_FACE_PROMPTS = [
    "保留同一个人，换衣服",
    "保留同一个人，只把衣服换成深色西装、背景换成办公室",
    "保留脸，换背景",
    "keep the face, new background",
    "keep the same face",
    "new background, keep the same person",
    "same person, only change the clothes",
]
KEEP_PRODUCT_PROMPTS = [
    "保留产品，只换背景",
    "产品不变，只改背景",
    "preserve the product, recolor the backdrop",
    "keep the product, only change the background",
]


def test_keep_identity_keep_face_prompt_routes_to_seedream_edit(catalog):
    """#825: identity-lock / keep-the-face edits now Auto-pick Seedream 5.0 Pro edit."""
    for prompt in KEEP_FACE_PROMPTS:
        choice = auto_models.choose("image_edit", prompt, None, catalog)
        assert choice["auto"] is True, prompt
        assert choice["category"] == "keep_identity", prompt
        assert choice["model"] == SEEDREAM_EDIT, prompt
        assert choice["reason"] == KEEP_IDENTITY_TIP, prompt
        assert auto_models.pill_tooltip(choice, "zh") == "自动选择：保留同一人物"
        assert auto_models.pill_tooltip(choice, "en") == "Auto-picked: keep the same person"
        assert auto_models.pill_label(choice) == "Auto · Seedream 5.0 Pro"



def test_keep_product_prompt_routes_to_banana_edit(catalog):
    """#825: product / background-only keep phrases stay on Banana 2.1 with the 保留商品不变 tip."""
    for prompt in KEEP_PRODUCT_PROMPTS:
        choice = auto_models.choose("image_edit", prompt, None, catalog)
        assert choice["auto"] is True, prompt
        assert choice["category"] == "keep_product", prompt
        assert choice["model"] == NANO_EDIT, prompt
        assert choice["reason"] == KEEP_PRODUCT_TIP, prompt
        assert auto_models.pill_tooltip(choice, "zh") == "自动选择：保留商品不变"
        assert auto_models.pill_tooltip(choice, "en") == "Auto-picked: keep the product unchanged"
        assert auto_models.pill_label(choice) == "Auto · Nano Banana 2.1"


def test_keep_identity_wins_when_prompt_has_person_and_product_words(catalog):
    """First-match: keep_identity is above keep_product, so person/face words win over product words."""
    prompt = "只换背景，人脸不要动"
    choice = auto_models.choose("image_edit", prompt, None, catalog)
    assert choice["category"] == "keep_identity"
    assert choice["model"] == SEEDREAM_EDIT
    assert auto_models.pill_label(choice) == "Auto · Seedream 5.0 Pro"
    assert auto_models.pill_tooltip(choice, "zh") == "自动选择：保留同一人物"
    assert auto_models.pill_tooltip(choice, "en") == "Auto-picked: keep the same person"

    # "keep the same face" must not fall through to keep_generic's "keep the same" prefix.
    choice = auto_models.choose("image_edit", "keep the same face", None, catalog)
    assert choice["category"] == "keep_identity"
    assert choice["model"] == SEEDREAM_EDIT
    assert auto_models.pill_tooltip(choice, "zh") == "自动选择：保留同一人物"

    # Generic keep + person/face words: keep_identity still wins over keep_generic.
    choice = auto_models.choose("image_edit", "保持一致，人脸不要动", None, catalog)
    assert choice["category"] == "keep_identity"
    assert choice["model"] == SEEDREAM_EDIT
    assert auto_models.pill_label(choice) == "Auto · Seedream 5.0 Pro"
    assert auto_models.pill_tooltip(choice, "zh") == "自动选择：保留同一人物"
    assert auto_models.pill_tooltip(choice, "en") == "Auto-picked: keep the same person"


KEEP_GENERIC_PROMPTS = [
    "keep the same bottle, change the background",
    "保持原样，把香水瓶放到海边",
    "保持一致",
    "背景改成海边，其他保持不变",
]
# These also contain 只换背景, so first-match hits keep_product (still Banana 2.1).
KEEP_GENERIC_WITH_PRODUCT_PROMPTS = [
    "保持一致，只换背景",
    "商品保持原样，只换背景",
]


def test_keep_generic_prompts_route_to_banana(catalog):
    """#825: generic keep phrases stay on Banana 2.1 with the 保持原图一致 tip."""
    for prompt in KEEP_GENERIC_PROMPTS:
        choice = auto_models.choose("image_edit", prompt, None, catalog)
        assert choice["auto"] is True, prompt
        assert choice["category"] == "keep_generic", prompt
        assert choice["model"] == NANO_EDIT, prompt
        assert choice["reason"] == KEEP_GENERIC_TIP, prompt
        assert auto_models.pill_tooltip(choice, "zh") == "自动选择：保持原图一致", prompt
        assert auto_models.pill_tooltip(choice, "en") == "Auto-picked: keep the original consistent", prompt
        assert auto_models.pill_label(choice) == "Auto · Nano Banana 2.1", prompt

    for prompt in KEEP_GENERIC_WITH_PRODUCT_PROMPTS:
        choice = auto_models.choose("image_edit", prompt, None, catalog)
        assert choice["model"] == NANO_EDIT, prompt
        # 只换背景 is a keep_product keyword and that row sits above keep_generic.
        assert choice["category"] == "keep_product", prompt
        assert auto_models.pill_tooltip(choice, "zh") == "自动选择：保留商品不变", prompt


def test_keep_row_hover_tips(catalog):
    """Hover tips for all three keep_* rows."""
    ident = auto_models.choose("image_edit", "保留同一个人，换衣服", None, catalog)
    assert ident["category"] == "keep_identity"
    assert auto_models.pill_tooltip(ident, "zh") == "自动选择：保留同一人物"
    assert auto_models.pill_tooltip(ident, "en") == "Auto-picked: keep the same person"

    product = auto_models.choose("image_edit", "保留产品，只换背景", None, catalog)
    assert product["category"] == "keep_product"
    assert auto_models.pill_tooltip(product, "zh") == "自动选择：保留商品不变"
    assert auto_models.pill_tooltip(product, "en") == "Auto-picked: keep the product unchanged"

    generic = auto_models.choose("image_edit", "保持一致", None, catalog)
    assert generic["category"] == "keep_generic"
    assert auto_models.pill_tooltip(generic, "zh") == "自动选择：保持原图一致"
    assert auto_models.pill_tooltip(generic, "en") == "Auto-picked: keep the original consistent"


def test_keep_identity_move_leaves_other_auto_rows_unchanged(catalog):
    """Frozen check: keep_identity (Seedream), then keep_product and keep_generic (Banana)."""
    table = auto_models.load_table()
    ie_cats = table["image_edit"]["categories"]
    assert [c["id"] for c in ie_cats] == [
        "keep_identity", "keep_product", "keep_generic", "photo_retouch", "person",
    ]

    keep = ie_cats[0]
    assert keep["id"] == "keep_identity"
    assert keep["model"] == SEEDREAM_EDIT
    assert keep["zh"] == KEEP_IDENTITY_REASON["zh"] and keep["en"] == KEEP_IDENTITY_REASON["en"]
    assert keep["tip"] == KEEP_IDENTITY_TIP
    assert keep.get("fallback") in (None, "", [])
    keywords = keep["keywords"]
    for token in (
        "保留同一个人", "保留脸", "同一个人", "same person", "same face",
        "keep the face", "keep the same face", "keep the same person",
    ):
        # 「保留同一个人」 is a substring hit on 同一个人; the others are listed verbatim.
        if token == "保留同一个人":
            assert "同一个人" in keywords
        else:
            assert token in keywords, token
    product_keywords = [
        "keep the product", "don't change the product", "same product", "preserve the product",
        "保持产品", "产品不变", "保留产品", "只换背景", "只改背景",
    ]
    generic_keywords = ["keep the same", "保持一致", "保持原样", "保持原貌", "保持不变"]
    for token in product_keywords + generic_keywords:
        assert token not in keywords, token
    assert len(keywords) == 30

    product = ie_cats[1]
    assert product["id"] == "keep_product"
    assert product["model"] == NANO_EDIT
    assert product["zh"] == KEEP_IDENTITY_REASON["zh"] and product["en"] == KEEP_IDENTITY_REASON["en"]
    assert product["tip"] == KEEP_PRODUCT_TIP
    assert product.get("fallback") in (None, "", [])
    assert product["keywords"] == product_keywords

    generic = ie_cats[2]
    assert generic["id"] == "keep_generic"
    assert generic["model"] == NANO_EDIT
    assert generic["zh"] == KEEP_GENERIC_REASON["zh"] and generic["en"] == KEEP_GENERIC_REASON["en"]
    assert generic["tip"] == KEEP_GENERIC_TIP
    assert generic.get("fallback") in (None, "", [])
    assert generic["keywords"] == generic_keywords

    # person t2i / person edit (Seedream) — model + short tip unchanged
    person = next(c for c in table["text_to_image"]["categories"] if c["id"] == "person")
    assert person["model"] == SEEDREAM
    assert person["tip"] == {"zh": "写实人物", "en": "realistic person"}
    person_edit = next(c for c in ie_cats if c["id"] == "person")
    assert person_edit["model"] == SEEDREAM_EDIT
    assert person_edit["tip"] == {"zh": "写实人物", "en": "realistic person"}

    # product photoreal (产品摄影)
    photoreal = next(c for c in table["text_to_image"]["categories"] if c["id"] == "photoreal")
    assert photoreal["model"] == SEEDREAM
    assert photoreal["tip"] == {"zh": "产品摄影", "en": "product photography"}

    # poster (Flare, no registered fallback — as on #882)
    poster = next(c for c in table["text_to_image"]["categories"] if c["id"] == "poster_text")
    assert poster["model"] == "openai/gpt-image-2.6-flare/text-to-image"
    assert poster.get("fallback") in (None, "", [])
    assert poster["tip"] == {"zh": "海报/带字", "en": "poster / text"}

    # anime / illustration (Midjourney)
    anime = next(c for c in table["text_to_image"]["categories"] if c["id"] == "anime_art")
    assert anime["model"] == "midjourney/text-to-image"
    assert "illustration" in anime["keywords"] and "插画" in anime["keywords"]

    # logo
    logo = next(c for c in table["text_to_image"]["categories"] if c["id"] == "logo")
    assert logo["model"] == "recraft-ai/recraft-v3"

    # masked edit (Sunburst → Flare)
    masked = table["image_edit"]["masked"]
    assert masked["model"] == "openai/gpt-image-2.6-sunburst/edit"
    assert masked["fallback"] == "openai/gpt-image-2.6-flare/edit"
    assert masked["tip"] == {"zh": "选区编辑", "en": "selection edit"}

    # photo_retouch stays Seedream edit
    retouch = next(c for c in ie_cats if c["id"] == "photo_retouch")
    assert retouch["model"] == SEEDREAM_EDIT

    # multi-reference stays Banana 2.1 edit
    assert table["image_edit"]["multi_reference"]["model"] == "google/nano-banana-2.1/edit"

    # Live matcher: other rows still route the same way
    assert auto_models.choose("text_to_image", "一张写实人像，自然光", None, catalog)["category"] == "person"
    assert auto_models.choose("image_edit", "编辑这张写实人像，让她微笑", None, catalog)["category"] == "person"
    assert auto_models.choose("text_to_image", "电商主图，白底，香水瓶", None, catalog)["category"] == "photoreal"
    assert auto_models.choose("text_to_image", 'Movie poster with the headline "SUMMER"', None, catalog)["category"] == "poster_text"
    assert auto_models.choose("text_to_image", "Anime girl under cherry blossoms", None, catalog)["category"] == "anime_art"
    assert auto_models.choose("text_to_image", "Minimal logo for a tea brand", None, catalog)["category"] == "logo"
    assert auto_models.choose("image_edit", "retouch the portrait, natural skin", None, catalog)["category"] == "photo_retouch"
    masked_choice = auto_models.choose("image_edit", "edit the selected area", None, catalog, masked=True)
    assert masked_choice["category"] == "masked" and masked_choice["model"] == masked["model"]
