"""#1019 default path: locked cards, eight exact sizes, refs, opaque flatten, per-stage quote.

Industry templates stay on the #979 3+1 contract. No WaveSpeed call.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from ComfyArt.api import brand_identity as brand
from ComfyArt.api.bot_asks import validate_spec
from ComfyArt.bot.plan_quote import build_quote
from ComfyArt.bot.skill_output import apply_generate, plan_for


def setup_function():
    brand.reset_for_tests()


def teardown_function():
    brand.reset_for_tests()


def _card1():
    return validate_spec({"questions": [
        {"id": "bi_delivery", "prompt": "这次「基础品牌视觉系统」要交付哪些物料？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}]},
        {"id": "bi_color", "prompt": "色彩方向选哪一种？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}]},
        {"id": "bi_mark", "prompt": "Logo 的构成方向偏好？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}]},
        {"id": "bi_source", "prompt": "门店与产品素材怎么处理？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}]},
    ], "page_count": 4})


def test_cards_1_and_2_keep_locked_labels_when_the_model_count_matches():
    """A live card kept 「暖木棕 + 米白」 because three options matched. The lock wins."""
    card = validate_spec({"questions": [
        {"id": "bi_delivery", "prompt": "这次「基础品牌视觉系统」要交付哪些物料？",
         "options": [{"id": "A", "label": "随便一套"}, {"id": "B", "label": "菜单"},
                     {"id": "C", "label": "社媒"}, {"id": "D", "label": "名片"}]},
        {"id": "bi_color", "prompt": "色彩方向选哪一种？",
         "options": [{"id": "A", "label": "暖木棕 + 米白"}, {"id": "B", "label": "只要棕色"},
                     {"id": "C", "label": "绿色"}]},
        {"id": "bi_mark", "prompt": "Logo 的构成方向偏好？",
         "options": [{"id": "A", "label": "甲"}, {"id": "B", "label": "乙"}, {"id": "C", "label": "丙"}]},
        {"id": "bi_source", "prompt": "门店与产品素材怎么处理？",
         "options": [{"id": "A", "label": "没有照片"}, {"id": "B", "label": "我来传"},
                     {"id": "C", "label": "只要平面"}]},
    ], "page_count": 4})
    color = card["questions"][1]["options"]
    assert [opt["label"] for opt in color] == [
        "暖土色为主 + 低饱和靛蓝点缀",
        "纯暖土色系：陶土橘 / 焦糖 / 米白 / 深焙棕",
        "鼠尾草绿 + 原木 + 米白，自然感更强",
    ]
    blob = __import__("json").dumps(card, ensure_ascii=False)
    assert "暖木棕 + 米白" not in blob
    assert "随便一套" not in blob
    mood = validate_spec({"questions": [{
        "id": "bi_moodboard",
        "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
        "options": [{"id": "A", "label": "可以"}, {"id": "B", "label": "再来一张"},
                    {"id": "C", "label": "我自己改"}],
    }]})
    assert [opt["label"] for opt in mood["questions"][0]["options"]] == [
        "就这版，通过", "重出情绪板，加强靛蓝点缀", "告诉我要改哪几格",
    ]
    en = brand.normalize_card({"questions": [{
        "id": "bi_color",
        "prompt": "Which color direction?",
        "options": [{"id": "A", "label": "Warm wood and white"},
                    {"id": "B", "label": "Brown only"}, {"id": "C", "label": "Green"}],
    }]}, "en")
    assert en["questions"][1]["options"][0]["label"] == (
        "Warm earth as the base, with a low-saturation indigo accent"
    )
    assert "Warm wood and white" not in __import__("json").dumps(en)


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


def test_each_slot_prompt_locks_a_different_structure():
    mood = brand.fill_default({"brand_slot": "moodboard", "prompt": "栖木咖啡"})
    assert "3 equal columns and 3 equal rows" in mood["prompt"]
    labels = ["质感", "色彩", "符号", "字标", "版式", "材料", "外带杯", "门头", "数字"]
    positions = [mood["prompt"].index(label) for label in labels]
    assert positions == sorted(positions)
    assert "exactly one Chinese label" in mood["prompt"]
    assert "image that matches that label" in mood["prompt"]
    assert "No empty cell" in mood["prompt"]
    assert "separator" in mood["prompt"] and "｜" in mood["prompt"]
    assert "full-bleed" in mood["prompt"] and "edge to edge" in mood["prompt"]
    assert "bottom-left" in mood["prompt"]
    for wrong in ("色调", "字体", "材质"):
        assert wrong not in mood["prompt"]
    hint = brand.default_hint()
    hint_at = [hint.index(label) for label in labels]
    assert hint_at == sorted(hint_at)
    assert "exactly one Chinese label" in hint
    assert "matching that label" in hint
    assert "No empty cell" in hint
    assert "separator" in hint
    assert "full-bleed" in hint and "edge to edge" in hint
    assert "bottom-left" in hint
    assert "色调" not in hint
    a = brand.fill_default({"brand_slot": "logo_a", "prompt": "方向A"})
    b = brand.fill_default({"brand_slot": "logo_b", "prompt": "方向B"})
    c = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C"})
    assert "one open single-line drawing" in a["prompt"] and "single-line" in a["prompt"]
    assert "solid filled wood plaque and a circular seal" in b["prompt"] and "circular seal" in b["prompt"]
    assert "cup-shaped" in c["prompt"]
    assert "single-line" not in b["prompt"]
    assert "perched bird is the negative space inside the cup" in c["prompt"]
    assert "accent color or the dark color from the confirmed color direction" in c["prompt"]
    assert "reversed out inside it as negative space" in c["prompt"]
    assert "indigo" not in c["prompt"].lower() and "靛蓝" not in c["prompt"]
    assert "indigo" not in brand._SLOT_LOCK["logo_c"].lower() and "靛蓝" not in brand._SLOT_LOCK["logo_c"]
    assert "indigo" not in hint.lower() and "靛蓝" not in hint
    assert "handled cup" in c["prompt"] and "positive shape" in c["prompt"]
    assert "bird standing on a branch" in c["prompt"]
    assert "The wordmark appears exactly once per zone." in c["prompt"]
    for board in (a, b, c):
        assert "主组合, 符号构造, 横版, 小尺寸" in board["prompt"]
        assert "exactly once" in board["prompt"]
        assert "No other small text." in board["prompt"]
        assert "No bottom caption." in board["prompt"]
        assert "Do not print an English instruction label." in board["prompt"]
        assert "STRUCTURE LOCK" not in board["prompt"]
        assert "Each of the four zone labels appears exactly once." in board["prompt"]
        assert "No empty placeholder box" in board["prompt"] and "no X box" in board["prompt"]
        assert "小尺寸 includes the symbol" in board["prompt"]
    spec = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})
    headings = [
        "标识 / LOGO", "色彩 / COLOR", "变体 / VARIANTS", "字体 / TYPE",
        "版式 / LAYOUT", "使用禁忌 / MISUSE", "影像与材质 / IMAGE",
    ]
    assert "exactly 7 panels" in spec["prompt"]
    assert spec["prompt"].count("exactly 7 panels") == 1
    positions = [spec["prompt"].index(heading) for heading in headings]
    assert positions == sorted(positions)
    for heading in headings:
        assert heading in spec["prompt"], heading
    for old in OLD_SPEC_HEADINGS:
        assert old not in spec["prompt"], old
    assert "最小使用尺寸" in spec["prompt"]
    assert "not a separate panel" in spec["prompt"]
    assert "最小尺寸" not in spec["prompt"].replace("最小使用尺寸", "")
    assert "No heading is repeated" in spec["prompt"]
    assert "one filled layout diagram" in spec["prompt"]
    assert "full bilingual heading" in spec["prompt"] and "not clipped to 字" in spec["prompt"]
    assert "hierarchy and annotation density follow the gold" in spec["prompt"]
    assert "wordmark at three sizes" not in spec["prompt"]
    assert "no small text at all" not in spec["prompt"]
    assert "short captions of the same kind as the gold" in spec["prompt"]
    assert "one garbled character is not acceptable" in spec["prompt"]
    assert "moodboard 色彩 cell" in spec["prompt"]
    assert "each swatch has a Chinese color name, a role, and a percentage" in spec["prompt"]
    assert "any accent is at most about 5%" in spec["prompt"]
    assert "do not hardcode a palette" in spec["prompt"]
    assert "栖木咖啡" not in spec["prompt"]
    assert "no color-name label" not in spec["prompt"]
    assert "no percentage text" not in spec["prompt"]
    assert "ratios are shown only by the width" not in spec["prompt"]
    assert "Allowed on-card text includes the bilingual headings" in spec["prompt"]
    assert "a Chinese color name plus a role plus a percentage" in spec["prompt"]
    assert "short captions on 使用禁忌 / MISUSE and 影像与材质 / IMAGE" in spec["prompt"]
    assert "real Chinese brand name" in spec["prompt"] and "real English brand name" in spec["prompt"]
    assert "character for character" in spec["prompt"]
    assert "Do not drop a character" in spec["prompt"]
    assert "red X" in spec["prompt"]
    assert "Do not write invented body copy" in spec["prompt"]
    assert "Do not invent English" in spec["prompt"]
    for banned in ("The only words", "No explanatory caption", "no English subtitle", "不要说明文字", "只能出现这些字", "no sample English", "no invented words"):
        assert banned not in spec["prompt"], banned
    assert "uses only the brand colors" in spec["prompt"]
    assert "title, subtitle" not in spec["prompt"]
    assert "#" not in spec["prompt"]
    assert "moodboard 色彩 cell" in hint
    assert "Do not state hex values" in hint and "exact values are on the spec card" in hint
    assert "#" not in hint
    store = brand.fill_default({"brand_slot": "storefront", "prompt": "门头"})
    assert "full shopfront, front view" in store["prompt"]
    assert "A-frame standing sign" in store["prompt"]
    assert "Not a hanging-sign close-up" in store["prompt"]
    cup = brand.fill_default({"brand_slot": "cup", "prompt": "杯"})
    assert "使用禁忌" in spec["prompt"] and "影像与材质" in spec["prompt"]
    assert "Chinese brand name and the English brand name" in cup["prompt"]
    assert "must wear a cup sleeve" in cup["prompt"] and "杯套" in cup["prompt"]
    assert "A bare cup with no sleeve is wrong." in cup["prompt"]
    again = brand.fill_default({"brand_slot": "logo_a", "prompt": a["prompt"]})
    assert again["prompt"].count("one open single-line drawing of a bird perched on a branch") == 1
    leaked = brand.fill_default({
        "brand_slot": "logo_c",
        "prompt": "bottom caption STRUCTURE LOCK C: keep the cup",
    })
    assert "STRUCTURE LOCK" not in leaked["prompt"]
    assert "keep the cup" in leaked["prompt"]
    assert leaked["prompt"].count("cup-shaped") == 1
    leaked_spec = brand.fill_default({"brand_slot": "spec", "prompt": "规范 GUIDELINE LOCK"})
    assert "GUIDELINE LOCK" not in leaked_spec["prompt"]
    assert "Do not print an English instruction label." in leaked_spec["prompt"]


def test_a_second_confirm_of_the_same_stage_does_not_double_the_total():
    brand.reset_for_tests()
    steps = [{"tool": "generate_image", "arguments": {"brand_slot": "logo_a"}}]
    brand.note_confirmed(0.2, 3, stage=brand.quoted_stage(steps))
    brand.note_confirmed(0.2, 3, stage=2)
    assert brand._progress()["spent"] == 0.2
    assert brand.spend_before(2) == 0.0


def _logo_plan(slot: str, **over):
    args = {
        "skill": brand.SKILL,
        "brand_slot": slot,
        "width": 2048,
        "height": 2048,
        "count": 1,
        "edit_model": brand.QWEN_EDIT,
        "prompt": slot,
    }
    args.update(over)
    return {
        "tool": "generate_image",
        "model": str(args.get("edit_model") or args.get("model") or ""),
        "arguments": args,
    }


def _three_logos():
    return [_logo_plan(slot) for slot in ("logo_a", "logo_b", "logo_c")]


def test_stage_repeat_continues_once_then_blocks_and_a_changed_plan_is_new():
    """Fingerprint is tool, model, size, count, and slot. Prompt wording is not part of it."""
    steps = _three_logos()
    assert brand.stage_repeat(steps) == "new"
    brand.note_confirmed(0.09, 3, stage=2)
    brand.remember_stage_plan(steps, fresh=True)
    assert brand.stage_repeat(steps) == "continue"
    reworded = [_logo_plan(slot, prompt="entirely different prompt") for slot in ("logo_a", "logo_b", "logo_c")]
    assert brand.stage_fingerprint(reworded) == brand.stage_fingerprint(steps)
    assert brand.stage_repeat(reworded) == "continue"
    # A repeat confirm replaces the amount and keeps the unsubmitted plan.
    brand.note_confirmed(0.09, 3, stage=2)
    assert brand._progress()["spent"] == 0.09
    assert brand.spend_before(2) == 0.0
    assert brand.stage_repeat(steps) == "continue"
    brand.note_brand_submitted(_logo_plan("logo_a")["arguments"])
    brand.mark_stage_dispatched(steps)
    assert brand.submitted_slots(2) == {"logo_a"}
    assert brand.stage_repeat(steps) == "continue"
    brand.note_brand_submitted(_logo_plan("logo_b")["arguments"])
    brand.note_brand_submitted(_logo_plan("logo_c")["arguments"])
    brand.mark_stage_dispatched(steps)
    assert brand.stage_repeat(steps) == "done"
    assert brand.stage_repeat([_logo_plan(slot, width=1024) for slot in ("logo_a", "logo_b", "logo_c")]) == "new"
    assert brand.stage_repeat([_logo_plan(slot, edit_model="other-model") for slot in ("logo_a", "logo_b", "logo_c")]) == "new"
    assert brand.stage_repeat([_logo_plan(slot, count=2) for slot in ("logo_a", "logo_b", "logo_c")]) == "new"
    assert brand.stage_repeat(_three_logos() + [_logo_plan("logo_a")]) == "new"
    assert "下一阶段" in brand.stage_done_text("zh")
    assert "next stage" in brand.stage_done_text("en")


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
    assert mood[1] == 0
    assert a[1] == 1152 + brand.GAP
    assert spec[1] == a[1] + 2048 + brand.GAP
    assert b[0] - a[0] == 2048 + brand.GAP


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


SPEC_HEADINGS = (
    "标识 / LOGO", "色彩 / COLOR", "变体 / VARIANTS", "字体 / TYPE",
    "版式 / LAYOUT", "使用禁忌 / MISUSE", "影像与材质 / IMAGE",
)
OLD_SPEC_HEADINGS = ("色彩比例", "字体层级", "影像材质", "中英各三档")
_LOCK_DIRECTIVE = __import__("re").compile(r"\b(?:[A-Z]{2,} +)+LOCK\b")


def _brand_prompt_sources() -> list[tuple[str, str]]:
    import json
    from pathlib import Path

    from ComfyArt.bot.skill_output import run_hint

    root = Path("src")
    skills = (root / "skills.ts").read_text(encoding="utf-8")
    start = skills.index("id: 'brand-identity-director'")
    skill = skills[start:skills.index("id: 'packaging-design-director'", start)]
    copy = json.loads((root / "data/copy-748.json").read_text(encoding="utf-8"))["brand-identity-director"]
    texts = [("skill", skill), ("copy-748", json.dumps(copy, ensure_ascii=False))]
    texts.append(("default-hint", brand.default_hint()))
    for pid in ("geometric", "handmade", "tech", "beauty", "foodbev", "pet"):
        texts.append((f"hint:{pid}", run_hint(brand.SKILL, "", preset_id=pid)))
    for slot in ("moodboard", "logo_a", "logo_b", "logo_c", "spec", "cup", "bag", "storefront"):
        filled = brand.fill_default({"brand_slot": slot, "prompt": "栖木"})
        texts.append((slot, filled["prompt"]))
    return texts


def test_spec_card_is_seven_lovart_panels_and_brand_prompts_have_no_lock_words():
    spec = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})["prompt"]
    assert "exactly 7 panels" in spec
    assert [spec.index(heading) for heading in SPEC_HEADINGS] == sorted(spec.index(heading) for heading in SPEC_HEADINGS)
    for old in OLD_SPEC_HEADINGS:
        assert old not in spec, old
    assert "最小使用尺寸" in spec and "最小尺寸" not in spec.replace("最小使用尺寸", "")
    assert "full bilingual heading" in spec and "not clipped to 字" in spec
    assert "wordmark at three sizes" not in spec
    assert "no small text at all" not in spec
    assert "short captions of the same kind as the gold" in spec
    assert "Allowed on-card text includes the bilingual headings" in spec
    for banned in ("The only words", "No explanatory caption", "no English subtitle", "不要说明文字", "只能出现这些字"):
        assert banned not in spec, banned
    assert "one garbled character is not acceptable" in spec
    assert "Do not print an English instruction label." in spec
    assert "Paper ground, not black." in spec
    # The locked brief still ends on this sentence. The visual-assembly line follows it.
    assert brand._spec_lock().rstrip().endswith("Paper ground, not black.")
    assert spec.rstrip().endswith(brand._spec_assembly_line())
    brief_at = spec.index("Paper ground, not black.")
    assert spec[brief_at:].lstrip().startswith("Paper ground, not black.")
    logo_c = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C STRUCTURE LOCK C"})["prompt"]
    assert "STRUCTURE LOCK" not in logo_c
    assert "主组合, 符号构造, 横版, 小尺寸" in logo_c
    assert "perched bird is the negative space inside the cup" in logo_c
    assert "The wordmark appears exactly once per zone." in logo_c
    for name, text in _brand_prompt_sources():
        assert _LOCK_DIRECTIVE.search(text) is None, name
        assert "lockup" not in text.lower(), name
        assert "STRUCTURE LOCK" not in text and "GUIDELINE LOCK" not in text
        assert "LAYOUT LOCK" not in text and "APPLICATION LOCK" not in text
        if not name.startswith("hint:"):
            assert "Output lock:" not in text, name
    from ComfyArt.bot.skill_output import apply_generate
    caller = (
        "栖木咖啡\nOutput lock: leaked header\nSTRUCTURE LOCK C: keep the cup\n"
        "GUIDELINE LOCK\nLAYOUT LOCK\nAPPLICATION LOCK"
    )
    for slot in ("logo_a", "logo_b", "logo_c", "spec"):
        assembled = apply_generate(
            {"skill": brand.SKILL, "brand_slot": slot, "prompt": brand.default_hint() + "\n" + caller},
            current_skill=brand.SKILL,
        )["prompt"]
        assert "Output lock:" not in assembled, slot
        assert "STRUCTURE LOCK" not in assembled, slot
        assert "GUIDELINE LOCK" not in assembled, slot
        assert "LAYOUT LOCK" not in assembled, slot
        assert "APPLICATION LOCK" not in assembled, slot
        assert "Do not print an English instruction label." in assembled, slot
        assert "keep the cup" in assembled, slot
        assert "no industry template was selected" in assembled, slot
        if slot == "spec":
            for heading in SPEC_HEADINGS:
                assert heading in assembled, heading
            for old in OLD_SPEC_HEADINGS:
                assert old not in assembled, old
            assert "each swatch has a Chinese color name, a role, and a percentage" in assembled
            assert "any accent is at most about 5%" in assembled
            assert "Allowed on-card text includes the bilingual headings" in assembled
            assert "short captions on 使用禁忌 / MISUSE and 影像与材质 / IMAGE" in assembled
            assert "no small text at all" not in assembled
            assert "wordmark at three sizes" not in assembled
            assert "no color-name label" not in assembled
            assert "no percentage text" not in assembled
            assert "ratios are shown only by the width" not in assembled
            for banned in ("The only words", "No explanatory caption", "no English subtitle", "不要说明文字", "只能出现这些字"):
                assert banned not in assembled, banned
        if slot == "logo_c":
            assert "cup-shaped" in assembled
            assert "The wordmark appears exactly once per zone." in assembled


def test_closing_rules_are_in_the_skill_instructions():
    from pathlib import Path
    text = Path("src/skills.ts").read_text(encoding="utf-8")
    start = text.index("id: 'brand-identity-director'")
    skill = text[start:text.index("category: 'branding'", start)]
    assert "矢量替换" in skill and "色值为屏幕估算" in skill
    assert "可直接投产" in skill and "Never say" in skill
    assert "words consistent with the moodboard" in skill
    assert "does not state hex values" in skill
    assert "exact values are on the spec card" in skill
    assert "moodboard color cell" in skill
    assert "each swatch has a Chinese color name, a role, and a percentage" in skill
    assert "any accent is at most about 5%" in skill
    assert "no color-name label" not in skill
    assert "no percentage text" not in skill
    assert "ratios are shown only by the width" not in skill
    assert "Do not write invented body copy" in skill and "Do not invent English" in skill
    assert "cup sleeve" in skill
    skill_headings = [
        "标识 / LOGO", "色彩 / COLOR", "变体 / VARIANTS", "字体 / TYPE",
        "版式 / LAYOUT", "使用禁忌 / MISUSE", "影像与材质 / IMAGE",
    ]
    assert "exactly 7 panels" in skill
    assert [skill.index(heading) for heading in skill_headings] == sorted(skill.index(heading) for heading in skill_headings)
    for old in OLD_SPEC_HEADINGS:
        assert old not in skill, old
    assert "最小使用尺寸" in skill and "最小尺寸" not in skill.replace("最小使用尺寸", "")
    assert "no small text at all" not in skill and "one garbled character is not acceptable" in skill
    assert "Do not print an English instruction label." in skill
    assert "accent color or the dark color from the confirmed color direction" in skill
    assert "reversed out inside it as negative space" in skill and "not drawn as a positive bird" in skill
    assert "indigo" not in skill.lower() and "靛蓝" not in skill
    assert "Paper ground, not black." in skill
    assert "full bilingual heading" in skill and "wordmark at three sizes" not in skill
    assert "Allowed on-card text includes the bilingual headings" in skill
    assert "陶土橘" not in skill and "栖木咖啡" not in skill
    for banned in ("The only words", "No explanatory caption", "no English subtitle", "不要说明文字", "只能出现这些字"):
        assert banned not in skill, banned
    assert "wordmark appears exactly once per zone" in skill
    assert "#" not in skill
    hint = brand.default_hint()
    assert "矢量替换" in hint and "色值为屏幕估算" in hint
    assert "#" not in hint
    lock = brand._spec_lock()
    assert "Paper ground, not black." in lock
    assert lock.rstrip().endswith("Paper ground, not black.")
    assert lock == brand.scrub_internal_marks(lock)
    assert lock in hint
    assert "Paper ground, not black." in hint
    assert "accent color or the dark color from the confirmed color direction" in hint
    assert "indigo" not in hint.lower() and "靛蓝" not in hint


def test_fallback_copy_does_not_name_one_brand():
    spec = _card1()
    blob = __import__("json").dumps(spec, ensure_ascii=False)
    assert "栖木" not in blob and "QIMU" not in blob and "枝桠" not in blob
    brand._progress()["urls"] = {"logo_a": "/a.png", "logo_b": "/b.png", "logo_c": "/c.png"}
    card3 = validate_spec({"questions": [{
        "id": "bi_direction",
        "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
        "options": [{"id": "A", "label": "x"}],
    }]})
    labels = [opt["label"] for opt in card3["questions"][0]["options"]]
    assert labels == ["单线鸟停枝", "木牌加圆印", "杯形负空间"]
    assert [opt["description"] for opt in card3["questions"][0]["options"]] == [
        "一根连续的线，画出停在枝上的鸟",
        "实心木牌，旁边一枚圆形印章",
        "杯子外形，停着的鸟是杯中的负空间",
    ]
    assert "栖" not in __import__("json").dumps(card3, ensure_ascii=False)


def test_other_skills_still_preselect_a_recommended_option():
    """The badge-only change is brand card 3. Other cards still copy recommended into defaults."""
    spec = validate_spec({
        "prompt": "which direction?",
        "options": [{"id": "a", "label": "A", "recommended": True}, {"id": "b", "label": "B"}],
    })
    assert spec["defaults"] == ["a"]
    assert spec["options"][0]["recommended"] is True


def test_default_path_image_budget_covers_eight_generates():
    from ComfyArt.bot.run_budget import ProgressTracker, StepObservation
    tracker = ProgressTracker()
    brand.ensure_run_budget(tracker, brand.SKILL, "")
    assert tracker.planned_images == 8 and tracker.gen_cap() == 10
    template = ProgressTracker()
    brand.ensure_run_budget(template, brand.SKILL, "geometric")
    assert template.planned_images == 0
    ask = [StepObservation("ask_user", "ask_user\x00{}", "{}", False)]
    quote = [StepObservation("quote_plan", "quote_plan\x00{}", "{}", False)]
    gen = [StepObservation("generate_image", "generate_image\x00{\"count\": 1}", "{}", False)]
    for _ in range(3):
        assert tracker.over_budget(ask) is False
        assert tracker.over_budget(quote) is False
    for _ in range(8):
        assert tracker.over_budget(gen) is False
    assert tracker.gen_calls == 8 and tracker.gen_calls < tracker.gen_cap()


def test_wrapup_stays_hidden_until_the_four_deliverables_are_placed():
    brand.record_card_answer(_card1(), {"bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
                                         "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]}})
    mood = apply_generate({"skill": brand.SKILL, "prompt": "board"}, brand.SKILL)
    brand.record_submitted(mood, {"ids": ["h-mood"]})
    brand.record_wait({"results": [{"id": "h-mood", "shapes": ["shape:mood"], "urls": ["/m.png"]}]})
    brand.record_card_answer(validate_spec({
        "questions": [{"id": "bi_moodboard", "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
                       "options": [{"id": "A", "label": "就这版，通过"}, {"id": "B", "label": "重出"}]}],
    }), {"bi_moodboard": {"selected": ["A"]}})
    for slot in ("logo_a", "logo_b", "logo_c"):
        logo = apply_generate({"skill": brand.SKILL, "prompt": slot}, brand.SKILL)
        brand.record_submitted(logo, {"ids": [f"h-{slot}"]})
        brand.record_wait({"results": [{"id": f"h-{slot}", "shapes": [f"shape:{slot}"], "urls": [f"/{slot}.png"]}]})
    brand.record_card_answer(validate_spec({
        "questions": [{"id": "bi_direction", "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
                       "options": [{"id": "A", "label": "方向 A"}, {"id": "B", "label": "方向 B"},
                                   {"id": "C", "label": "方向 C"}]}],
    }), {"bi_direction": {"selected": ["A"]}})
    assert brand.should_hold_wrapup() is True
    brand.hold_wrapup("本次交付清单：规范卡、外带杯、纸袋、门头。")
    assert brand.release_wrapup() == ""
    for name in ("spec", "cup", "bag", "store"):
        final = apply_generate({"skill": brand.SKILL, "prompt": name}, brand.SKILL)
        brand.record_submitted(final, {"ids": [f"h-{final['brand_slot']}"]})
        brand.record_wait({"results": [{"id": f"h-{final['brand_slot']}", "shapes": [f"shape:{final['brand_slot']}"],
                                        "urls": [f"/{final['brand_slot']}.png"]}]})
    assert brand.finals_placed() is True
    assert brand.release_wrapup().startswith("本次交付清单")


def test_model_quote_tool_still_names_each_material_and_asks():
    import asyncio
    brand.record_card_answer(_card1(), {"bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
                                         "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]}})
    mood = apply_generate({"skill": brand.SKILL, "prompt": "board"}, brand.SKILL)
    brand.record_submitted(mood, {"ids": ["h-mood"]})
    brand.record_wait({"results": [{"id": "h-mood", "shapes": ["shape:mood"], "urls": ["/m.png"]}]})
    brand.record_card_answer(validate_spec({
        "questions": [{"id": "bi_moodboard", "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
                       "options": [{"id": "A", "label": "就这版，通过"}, {"id": "B", "label": "重出"}]}],
    }), {"bi_moodboard": {"selected": ["A"]}})
    for slot in ("logo_a", "logo_b", "logo_c"):
        logo = apply_generate({"skill": brand.SKILL, "prompt": slot}, brand.SKILL)
        brand.record_submitted(logo, {"ids": [f"h-{slot}"]})
        brand.record_wait({"results": [{"id": f"h-{slot}", "shapes": [f"shape:{slot}"], "urls": [f"/{slot}.png"]}]})
    brand.record_card_answer(validate_spec({
        "questions": [{"id": "bi_direction", "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
                       "options": [{"id": "A", "label": "方向 A"}, {"id": "B", "label": "方向 B"},
                                   {"id": "C", "label": "方向 C"}]}],
    }), {"bi_direction": {"selected": ["A"]}})
    # The model's own quote_plan steps have no brand_slot.
    raw = [{"tool": "generate_image", "text": "image", "model": "", "arguments": {"prompt": f"piece {i}"}}
           for i in range(4)]
    steps = brand.annotate_quote_steps(raw)
    assert [s["arguments"]["brand_slot"] for s in steps] == ["spec", "cup", "bag", "storefront"]

    async def pricer(model, inputs):
        return 0.03, "quote", ""

    async def models_for(feature):
        return []

    quote = asyncio.run(build_quote(steps, "zh", threshold=0.5, pricer=pricer, models_for=models_for))
    assert quote is not None and quote.ask is True
    assert [ln.text for ln in quote.lines] == [
        "规范卡 1536×2048 3:4",
        "外带杯与杯套 1536×2048 3:4",
        "纸袋 1536×2048 3:4",
        "门店门头 2048×1152 16:9",
    ]
    assert all("精确像素" not in ln.text and "Qwen" not in ln.text for ln in quote.lines)


def test_opaque_rgba_is_flattened_even_when_alpha_is_full():
    raw = io.BytesIO()
    Image.new("RGBA", (4, 4), (10, 20, 30, 255)).save(raw, format="PNG")
    flat = brand.flatten_opaque(raw.getvalue())
    with Image.open(io.BytesIO(flat)) as img:
        assert img.mode == "RGB"
        assert img.getpixel((0, 0)) == (10, 20, 30)


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
    assert quote.lines[0].text == "情绪板 2048×1152 16:9"
    assert "精确像素" not in quote.lines[0].text


def test_third_stage_cumulative_is_the_sum_of_the_confirmed_stages():
    """Stages quoted 3, 9, and 12. The third card's cumulative is 24, not 21."""
    import asyncio
    brand.note_confirmed(0.03, 1, stage=1)
    brand.note_confirmed(0.09, 3, stage=2)
    assert brand._progress()["spent"] == 0.12

    async def pricer(model, inputs):
        return 0.03, "quote", ""

    async def models_for(feature):
        return []

    steps = []
    for slot, width, height, ratio in (
        ("spec", 1536, 2048, "3:4"),
        ("cup", 1536, 2048, "3:4"),
        ("bag", 1536, 2048, "3:4"),
        ("storefront", 2048, 1152, "16:9"),
    ):
        steps.append({"text": slot, "tool": "generate_image", "model": brand.QWEN_T2I, "arguments": {
            "skill": brand.SKILL, "brand_slot": slot, "prompt": slot,
            "width": width, "height": height, "ratio": ratio, "count": 1,
        }})
    quote = asyncio.run(build_quote(steps, "zh", threshold=0.5, pricer=pricer, models_for=models_for))
    assert quote is not None
    assert "本阶段 12" in quote.prompt
    assert "累计 24" in quote.prompt
    assert "累计 21" not in quote.prompt
    brand.drop_memory_for_tests()
    assert brand._progress()["spent"] == 0.12
    again = asyncio.run(build_quote(steps, "zh", threshold=0.5, pricer=pricer, models_for=models_for))
    assert "累计 24" in again.prompt


