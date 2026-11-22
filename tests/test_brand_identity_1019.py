"""#1019 default path: locked cards, eight exact sizes, refs, opaque flatten, per-stage quote.

Industry templates stay on the #979 3+1 contract. No WaveSpeed call.
"""
from __future__ import annotations

import io

from PIL import Image

from ComfyArt.api import brand_identity as brand
from ComfyArt.api.bot_asks import validate_spec
from ComfyArt.bot.plan_quote import build_quote
from ComfyArt.bot.skill_output import apply_generate, plan_for


def setup_function():
    brand.reset_for_tests()


def _card1():
    return validate_spec({"questions": [
        {"id": "bi_delivery", "prompt": "这次「基础品牌视觉系统」要交付哪些物料？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}]},
        {"id": "bi_color", "prompt": "色彩方向选哪一种？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}]},
        {"id": "bi_mark", "prompt": "Logo 的构成方向偏好？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}]},
        {"id": "bi_source", "prompt": "门店与产品素材怎么处理？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}]},
    ], "page_count": 4})


def test_card1_is_one_card_four_pages_and_not_preselected():
    spec = _card1()
    assert spec["page_count"] == 4
    assert [q["page"] for q in spec["questions"]] == [1, 2, 3, 4]
    assert spec["allow_skip"] is True
    delivery = spec["questions"][0]
    assert delivery["max_selections"] == 4 and delivery["allow_other"] is True
    assert "核心套装" in delivery["options"][0]["label"]
    assert all("recommended" not in opt for q in spec["questions"] for opt in q["options"])
    assert "defaults" not in spec
    for q in spec["questions"]:
        assert "defaults" not in q


def test_generate_before_card1_is_not_submitted():
    args = apply_generate({"skill": brand.SKILL, "prompt": "栖木咖啡"}, brand.SKILL)
    assert args["_brand_block"]["submitted"] is False
    assert "1024" not in str(args.get("width"))


def test_default_path_sizes_do_not_squash_to_1024():
    brand.record_card_answer(_card1(), {"bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
                                         "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]}})
    mood = apply_generate({"skill": brand.SKILL, "prompt": "moodboard", "width": 2048, "height": 2048}, brand.SKILL)
    assert (mood["width"], mood["height"], mood["ratio"], mood["brand_slot"]) == (2048, 1152, "16:9", "moodboard")
    assert mood["width"] != 1024
    brand.record_submitted(mood, {"ids": ["holder-mood"]})
    brand.record_wait({"results": [{"id": "holder-mood", "shapes": ["shape:mood"], "urls": ["/view?f=mood.png"]}]})
    brand.record_card_answer(validate_spec({
        "questions": [{"id": "bi_moodboard", "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
                       "options": [{"id": "A", "label": "就这版，通过"}, {"id": "B", "label": "重出"}]}],
    }), {"bi_moodboard": {"selected": ["A"]}})
    logos = [apply_generate({"skill": brand.SKILL, "prompt": f"logo {i}"}, brand.SKILL) for i in range(3)]
    assert [(a["brand_slot"], a["width"], a["height"]) for a in logos] == [
        ("logo_a", 2048, 2048), ("logo_b", 2048, 2048), ("logo_c", 2048, 2048)]
    assert all(a["refs"] == ["shape:mood"] for a in logos)
    for i, slot in enumerate(("logo_a", "logo_b", "logo_c")):
        brand.record_submitted(logos[i], {"ids": [f"holder-{slot}"]})
        brand.record_wait({"results": [{"id": f"holder-{slot}", "shapes": [f"shape:{slot}"], "urls": [f"/view?f={slot}.png"]}]})
    card3 = validate_spec({"questions": [{
        "id": "bi_direction",
        "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
        "options": [{"id": "A", "label": "方向 A", "recommended": True},
                    {"id": "B", "label": "方向 B"}, {"id": "C", "label": "方向 C"}],
    }]})
    flagged = [opt for opt in card3["questions"][0]["options"] if opt.get("recommended")]
    assert len(flagged) == 1 and flagged[0]["id"] == "A"
    assert "defaults" not in card3["questions"][0]
    assert [opt.get("image_url") for opt in card3["questions"][0]["options"]] == [
        "/view?f=logo_a.png", "/view?f=logo_b.png", "/view?f=logo_c.png"]
    brand.record_card_answer(card3, {"bi_direction": {"selected": ["A"]}})
    finals = [apply_generate({"skill": brand.SKILL, "prompt": name}, brand.SKILL)
              for name in ("spec", "cup", "bag", "store")]
    assert [(a["brand_slot"], a["width"], a["height"]) for a in finals] == [
        ("spec", 1536, 2048), ("cup", 1536, 2048), ("bag", 1536, 2048), ("storefront", 2048, 1152)]
    assert all(a["refs"] == ["shape:logo_a", "shape:mood"] for a in finals)
    assert all(a["size_lock"] is True and a["brand_opaque"] is True for a in finals)


def test_industry_template_is_unchanged():
    stage1 = plan_for(brand.SKILL, "geometric", 1)
    stage2 = plan_for(brand.SKILL, "geometric", 2)
    assert (stage1["width"], stage1["height"], stage1["images"]) == (1024, 1024, 3)
    assert (stage2["width"], stage2["height"], stage2["images"]) == (2048, 1152, 1)
    assert stage1["total_images"] == 4
    args = apply_generate({"skill": brand.SKILL, "preset": "handmade", "prompt": "方向"}, brand.SKILL)
    assert (args["width"], args["height"], args["preset"], args["stage"]) == (1024, 1024, "handmade", 1)
    assert "brand_slot" not in args


def test_rows_center_the_logos_between_moodboard_and_deliverables():
    mood = brand.slot_origin("moodboard")
    a, b, c = (brand.slot_origin(s) for s in ("logo_a", "logo_b", "logo_c"))
    spec, cup, bag, store = (brand.slot_origin(s) for s in ("spec", "cup", "bag", "storefront"))
    assert mood[1] < a[1] < spec[1]
    assert a[0] < b[0] < c[0]
    assert spec[0] < cup[0] < bag[0] < store[0]
    # Middle row is centered in the wider deliverable row, not left-aligned to x=0
    # unless the rows happen to match. Deliverables are wider than three squares? 
    # 3*1536+2048+3*40 = 6776; 3*2048+2*40 = 6224, so logos start inset.
    assert a[0] > spec[0]
    assert a[1] == b[1] == c[1]
    assert spec[1] == store[1]


def test_flatten_puts_alpha_on_white_and_leaves_opaque_bytes():
    opaque = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(opaque, format="PNG")
    raw = opaque.getvalue()
    assert brand.flatten_opaque(raw) == raw
    transparent = io.BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 0)).save(transparent, format="PNG")
    flat = brand.flatten_opaque(transparent.getvalue())
    with Image.open(io.BytesIO(flat)) as img:
        assert img.mode == "RGB"
        assert img.getpixel((0, 0)) == (255, 255, 255)


def test_closing_rules_are_in_the_skill_instructions():
    from pathlib import Path
    text = Path("src/skills.ts").read_text(encoding="utf-8")
    assert "矢量替换" in text and "色值为屏幕估算" in text
    assert "可直接投产" in text and "Never say" in text


def test_stage_quote_is_separate_and_names_the_cumulative():
    import asyncio
    brand.record_card_answer(_card1(), {"bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
                                         "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]}})
    mood = apply_generate({"skill": brand.SKILL, "prompt": "board"}, brand.SKILL)

    async def pricer(model, inputs):
        return 0.03, "quote", ""

    async def models_for(feature):
        return []

    steps = [{"text": "moodboard", "tool": "generate_image", "model": brand.QWEN_T2I, "arguments": mood}]
    quote = asyncio.run(build_quote(steps, "zh", threshold=0.5, pricer=pricer, models_for=models_for))
    assert quote is not None and quote.ask is True
    assert quote.n == 1
    assert "累计" in quote.prompt and "本阶段" in quote.prompt
    # One image at $0.03 is under the $0.50 gate and still shows a card.
    assert quote.total == 0.03