def test_spec_prompt_leads_with_the_panel_contract_and_keeps_the_locked_brief_last():
    caller = brand._spec_lock() + "\nMerge the type and layout panels into 版式 / TYPE."
    spec = brand.fill_default({"brand_slot": "spec", "prompt": caller})["prompt"]
    assert spec.startswith("Draw seven separate panels")
    assert "字体 / TYPE is its own panel" in spec
    assert "版式 / LAYOUT is a different panel" in spec
    assert "percentages sum to 100%" in spec
    assert "soft vignette" in spec
    assert "drawn 「最小使用尺寸」 diagram" in spec
    assert brand._spec_lock().rstrip().endswith("Paper ground, not black.")
    assert spec.rstrip().endswith(brand._spec_assembly_line())
    assert brand._spec_lock() in spec
    assert spec.index("版式 / TYPE") < spec.rindex("Paper ground, not black.")
    assert spec.index("Paper ground, not black.") < spec.index(brand._spec_assembly_line())
    assert spec.count("exactly 7 panels") == 1
    again = brand.fill_default({"brand_slot": "spec", "prompt": spec})["prompt"]
    assert again.count("Draw seven separate panels") == 1
    assert again.count("exactly 7 panels") == 1
    assert again.rstrip().endswith(brand._spec_assembly_line())
    assert again == spec


def test_moodboard_prompt_keeps_the_locked_color_direction():
    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]},
        "bi_color": {"selected": ["A"]},
        "bi_mark": {"selected": ["A"]},
        "bi_source": {"selected": ["A"]},
    })
    mood = brand.fill_default({"brand_slot": "moodboard", "prompt": "暖木棕 + 米白"})
    assert "暖土色为主 + 低饱和靛蓝点缀" in mood["prompt"]
    assert "Confirmed color direction" in mood["prompt"]
    again_mood = brand.fill_default({"brand_slot": "moodboard", "prompt": mood["prompt"]})
    assert again_mood["prompt"] == mood["prompt"]
    logo = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C"})
    assert "The confirmed color direction for this badge's accent is: 暖土色为主 + 低饱和靛蓝点缀" in logo["prompt"]
    assert "靛蓝" not in brand._SLOT_LOCK["logo_c"] and "indigo" not in brand._SLOT_LOCK["logo_c"].lower()
    again = brand.fill_default({"brand_slot": "logo_c", "prompt": logo["prompt"]})
    assert again["prompt"] == logo["prompt"]


def test_logo_c_warm_earth_prompt_does_not_name_indigo():
    """Pure warm earth has no indigo, so the assembled logo C prompt must not invent one."""
    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]},
        "bi_color": {"selected": ["B"]},
        "bi_mark": {"selected": ["A"]},
        "bi_source": {"selected": ["A"]},
    })
    logo = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C"})["prompt"]
    assert "indigo" not in logo.lower()
    assert "靛蓝" not in logo.lower()
    assert "accent color or the dark color from the confirmed color direction" in logo
    assert "reversed out inside it as negative space" in logo
    assert "纯暖土色系" in logo
    assert "indigo" not in brand._SLOT_LOCK["logo_c"].lower()
    assert "靛蓝" not in brand.default_hint().lower()


def test_visual_assembly_follows_the_gold_sheet():
    """Slot prompts and runtime color lines carry the gold layout. The shared lock names no palette."""
    from pathlib import Path
    skill_text = Path("src/skills.ts").read_text(encoding="utf-8")
    skill_at = skill_text.index("id: 'brand-identity-director'")
    skill = skill_text[skill_at:skill_text.index("category: 'branding'", skill_at)]
    hint = brand.default_hint()
    banned_names = ("陶土橙", "焦糖棕", "燕麦奶白", "深焙棕", "低饱和靛蓝", "靛蓝", "暖土为主·蔚蓝点缀")
    assert "焯糖棕" not in banned_names and "低饱和蔚蓝" not in banned_names
    assert "焦糖棕" in banned_names and "低饱和靛蓝" in banned_names
    for banned in banned_names:
        assert banned not in brand._SLOT_LOCK["logo_c"], banned
        assert banned not in brand._SLOT_LOCK["logo_a"], banned
        assert banned not in brand._SLOT_LOCK["logo_b"], banned
        assert banned not in brand._SLOT_LOCK["cup"], banned
        assert banned not in brand._SLOT_LOCK["bag"], banned
        assert banned not in brand._SLOT_LOCK["storefront"], banned
        assert banned not in brand._spec_lock(), banned
        assert banned not in brand._SPEC_PREFACE, banned
        assert banned not in hint, banned
        assert banned not in skill, banned
    for source in (hint, skill):
        assert "The cup silhouette has no handle." in source
        assert "小尺寸 is an icon, a cup-lid sticker, and an emboss." in source
        assert "横版 appears once and must not be drawn a second time." in source
        assert "a paper takeaway cup wearing the sleeve, and a clear iced cup" in source
        assert "A flat sleeve lies in front." in source
        assert "one thin stripe in the accent color of the confirmed color direction" in source
        assert "One plain white cup alone is wrong." in source
        assert "a large bag standing and a smaller bag lying in front" in source
        assert "thin vertical stripe in the accent color of the confirmed color direction" in source
        assert "fascia eave is the accent color or the dark color from the confirmed color direction, not bare wood" in source
        assert "影像格小字不得写错" in source
    assert "影像格小字不得写错" not in brand._spec_lock()
    assert "影像格小字不得写错" not in brand._SPEC_PREFACE
    logo_c = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C"})["prompt"]
    assert "The cup silhouette has no handle." in logo_c
    assert "not a picture of a handled cup" in logo_c
    assert logo_c.count("cup-shaped") == 1
    assert "an icon, a cup-lid sticker, and an emboss" in logo_c
    assert "Do not draw a second landscape treatment." in logo_c
    assert "横版 appears once." in logo_c
    logo_a = brand.fill_default({"brand_slot": "logo_a", "prompt": "方向A"})["prompt"]
    assert "a rounded-square icon, a circular stamp, and a solid square badge" in logo_a
    logo_b = brand.fill_default({"brand_slot": "logo_b", "prompt": "方向B"})["prompt"]
    assert "the seal, a horizontal plaque, a circle, and a square" in logo_b
    cup = brand.fill_default({"brand_slot": "cup", "prompt": "杯"})["prompt"]
    assert "a paper takeaway cup wearing the sleeve, and a clear iced cup" in cup
    assert "one thin stripe in the accent color" in cup
    assert "One plain white cup alone is wrong." in cup
    assert "A bare cup with no sleeve is wrong." in cup
    bag = brand.fill_default({"brand_slot": "bag", "prompt": "袋"})["prompt"]
    assert "a large bag standing and a smaller bag lying in front" in bag
    assert "thin vertical stripe" in bag
    store = brand.fill_default({"brand_slot": "storefront", "prompt": "门头"})["prompt"]
    assert "fascia eave" in store and "not bare wood" in store
    assert "full shopfront, front view" in store
    spec = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})["prompt"]
    assert spec.startswith("Draw seven separate panels")
    assert spec.count("exactly 7 panels") == 1
    assert spec.count("Draw seven separate panels") == 1
    assert "3 by 3 grid" in spec
    assert "independent panel" in spec
    assert "minimum-size diagram of the mark with measurement lines" in spec
    assert "The hue hint is not a swatch and it does not remove the swatches." in spec
    assert "Do not write COLR, TISUS, or INMAGE." in spec
    assert "影像格小字不得写错" in spec
    assert "影像格 small labels and captions on 影像与材质 / IMAGE must be spelled correctly" in spec
    assert "no typo, no garble, and no invented heading fragment" in spec
    assert "影像格小字不得写错" not in brand._spec_lock()
    assert "影像格小字不得写错" not in brand._SPEC_PREFACE
    assert "影像格小字不得写错" in brand.default_hint()
    assert spec.rstrip().endswith(brand._spec_assembly_line())
    assert brand._spec_lock().rstrip().endswith("Paper ground, not black.")
    again = brand.fill_default({"brand_slot": "spec", "prompt": spec})["prompt"]
    assert again == spec

    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]},
        "bi_color": {"selected": ["A"]},
        "bi_mark": {"selected": ["A"]},
        "bi_source": {"selected": ["A"]},
    })
    hint = "暖土色为主 + 低饱和靛蓝点缀"
    mood = brand.fill_default({"brand_slot": "moodboard", "prompt": "板"})["prompt"]
    assert "print this direction as the cell annotation" in mood
    assert "Do not swap the accent for a different hue." in mood
    assert hint in mood
    assert brand.fill_default({"brand_slot": "moodboard", "prompt": mood})["prompt"] == mood
    badge = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C"})["prompt"]
    assert "Fill the badge with that accent or the dark color in this direction." in badge
    assert "Do not invent a hue that is outside this direction." in badge
    assert brand.fill_default({"brand_slot": "logo_c", "prompt": badge})["prompt"] == badge
    for slot, part in (
        ("cup", "sleeve stripe"),
        ("bag", "side stripe"),
        ("storefront", "fascia eave"),
    ):
        filled = brand.fill_default({"brand_slot": slot, "prompt": slot})["prompt"]
        assert "The confirmed color direction for the " + part + " is: " + hint in filled
        assert brand.fill_default({"brand_slot": slot, "prompt": filled})["prompt"] == filled
    spec_a = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})["prompt"]
    assert "Sample the swatches from the confirmed color direction: " + hint in spec_a
    assert brand.fill_default({"brand_slot": "spec", "prompt": spec_a})["prompt"] == spec_a

    brand.reset_for_tests()
    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]},
        "bi_color": {"selected": ["B"]},
        "bi_mark": {"selected": ["A"]},
        "bi_source": {"selected": ["A"]},
    })
    for slot in ("logo_c", "spec", "cup", "bag", "storefront", "moodboard"):
        warm = brand.fill_default({"brand_slot": slot, "prompt": slot})["prompt"]
        assert "indigo" not in warm.lower() and "靛蓝" not in warm, slot


def test_card3_options_match_the_enforced_structures():
    card = validate_spec({"questions": [{
        "id": "bi_direction",
        "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
        "options": [
            {"id": "A", "label": "手刻印章", "recommended": True, "image_url": "/a.png"},
            {"id": "B", "label": "木纹", "image_url": "/b.png"},
            {"id": "C", "label": "方向 C", "image_url": "/c.png"},
        ],
    }]})
    opts = card["questions"][0]["options"]
    assert [(o["label"], o["description"]) for o in opts] == [
        ("单线鸟停枝", "一根连续的线，画出停在枝上的鸟"),
        ("木牌加圆印", "实心木牌，旁边一枚圆形印章"),
        ("杯形负空间", "杯子外形，停着的鸟是杯中的负空间"),
    ]
    blob = __import__("json").dumps(card, ensure_ascii=False)
    assert "手刻印章" not in blob
    assert opts[0]["recommended"] is True
    assert [o.get("image_url") for o in opts] == ["/a.png", "/b.png", "/c.png"]
    brand.reset_for_tests()
    brand._progress()["urls"] = {"logo_a": "/a.png", "logo_b": "/b.png", "logo_c": "/c.png"}
    loose = brand.normalize_card({"questions": [{
        "prompt": "选定哪个 Logo 方向？",
        "allow_other": True,
        "options": [
            {"id": "A", "label": "甲"}, {"id": "B", "label": "乙"},
            {"id": "C", "label": "丙"}, {"id": "D", "label": "其他"},
        ],
    }]}, "zh")
    loose_opts = loose["questions"][0]["options"]
    assert loose["allow_other"] is False
    assert [o["id"] for o in loose_opts] == ["A", "B", "C"]
    assert [o.get("image_url") for o in loose_opts] == ["/a.png", "/b.png", "/c.png"]
    assert all(o["label"] != "其他" for o in loose_opts)
    assert "defaults" not in card["questions"][0]
    en = brand.normalize_card({"questions": [{
        "id": "bi_direction",
        "prompt": "Which logo direction should be the final mark (logo_primary)?",
        "options": [{"id": "A", "label": "Hand seal", "recommended": True, "image_url": "/a.png"},
                    {"id": "B", "label": "B", "image_url": "/b.png"},
                    {"id": "C", "label": "C", "image_url": "/c.png"}],
    }]}, "en")
    en_opts = en["questions"][0]["options"]
    assert [o["label"] for o in en_opts] == [
        "Single-line bird on a branch",
        "Wooden signboard and round seal",
        "Cup-shaped negative space",
    ]
    assert "bird perched on a branch" in en_opts[0]["description"]
    assert "round seal" in en_opts[1]["description"]
    assert "perched bird is the negative space inside the cup" in en_opts[2]["description"]
    assert en_opts[0]["recommended"] is True


def _direction_ask(options):
    return {"questions": [{
        "id": "bi_direction",
        "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
        "options": options,
    }]}


def test_card3_accepts_logo_slot_ids_and_recovered_wait_urls():
    card = validate_spec(_direction_ask([
        {"id": "logo_a", "label": "方向 A", "image_url": "/from-a.png"},
        {"id": "logo_b", "label": "方向 B", "image_url": "/from-b.png"},
        {"id": "logo_c", "label": "方向 C", "image_url": "/from-c.png"},
    ]))
    assert [o["image_url"] for o in card["questions"][0]["options"]] == ["/from-a.png", "/from-b.png", "/from-c.png"]
    brand.reset_for_tests()
    brand.record_wait({"results": [
        {"id": "logo_a", "status": "done", "shapes": ["s:a"], "urls": ["/slot-a.png"]},
        {"id": "B", "status": "done", "shapes": ["s:b"], "urls": ["/slot-b.png"]},
        {"id": "task-c", "brand_slot": "logo_c", "status": "done", "shapes": ["s:c"], "urls": ["/slot-c.png"]},
    ]})
    recovered = validate_spec(_direction_ask([
        {"id": "A", "label": "方向 A"},
        {"id": "B", "label": "方向 B"},
        {"id": "C", "label": "方向 C"},
    ]))
    assert [o["image_url"] for o in recovered["questions"][0]["options"]] == [
        "/slot-a.png", "/slot-b.png", "/slot-c.png"]


def test_card3_without_logo_urls_is_an_error_and_the_second_try_stops():
    ask = _direction_ask([
        {"id": "A", "label": "方向 A"},
        {"id": "B", "label": "方向 B"},
        {"id": "C", "label": "方向 C"},
    ])
    try:
        validate_spec(ask)
    except ValueError as exc:
        first = str(exc)
    else:
        raise AssertionError("a text-only card 3 was returned")
    assert "还不能出方向卡" in first
    assert "wait_generation" in first
    assert "[non-retryable]" not in first
    try:
        validate_spec(ask)
    except ValueError as exc:
        second = str(exc)
    else:
        raise AssertionError("the second miss still returned a card")
    assert "[non-retryable]" in second
    assert "还不能出方向卡" in second


def test_spec_palette_is_sampled_and_the_color_answer_is_only_a_hue_hint():
    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]},
        "bi_color": {"selected": ["B"], "other_text": "暖木棕 #6B4A32"},
        "bi_mark": {"selected": ["A"]},
        "bi_source": {"selected": ["A"]},
    })
    assert brand.color_hue_hint() == "暖木棕"
    assert "#" not in brand.color_hue_hint()
    spec = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})
    assert "暖木棕" in spec["prompt"]
    assert "6B4A32" not in spec["prompt"]
    assert "#C46A3A" not in spec["prompt"] and "#C4784A" not in spec["prompt"]
    assert "#" not in spec["prompt"]
    assert "sampled from the moodboard 色彩 cell" in spec["prompt"]
    assert "never a printed swatch" in spec["prompt"]
    brand.reset_for_tests()
    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]},
        "bi_color": {"selected": ["B"]},
        "bi_mark": {"selected": ["A"]},
        "bi_source": {"selected": ["A"]},
    })
    family = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})
    assert "纯暖土色系" in family["prompt"]
    assert "#" not in family["prompt"]


def _logos_ready():
    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
        "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]},
    })
    brand.record_submitted({"brand_slot": "moodboard"}, {"ids": ["h"]})
    brand.record_wait({"results": [{"id": "h", "shapes": ["shape:mood"], "urls": ["/m.png"]}]})
    brand.record_card_answer({"questions": [{
        "id": "bi_moodboard", "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
        "options": [{"id": "A", "label": "就这版，通过"}],
    }]}, {"bi_moodboard": {"selected": ["A"]}})


def _logo_calls():
    return tuple(
        ("generate_image", {"prompt": slot, "skill": brand.SKILL, "brand_slot": slot})
        for slot in ("logo_a", "logo_b", "logo_c")
    )


async def _brand_turn(monkeypatch, script, *, unit_price: float = 0.03, threshold: float | None = None,
                      user_text: str = "做三个方向", answers: list[str] | None = None):
    """One scripted turn. Pricing and MCP are local; WaveSpeed submit is counted and refused."""
    from ComfyArt.api import wavespeed
    from ComfyArt.bot.providers import TurnHandle
    from ComfyArt.bot.run_budget import resolve_policy
    from test_agent_budget_391 import Rig

    submits: list = []

    async def submit(*_args, **_kwargs):
        submits.append(1)
        raise AssertionError("wavespeed.submit must not run in this test")

    monkeypatch.setattr(wavespeed, "submit", submit)
    if threshold is not None:
        monkeypatch.setattr(wavespeed, "confirm_usd", lambda: threshold)
    confirms: list = []
    rig = Rig(monkeypatch, script)
    monkeypatch.setattr(rig.p, "_run_policy", lambda: resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"}))

    async def price(model, inputs):
        return (unit_price, "quote", "test-stage")

    monkeypatch.setattr(rig.p, "_price_one", price)

    async def models_for(feature):
        return []

    monkeypatch.setattr(rig.p, "_models_for", models_for)

    async def yes(spec, turn, handle, **kwargs):
        confirms.append(spec)
        if not answers:
            return "start"
        idx = len(confirms) - 1
        return answers[idx] if idx < len(answers) else "cancel"

    monkeypatch.setattr(rig.p, "_confirm_plan", yes)
    _res, events = await rig.send(user_text, goal="", handle=TurnHandle())
    return rig, events, confirms, submits


def _tool_texts(events, name):
    return [e.text for e in events if e.t == "tool_result" and e.name == name]


async def test_a_repeat_of_a_confirmed_stage_does_not_open_another_card(monkeypatch):
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()

        def first_script(messages, n):
            if n == 0:
                return calls(*_logo_calls())
            return reply("好")

        rig, _events, confirms, submits = await _brand_turn(monkeypatch, first_script)
        assert len(confirms) == 1
        assert len(rig.paid_mcp()) == 3
        assert submits == []
        assert brand._progress()["spent"] == 0.09
        assert brand.stage_repeat(_three_logos()) == "done"

        def again_script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _three_logos()}), *_logo_calls())
            return reply("好")

        rig, events, confirms, submits = await _brand_turn(monkeypatch, again_script)
        assert confirms == []
        assert rig.paid_mcp() == []
        assert submits == []
        texts = _tool_texts(events, "quote_plan") + _tool_texts(events, "generate_image")
        assert len(texts) == 4
        assert all("下一阶段" in text for text in texts)
        assert brand._progress()["spent"] == 0.09
    finally:
        BOT_CHAT_ID.reset(token)


async def test_identical_quote_dispatches_once_before_it_is_marked_done(monkeypatch):
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()

        def quote_only(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _three_logos()}))
            return reply("好")

        rig, _events, confirms, submits = await _brand_turn(monkeypatch, quote_only)
        assert len(confirms) == 1
        assert rig.paid_mcp() == []
        assert submits == []
        assert brand.stage_repeat(_three_logos()) == "continue"
        assert brand._progress()["spent"] == 0.09

        def generate(messages, n):
            if n == 0:
                return calls(*_logo_calls())
            return reply("好")

        rig, _events, confirms, submits = await _brand_turn(monkeypatch, generate)
        assert confirms == []
        assert len(rig.paid_mcp()) == 3
        assert submits == []
        assert brand.stage_repeat(_three_logos()) == "done"

        rig, events, confirms, submits = await _brand_turn(monkeypatch, generate)
        assert confirms == []
        assert rig.paid_mcp() == []
        assert submits == []
        texts = _tool_texts(events, "generate_image")
        assert len(texts) == 3 and all("下一阶段" in text for text in texts)
        assert brand._progress()["spent"] == 0.09
    finally:
        BOT_CHAT_ID.reset(token)


async def test_a_changed_fingerprint_asks_again_using_spend_before(monkeypatch):
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()

        def first_script(messages, n):
            if n == 0:
                return calls(*_logo_calls())
            return reply("好")

        await _brand_turn(monkeypatch, first_script)
        assert brand._progress()["spent"] == 0.09

        changed = [
            _logo_plan(slot, width=1024, height=1024, edit_model="other-model")
            for slot in ("logo_a", "logo_b", "logo_c")
        ] + [_logo_plan("logo_a", width=1024, height=1024, edit_model="other-model")]
        assert brand.stage_repeat(changed) == "new"

        def replan(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": changed}))
            return reply("好")

        _rig, _events, confirms, submits = await _brand_turn(monkeypatch, replan)
        assert len(confirms) == 1
        assert submits == []
        prompt = confirms[0]["prompt"]
        # 4 x $0.03 = $0.12 = 12 credits. spend_before removes the previous $0.09,
        # so the card is 12, not 0.09 + 0.12 = 21.
        assert "累计 12" in prompt
        assert "21" not in prompt
        assert brand._progress()["spent"] == 0.12
        assert brand.spend_before(2) == 0.0
    finally:
        BOT_CHAT_ID.reset(token)


def _short_logo_steps():
    """The quote the model actually sent: short prompts, same slot, model, size and count."""
    steps = []
    for slot, letter in (("logo_a", "A"), ("logo_b", "B"), ("logo_c", "C")):
        steps.append({
            "tool": "generate_image",
            "model": brand.QWEN_EDIT,
            "arguments": {
                "skill": brand.SKILL,
                "brand_slot": slot,
                "prompt": (
                    f"Logo direction {letter} for 栖木咖啡 QIMU COFFEE: "
                    "one open single-line bird on a branch, bilingual lockup, 2048x2048"
                ),
                "width": 2048,
                "height": 2048,
                "count": 1,
                "refs": ["shape:mood"],
                "edit_model": brand.QWEN_EDIT,
            },
        })
    return steps


def _quoted_generate(slot: str):
    """The generate that repeats the confirmed quote arguments, not a new prompt."""
    step = next(item for item in _short_logo_steps() if item["arguments"]["brand_slot"] == slot)
    return ("generate_image", dict(step["arguments"]))


def _long_generate(slot: str):
    return ("generate_image", {
        "prompt": (
            f"LONG PROMPT for {slot}. Full construction sheet, bilingual lockup, "
            "grid, reversed block, and many sentences that are not the quote text."
        ),
        "skill": brand.SKILL,
        "brand_slot": slot,
        "refs": ["shape:mood"],
    })


async def _live_brand_run(monkeypatch, script, handle=None):
    """One agent-loop turn. The plan gate is created once and kept across model steps."""
    from ComfyArt.api import wavespeed
    from ComfyArt.bot.providers import TurnHandle
    from test_agent_budget_391 import Rig

    submits: list = []

    async def submit(*_args, **_kwargs):
        submits.append(1)
        raise AssertionError("wavespeed.submit must not run in this test")

    monkeypatch.setattr(wavespeed, "submit", submit)
    confirms: list = []
    rig = Rig(monkeypatch, script)

    async def price(model, inputs):
        return (0.03, "quote", "test-stage")

    monkeypatch.setattr(rig.p, "_price_one", price)

    async def models_for(feature):
        return []

    monkeypatch.setattr(rig.p, "_models_for", models_for)

    async def yes(spec, turn, handle, **kwargs):
        confirms.append(spec)
        return "start"

    monkeypatch.setattr(rig.p, "_confirm_plan", yes)
    res, events = await rig.send("做三个方向", goal="", handle=handle or TurnHandle())
    return rig, res, events, confirms, submits


async def test_short_quote_then_confirmed_generates_submit_once_each(monkeypatch):
    """quote_plan alone, then one generate of that confirmed snapshot per later step."""
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        slots = ("logo_a", "logo_b", "logo_c")

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _short_logo_steps()}))
            if 1 <= n <= 3:
                return calls(_quoted_generate(slots[n - 1]))
            return reply("好")

        rig, _res, events, confirms, submits = await _live_brand_run(monkeypatch, script)
        assert len(confirms) == 1
        assert submits == []
        paid = rig.paid_mcp()
        assert [args["brand_slot"] for _name, args in paid] == list(slots)
        assert all("Logo direction" in args["prompt"] for _name, args in paid)
        assert all("LONG PROMPT" not in args["prompt"] for _name, args in paid)
        assert all(e.t != "tool_result" or "请先调用 quote_plan" not in e.text for e in events)
        assert brand.stage_repeat(_short_logo_steps()) == "done"
    finally:
        BOT_CHAT_ID.reset(token)


async def test_a_partial_stage_resumes_only_the_unsubmitted_slots(monkeypatch):
    """One submitted logo must not close the stage. The next turn finishes the other two."""
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()

        def first(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _short_logo_steps()}), _quoted_generate("logo_a"))
            return reply("好")

        rig, _res, _events, confirms, submits = await _live_brand_run(monkeypatch, first)
        assert len(confirms) == 1
        assert submits == []
        assert [args["brand_slot"] for _name, args in rig.paid_mcp()] == ["logo_a"]
        assert brand.submitted_slots(2) == {"logo_a"}
        assert brand.stage_repeat(_short_logo_steps()) == "continue"

        def again(messages, n):
            if n == 0:
                return calls(
                    ("quote_plan", {"steps": _short_logo_steps()}),
                    _quoted_generate("logo_a"),
                    _quoted_generate("logo_b"),
                    _quoted_generate("logo_c"),
                )
            return reply("好")

        rig, _res, events, confirms, submits = await _live_brand_run(monkeypatch, again)
        assert confirms == []
        assert submits == []
        assert [args["brand_slot"] for _name, args in rig.paid_mcp()] == ["logo_b", "logo_c"]
        assert "已经提交过了" in " ".join(_tool_texts(events, "generate_image"))
        assert brand.stage_repeat(_short_logo_steps()) == "done"
        assert brand.submitted_slots(2) == {"logo_a", "logo_b", "logo_c"}
    finally:
        BOT_CHAT_ID.reset(token)


async def test_plan_gate_stops_when_the_same_call_is_blocked_twice(monkeypatch):
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        extra = {"calls": 0}

        def script(messages, n):
            extra["calls"] = n + 1
            if n == 0:
                return calls(("quote_plan", {"steps": _short_logo_steps()}))
            if n in (1, 2):
                return calls(("generate_image", {
                    "prompt": "unconfirmed spec board " * 12,
                    "skill": brand.SKILL,
                    "brand_slot": "spec",
                }))
            return reply("应该停在第二次拦截")

        rig, res, events, confirms, submits = await _live_brand_run(monkeypatch, script)
        assert len(confirms) == 1
        assert rig.paid_mcp() == []
        assert submits == []
        texts = _tool_texts(events, "generate_image")
        assert texts[0].startswith("[tool error]") and "请先调用 quote_plan" in texts[0]
        assert "拦住了两次" in texts[1]
        assert "请先调用 quote_plan" not in texts[1]
        assert extra["calls"] == 3  # quote, first block, second block; no further model step
        stop = res.run["stop"]
        assert stop["reason"] == "error" and stop["sub"] == "tool"
        assert "拦住了两次" in stop["detail"]
    finally:
        BOT_CHAT_ID.reset(token)


async def test_stop_interrupts_before_the_next_brand_generate(monkeypatch):
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from ComfyArt.bot.providers import TurnHandle
    from test_agent_budget_391 import calls

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        handle = TurnHandle()

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _short_logo_steps()}))
            handle.stop_requested = True
            return calls(_long_generate("logo_a"))

        rig, res, _events, confirms, submits = await _live_brand_run(monkeypatch, script, handle)
        assert len(confirms) == 1
        assert rig.paid_mcp() == []
        assert submits == []
        assert rig.n == 2
        assert res.aborted is True
        assert res.run["stop"]["reason"] == "user_stop"
    finally:
        BOT_CHAT_ID.reset(token)


def _preset_generate(prompt: str, *, skill: bool) -> tuple[str, dict]:
    """One industry-template generate. `skill` False omits the skill key entirely."""
    args = {"prompt": prompt, "preset": "geometric"}
    if skill:
        args["skill"] = brand.SKILL
    return ("generate_image", args)


async def _preset_turns(monkeypatch, *, skill: bool, batched: bool, unit_price: float, turns: int = 1):
    """phase=logos preset calls. Returns one (confirms, paid submits) pair per turn.

    MCP stands in for the provider, so a submit is a generate_image that the plan
    gate allowed. wavespeed.submit stays at 0.
    """
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        assert brand._progress().get("phase") == "logos"
        rows = []
        for turn in range(turns):
            if batched:
                items = (
                    _preset_generate(f"mark {turn}a", skill=skill),
                    _preset_generate(f"mark {turn}b", skill=skill),
                )
            else:
                items = (_preset_generate(f"mark {turn}", skill=skill),)

            def script(messages, n, items=items):
                if n == 0:
                    return calls(*items)
                return reply("好")

            rig, _events, confirms, submits = await _brand_turn(
                monkeypatch, script, unit_price=unit_price, threshold=0.5)
            paid = rig.paid_mcp()
            assert submits == []
            assert all("brand_slot" not in args for _name, args in paid)
            rows.append((len(confirms), len(paid)))
        return rows
    finally:
        BOT_CHAT_ID.reset(token)


@pytest.mark.parametrize("with_skill", [True, False])
async def test_logos_preset_single_below_line_submits_without_confirm(monkeypatch, with_skill):
    """Below the line: no skill still submits with 0 confirms.

    A skill preset during an open brand stage confirms every call, including under $0.50.
    """
    rows = await _preset_turns(monkeypatch, skill=with_skill, batched=False, unit_price=0.03, turns=2)
    if with_skill:
        assert rows == [(1, 1), (1, 1)]
    else:
        assert rows == [(0, 1), (0, 1)]


@pytest.mark.parametrize("with_skill", [True, False])
async def test_logos_preset_single_above_line_each_submit_confirms(monkeypatch, with_skill):
    """Above the line: each single preset submit has its own confirm. Reuse is the P1."""
    rows = await _preset_turns(monkeypatch, skill=with_skill, batched=False, unit_price=0.60, turns=2)
    assert rows == [(1, 1), (1, 1)]
    assert sum(c for c, _s in rows) == sum(s for _c, s in rows) == 2


@pytest.mark.parametrize("with_skill", [True, False])
async def test_logos_preset_batch_below_line_submits_without_confirm(monkeypatch, with_skill):
    """Below the line: no skill submits the batch with 0 confirms.

    A skill preset batch during an open brand stage confirms once, then both submit.
    """
    rows = await _preset_turns(monkeypatch, skill=with_skill, batched=True, unit_price=0.03, turns=1)
    if with_skill:
        assert rows == [(1, 2)]
    else:
        assert rows == [(0, 2)]


@pytest.mark.parametrize("with_skill", [True, False])
async def test_logos_preset_batch_above_line_does_not_reuse_confirm(monkeypatch, with_skill):
    """Above the line a batch confirms once for the calls quoted together, then both submit.

    A later batch confirms again (confirms stay 1, not 0). stage_repeat=continue,
    the P1, would submit that later batch on the earlier confirm.
    """
    rows = await _preset_turns(monkeypatch, skill=with_skill, batched=True, unit_price=0.60, turns=2)
    assert rows == [(1, 2), (1, 2)]


_SKILL_START = "Use the ComfyArt skill 'brand-identity-director' for this task"


def _bare_generate(prompt: str) -> tuple[str, dict]:
    """No skill and no preset. current_skill stays empty unless the start line is sent."""
    return ("generate_image", {"prompt": prompt})


async def _bare_turns(monkeypatch, *, batched: bool, unit_price: float, turns: int = 2,
                      user_text: str = "做三个方向"):
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        assert brand._progress().get("phase") == "logos"
        rows = []
        slots = []
        for turn in range(turns):
            if batched:
                items = (
                    _bare_generate(f"open {turn}a"),
                    _bare_generate(f"open {turn}b"),
                )
            else:
                items = (_bare_generate(f"open {turn}"),)

            def script(messages, n, items=items):
                if n == 0:
                    return calls(*items)
                return reply("好")

            rig, _events, confirms, submits = await _brand_turn(
                monkeypatch, script, unit_price=unit_price, threshold=0.5, user_text=user_text)
            paid = rig.paid_mcp()
            assert submits == []
            rows.append((len(confirms), len(paid)))
            slots.append([args.get("brand_slot") for _name, args in paid])
        return rows, slots
    finally:
        BOT_CHAT_ID.reset(token)


async def test_logos_unscoped_single_below_line_does_not_reuse_confirm(monkeypatch):
    """No skill, no preset, current_skill empty. Below the line: 0 confirms, both submit."""
    rows, slots = await _bare_turns(monkeypatch, batched=False, unit_price=0.03)
    assert rows == [(0, 1), (0, 1)]
    assert slots == [[None], [None]]


async def test_logos_unscoped_single_above_line_each_submit_confirms(monkeypatch):
    """No skill, no preset, current_skill empty. Above the line each submit confirms."""
    rows, slots = await _bare_turns(monkeypatch, batched=False, unit_price=0.60)
    assert rows == [(1, 1), (1, 1)]
    assert slots == [[None], [None]]


async def test_logos_unscoped_batch_below_line_submits_without_confirm(monkeypatch):
    """No skill, no preset, current_skill empty. A batch under the line submits directly."""
    rows, slots = await _bare_turns(monkeypatch, batched=True, unit_price=0.03, turns=2)
    assert rows == [(0, 2), (0, 2)]
    assert slots == [[None, None], [None, None]]


async def test_logos_unscoped_batch_above_line_does_not_reuse_confirm(monkeypatch):
    """No skill, no preset, current_skill empty. Each batch above the line confirms once."""
    rows, slots = await _bare_turns(monkeypatch, batched=True, unit_price=0.60)
    assert rows == [(1, 2), (1, 2)]
    assert slots == [[None, None], [None, None]]


async def test_default_eight_image_path_with_skill_start_line_is_unchanged(monkeypatch):
    """The skill start line still fills the default slot and asks, then a repeat is done.

    begin_batch starts each turn at the same unsubmitted slot. The first turn confirms
    logo_a. The second turn is that same confirmed slot, so it does not submit again.
    """
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        user_text = f"{_SKILL_START}\n做三个方向"

        def script(messages, n):
            if n == 0:
                return calls(_bare_generate("default path"))
            return reply("好")

        rig, _events, confirms, submits = await _brand_turn(
            monkeypatch, script, unit_price=0.03, threshold=0.5, user_text=user_text)
        assert submits == []
        assert len(confirms) == 1
        assert [args.get("brand_slot") for _name, args in rig.paid_mcp()] == ["logo_a"]
        assert [args.get("skill") for _name, args in rig.paid_mcp()] == [brand.SKILL]

        rig, events, confirms, submits = await _brand_turn(
            monkeypatch, script, unit_price=0.03, threshold=0.5, user_text=user_text)
        assert confirms == []
        assert rig.paid_mcp() == []
        assert submits == []
        texts = _tool_texts(events, "generate_image")
        assert len(texts) == 1 and "下一阶段" in texts[0]
    finally:
        BOT_CHAT_ID.reset(token)


def _logo_a_script(messages, n):
    from test_agent_budget_391 import calls, reply
    if n == 0:
        return calls(("generate_image", {
            "prompt": "logo a",
            "skill": brand.SKILL,
            "brand_slot": "logo_a",
        }))
    return reply("done")


async def test_prompt_mutated_after_binding_does_not_submit(monkeypatch):
    """A confirmed logo_a whose prompt changes after bind submits nothing."""
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID

    real_bind = brand.bind_brand_generate

    def bind(args, quote_steps=None, claimed=None):
        prepared = real_bind(args, quote_steps, claimed)
        if isinstance(prepared, dict):
            prepared["prompt"] = "mutated after binding"
        return prepared

    monkeypatch.setattr(brand, "bind_brand_generate", bind)
    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        rig, events, confirms, submits = await _brand_turn(monkeypatch, _logo_a_script, threshold=0.5)
        prompts = [args.get("prompt") for _name, args in rig.paid_mcp()]
        texts = "\n".join(_tool_texts(events, "generate_image"))
        assert confirms
        assert prompts == []
        assert submits == []
        assert "参数已变化" in texts
        assert brand.submitted_slots(2) == set()
        assert list((brand._stage_record(2) or {}).get("dispatching_slots") or []) == []
        assert brand._progress()["phase"] == "logos"
        saved = [str(row.get("prompt") or "") for row in ((brand._grant_of(2) or {}).get("slots") or [])]
        assert saved and all(row.startswith("logo a") for row in saved)
        assert all("mutated after binding" not in row for row in saved)
    finally:
        BOT_CHAT_ID.reset(token)


async def test_grant_expired_at_dispatch_does_not_submit(monkeypatch):
    """The grant is still valid at the pre-bind check and expired before submit."""
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID

    armed = {"jump": False}
    real_clock = brand._clock
    real_block = brand.submit_block_reason

    def clock():
        now = real_clock()
        return now + 700 if armed["jump"] else now

    def block(args, turn=None, now=None):
        result = real_block(args, turn, now=now)
        armed["jump"] = True
        return result

    monkeypatch.setattr(brand, "_clock", clock)
    monkeypatch.setattr(brand, "submit_block_reason", block)
    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        rig, events, confirms, submits = await _brand_turn(monkeypatch, _logo_a_script, threshold=0.5)
        texts = "\n".join(_tool_texts(events, "generate_image"))
        assert confirms
        assert rig.paid_mcp() == []
        assert submits == []
        assert "报价已过期" in texts
        assert brand.submitted_slots(2) == set()
        assert list((brand._stage_record(2) or {}).get("dispatching_slots") or []) == []
        assert brand._progress()["phase"] == "logos"
    finally:
        BOT_CHAT_ID.reset(token)


async def test_confirmed_logo_a_submits_once_and_is_recorded(monkeypatch):
    """A normal confirmed default logo_a still submits once and records the slot."""
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        rig, _events, confirms, submits = await _brand_turn(monkeypatch, _logo_a_script, threshold=0.5)
        gens = [args for _name, args in rig.paid_mcp()]
        assert confirms
        assert submits == []
        assert len(gens) == 1
        assert gens[0].get("brand_slot") == "logo_a"
        assert str(gens[0].get("prompt") or "").startswith("logo a")
        assert brand.submitted_slots(2) == {"logo_a"}
        assert brand._progress()["phase"] == "logos"
    finally:
        BOT_CHAT_ID.reset(token)


async def test_changed_template_prompt_does_not_submit(monkeypatch):
    """A skill preset whose prompt is not the confirmed one does not submit."""
    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from test_agent_budget_391 import calls, reply

    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()

        def script(messages, n):
            if n == 0:
                return calls(("generate_image", {
                    "prompt": "one direction",
                    "skill": brand.SKILL,
                    "preset": "geometric",
                }))
            return calls(("generate_image", {
                "prompt": "changed after confirm",
                "skill": brand.SKILL,
                "preset": "geometric",
            }))

        rig, events, confirms, submits = await _brand_turn(
            monkeypatch, script, threshold=0.5, answers=["start", "cancel"])
        prompts = [str(args.get("prompt") or "") for _name, args in rig.paid_mcp()]
        texts = "\n".join(_tool_texts(events, "generate_image"))
        assert confirms
        assert submits == []
        assert any(p.startswith("one direction") for p in prompts)
        assert not any("changed after confirm" in p for p in prompts)
        assert "参数已变化" in texts or len(confirms) >= 2
        assert brand.submitted_slots(2) == set()
    finally:
        BOT_CHAT_ID.reset(token)


def test_failed_generate_row_renders_the_tool_error_sentence():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    chat = (root / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    css = (root / "src/styles/overlays.css").read_text(encoding="utf-8")
    assert "function toolErrorLine" in chat
    assert 'data-testid="process-row-error"' in chat
    assert "ca-process__errtext" in css


def _png(draw) -> bytes:
    img = Image.new("RGB", (96, 96), (236, 228, 214))
    draw(img)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _quote_the_default_total():
    """The confirmed default path is 3 + 9 + 12 = 24 credits, stored as 0.24 USD."""
    brand.note_confirmed(0.03, 1, stage=1)
    brand.note_confirmed(0.09, 3, stage=2)
    brand.note_confirmed(0.12, 4, stage=3)
    assert brand._progress()["spent"] == 0.24


def _submit_slot(slot: str) -> dict:
    args = {"skill": brand.SKILL, "brand_slot": slot, "prompt": slot}
    brand.note_brand_submitted(args)
    brand.record_submitted(args, {"ids": [f"h-{slot}"]})
    return args


def test_full_frame_noise_is_void_and_a_reviewable_sheet_is_kept():
    import random
    rng = random.Random(7)

    def noise(img: Image.Image):
        px = img.load()
        for y in range(img.size[1]):
            for x in range(img.size[0]):
                px[x, y] = (rng.randrange(256), rng.randrange(256), rng.randrange(256))

    def sheet(img: Image.Image):
        px = img.load()
        for y in range(20, 76):
            for x in range(12, 84):
                px[x, y] = (92, 64, 48)

    noise_png = _png(noise)
    sheet_png = _png(sheet)
    assert brand.image_is_full_frame_noise(noise_png)
    assert not brand.image_is_full_frame_noise(sheet_png)
    assert not brand.image_is_full_frame_noise(b"")
    reviewable = {
        "status": "done", "shapes": ["shape:spec"], "urls": ["/spec.png"],
        "generation_succeeded": True,
    }
    assert brand.delivery_void_reason(reviewable, image=sheet_png) == ""
    assert brand.delivery_void_reason(reviewable, image=noise_png) == "noise"
    assert brand.delivery_void_reason({"status": "running", "shapes": [], "urls": []}) == ""
    assert brand.delivery_void_reason({
        "status": "error", "error": "generation failed", "shapes": ["shape:bad"], "urls": ["/bad.png"],
        "generation_succeeded": False,
    }) == "explicit_failure"
    assert brand.delivery_void_reason({"status": "done", "shapes": [], "urls": []}) == "empty"


def test_failed_image_is_not_a_deliverable_and_retries_once_only_when_uncharged():
    """A failed canvas image is dropped. One silent retry keeps the confirmed 24.

    A charged failure is not retried. It has to be quoted again, and the ledger says which.
    """
    _quote_the_default_total()
    _submit_slot("spec")
    brand.record_wait({"results": [{
        "id": "h-spec", "status": "error", "error": "generation failed",
        "shapes": ["shape:noise"], "urls": ["/noise.png"],
        "generation_succeeded": False, "charged": False,
    }]})
    progress = brand._progress()
    assert "spec" not in (progress.get("shapes") or {})
    assert "spec" in progress["failed"]
    entry = progress["delivery_ledger"][-1]
    assert entry["reason"] == "explicit_failure"
    assert entry["retry"] is True and entry["requote"] is False
    assert entry["charged"] is False and entry["quote_kept"] is True
    assert "spec" not in brand.submitted_slots(3)
    assert progress["spent"] == 0.24
    assert brand.submit_block_reason({"brand_slot": "spec", "skill": brand.SKILL}) != "requote"

    _submit_slot("cup")
    brand.record_wait({"results": [{
        "id": "h-cup", "status": "error", "error": "The task finished but returned no image, and it may have been charged about $0.12.",
        "shapes": ["shape:cup"], "urls": ["/cup.png"],
        "generation_succeeded": False, "charged": True, "charged_usd": 0.12,
    }]})
    progress = brand._progress()
    assert "cup" not in (progress.get("shapes") or {})
    charged = progress["delivery_ledger"][-1]
    assert charged["retry"] is False and charged["requote"] is True and charged["charged"] is True
    assert "cup" in brand.submitted_slots(3)
    assert brand.submit_block_reason({"brand_slot": "cup", "skill": brand.SKILL}) == "requote"
    assert "重新取价" in brand.submit_block_text("requote", "zh")
    assert progress["spent"] == 0.24

    _submit_slot("bag")
    brand.record_wait({"results": [{
        "id": "h-bag", "status": "error", "error": "charge refunded",
        "shapes": ["shape:bag"], "generation_succeeded": False,
        "charged": True, "refunded": True,
    }]})
    refunded = brand._progress()["delivery_ledger"][-1]
    assert refunded["retry"] is True and refunded["requote"] is False and refunded["refunded"] is True
    assert "bag" not in brand.submitted_slots(3)
    assert brand._progress()["spent"] == 0.24

    brand.record_submitted({"skill": brand.SKILL, "brand_slot": "spec"}, {"ids": ["h-spec-2"]})
    brand.note_brand_submitted({"skill": brand.SKILL, "brand_slot": "spec"})
    brand.record_wait({"results": [{
        "id": "h-spec-2", "status": "done", "shapes": [], "urls": [], "charged": False,
    }]})
    second = brand._progress()["delivery_ledger"][-1]
    assert second["slot"] == "spec" and second["attempt"] == 2
    assert second["retry"] is False and second["requote"] is True
    assert brand._progress()["spent"] == 0.24

    _submit_slot("storefront")
    brand.record_wait({"results": [{
        "id": "h-storefront", "status": "done", "shapes": ["shape:store"],
        "urls": ["/store.png"], "generation_succeeded": True,
    }]})
    assert brand._progress()["shapes"]["storefront"] == "shape:store"
    assert "storefront" not in brand._progress()["failed"]


def test_a_confirmed_requote_lets_the_slot_submit_once():
    """A charged failure stays blocked until note_confirmed records the new quote.

    The new stage amount replaces the old one. Spent stays 3+9+12, and the slot
    can be submitted once under that confirmation.
    """
    _quote_the_default_total()
    args = _submit_slot("spec")
    brand.record_wait({"results": [{
        "id": "h-spec", "status": "error", "error": "generation failed",
        "shapes": ["shape:bad"], "generation_succeeded": False,
        "charged": True, "charged_usd": 0.12, "refunded": False,
    }]})
    assert brand.submit_block_reason(args) == "requote"
    assert "spec" in brand._progress()["failed"]
    assert brand._progress()["spent"] == 0.24
    # Still blocked until the new quote is confirmed.
    assert brand.submit_block_reason(args) == "requote"
    brand.note_confirmed(0.12, 4, stage=3)
    assert brand._progress()["spent"] == 0.24
    assert "spec" not in brand._progress()["failed"]
    settled = [row for row in brand._progress()["delivery_ledger"] if row.get("slot") == "spec"][-1]
    assert settled["requote"] is False and settled["settled"] is True
    assert brand._delivery_block("spec") is None
    assert brand.submit_block_reason(args) != "requote"
    assert "spec" not in brand.submitted_slots(3)
    brand.note_brand_submitted(args)
    assert "spec" in brand.submitted_slots(3)
    assert brand.submit_block_reason(args) == "submitted"
    assert brand._progress()["spent"] == 0.24


def test_raw_noise_text_without_a_charged_flag_is_not_a_free_retry():
    """The completed-noise sentence is a charge even when the flag was left off.

    An explicit charged or refunded field still wins, and the confirmed 24 stays put.
    """
    from ComfyArt.api import wavespeed

    _quote_the_default_total()
    _submit_slot("spec")
    brand.record_wait({"results": [{
        "id": "h-spec", "status": "error",
        "error": "full-frame noise is not a deliverable",
        "shapes": ["shape:noise"], "generation_succeeded": False,
    }]})
    entry = brand._progress()["delivery_ledger"][-1]
    assert entry["charged"] is True
    assert entry["retry"] is False and entry["requote"] is True
    assert brand.submit_block_reason({"skill": brand.SKILL, "brand_slot": "spec"}) == "requote"
    assert "may have been charged" not in entry["reason"]
    assert brand._progress()["spent"] == 0.24

    _submit_slot("cup")
    brand.record_wait({"results": [{
        "id": "h-cup", "status": "error",
        "error": "full-frame noise is not a deliverable",
        "shapes": ["shape:cup"], "generation_succeeded": False,
        "charged": True, "charged_usd": 0.03, "refunded": False,
    }]})
    flagged = brand._progress()["delivery_ledger"][-1]
    assert flagged["retry"] is False and flagged["requote"] is True and flagged["charged"] is True

    _submit_slot("bag")
    brand.record_wait({"results": [{
        "id": "h-bag", "status": "error", "error": "generation failed",
        "generation_succeeded": False, "charged": False, "refunded": False,
    }]})
    free = brand._progress()["delivery_ledger"][-1]
    assert free["retry"] is True and free["requote"] is False
    assert brand._progress()["spent"] == 0.24

    _submit_slot("storefront")
    brand.record_wait({"results": [{
        "id": "h-storefront", "status": "error", "error": "full-frame noise is not a deliverable",
        "generation_succeeded": False, "charged": True, "refunded": True,
    }]})
    refunded = brand._progress()["delivery_ledger"][-1]
    assert refunded["retry"] is True and refunded["requote"] is False and refunded["refunded"] is True
    assert brand._progress()["spent"] == 0.24

    stamped = wavespeed.stamp_wait_charge(
        {"ws:task-1": {"status": {"messages": [["execution_error", {
            "exception_message": "full-frame noise is not a deliverable",
        }]]}}},
        "task-1", 0.12, refunded=False,
    )
    payload = stamped["ws:task-1"]
    assert payload["charged"] is True and payload["refunded"] is False
    assert payload["charged_usd"] == 0.12
    info = payload["status"]["messages"][0][1]
    assert info["charged"] is True and info["refunded"] is False and info["charged_usd"] == 0.12
    source = open("api/wavespeed.py", encoding="utf-8").read()
    noise_at = source.index("full-frame noise is not a deliverable")
    assert source.index("stamp_wait_charge(", noise_at) > noise_at


def test_submitted_prompts_put_the_gold_commands_before_the_lock():
    """The command sits in the submitted body, immediately before the lock.

    The preface still leads the spec, the lock is still last, and the runtime
    line is still the final line. A second fill is the same bytes.
    """
    slots = {
        "moodboard": "暖木棕 + 米白",
        "logo_a": "方向A",
        "logo_b": "方向B",
        "logo_c": "方向C",
        "spec": "规范",
        "cup": "杯",
        "bag": "袋",
        "storefront": "门头",
    }
    expected = {
        "moodboard": "write the confirmed direction as the annotation",
        "logo_a": "rounded-square icon, a circular stamp, and a solid square badge",
        "logo_b": "The main seal is a circular stamp filled with the confirmed accent or its dark color.",
        "logo_c": "not a wood-grain brown plaque",
        "spec": "never a full-frame noise field",
        "cup": "the thin stripe on the sleeve is the confirmed accent",
        "bag": "down the side gusset, not only across the front face",
        "storefront": "nor a hue invented outside that confirmed direction",
    }
    for slot, caller in slots.items():
        filled = brand.fill_default({"brand_slot": slot, "prompt": caller})["prompt"]
        again = brand.fill_default({"brand_slot": slot, "prompt": filled})["prompt"]
        assert again == filled, slot
        lead = brand._slot_command(slot)
        lock = brand._spec_lock() if slot == "spec" else brand._SLOT_LOCK[slot]
        assert lead in filled, slot
        assert filled.index(caller) < filled.index(lead) < filled.index(lock), slot
        if slot == "spec":
            assert filled.startswith("Draw seven separate panels")
            assert filled.rstrip().endswith(brand._spec_assembly_line())
            assert filled.count("exactly 7 panels") == 1
            assert filled.count("Draw seven separate panels") == 1
        else:
            assert filled.startswith(caller), slot
        if slot == "logo_c":
            assert filled.count("cup-shaped") == 1
            assert "not a row of app icons" in filled
            assert "do not draw it again inside the small-size set" in filled
        assert expected[slot] in filled
        assert lead not in lock
        assert lead not in brand._SPEC_PREFACE
        assert lead not in brand.default_hint()
