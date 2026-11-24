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


def teardown_function():
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
    c = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C STRUCTURE LOCK C"})
    assert "single-line" in a["prompt"]
    assert "circular seal" in b["prompt"]
    assert "cup-shaped" in c["prompt"]
    assert "single-line" not in b["prompt"]
    assert "perched bird is the negative space inside the cup" in c["prompt"]
    assert "bird standing on a branch" in c["prompt"]
    assert c["model"] == brand.QWEN_T2I
    assert c["size_candidates"] == [brand.QWEN_T2I]
    assert "edit_model" not in c
    for board in (a, b, c):
        assert "STRUCTURE LOCK" not in board["prompt"]
        assert "GUIDELINE LOCK" not in board["prompt"]
        assert "LAYOUT LOCK" not in board["prompt"]
        assert "APPLICATION LOCK" not in board["prompt"]
        assert "主组合, 符号构造, 横版, 小尺寸" in board["prompt"]
        assert "exactly once" in board["prompt"]
        assert "No other small text." in board["prompt"]
        assert "No bottom caption." in board["prompt"]
        assert "Do not print an English instruction label." in board["prompt"]
        assert "Each of the four zone labels appears exactly once." in board["prompt"]
        assert "No empty placeholder box" in board["prompt"] and "no X box" in board["prompt"]
        assert "小尺寸 includes the symbol" in board["prompt"]
    spec = brand.fill_default({"brand_slot": "spec", "prompt": "规范 GUIDELINE LOCK"})
    assert "exactly seven sections" in spec["prompt"]
    assert "Seven sections, not eight cells." in spec["prompt"]
    assert "标识, 色彩, 变体, 字体, 版式, 使用禁忌, 影像与材质" in spec["prompt"]
    assert "变体 is one full-width band and appears once." in spec["prompt"]
    assert "Do not draw a second 变体 section." in spec["prompt"]
    assert "The 字体 heading is the two characters 字体." in spec["prompt"]
    assert "Do not clip that heading to 字." in spec["prompt"]
    assert "No heading is repeated" in spec["prompt"] and "版式 appears once" in spec["prompt"]
    assert "版式 is one filled layout diagram" in spec["prompt"]
    assert "moodboard 色彩 cell" in spec["prompt"]
    assert "Chinese color name, and a percentage" in spec["prompt"]
    assert "character for character" in spec["prompt"]
    assert "Do not drop a character" in spec["prompt"]
    assert "red X" in spec["prompt"]
    assert "the mark in those brand colors only" in spec["prompt"]
    for caption in brand._MISUSE_CAPTIONS + brand._IMAGE_CAPTIONS:
        assert caption in spec["prompt"]
    assert "do not print a bare percent sign" in spec["prompt"]
    assert "do not print Latin fragments" in spec["prompt"]
    assert "GUIDELINE LOCK" not in spec["prompt"]
    assert "STRUCTURE LOCK" not in spec["prompt"]
    assert "title, subtitle" not in spec["prompt"]
    assert "最小尺寸" not in spec["prompt"]
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
    assert "Chinese brand name AND the English brand name" in cup["prompt"]
    assert "must wear a cup sleeve" in cup["prompt"] and "杯套" in cup["prompt"]
    assert "A bare cup with no sleeve is wrong." in cup["prompt"]
    again = brand.fill_default({"brand_slot": "logo_a", "prompt": a["prompt"]})
    assert "STRUCTURE LOCK" not in again["prompt"]
    assert again["prompt"].count("one open single-line drawing") == 1
    assert "APPLICATION LOCK" not in cup["prompt"] and "APPLICATION LOCK" not in store["prompt"]
    leaked = brand.fill_default({
        "brand_slot": "logo_c",
        "prompt": "bottom caption STRUCTURE LOCK C: keep the cup",
    })
    assert "STRUCTURE LOCK" not in leaked["prompt"]
    assert "keep the cup" in leaked["prompt"]
    assert leaked["prompt"].count("cup-shaped") == 1


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
    assert "Seven sections, not eight cells." in skill
    assert "never clipped to 字" in skill
    assert "cup sleeve" in skill
    assert "不要拉伸或压缩标识比例" in skill
    assert "自然柔光，干净高光不压暗" in skill
    assert "STRUCTURE LOCK" not in skill
    assert "标识, 色彩, 变体, 字体, 版式, 使用禁忌, 影像与材质" in skill
    assert "#" not in skill
    hint = brand.default_hint()
    assert "矢量替换" in hint and "色值为屏幕估算" in hint
    assert "Seven sections, not eight cells." in hint
    assert "Do not clip that heading to 字." in hint
    assert "不要拉伸或压缩标识比例" in hint
    assert "自然柔光，干净高光不压暗" in hint
    assert "STRUCTURE LOCK" not in hint
    assert "#" not in hint


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


async def _brand_turn(monkeypatch, script):
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
    confirms: list = []
    rig = Rig(monkeypatch, script)
    monkeypatch.setattr(rig.p, "_run_policy", lambda: resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"}))

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
    _res, events = await rig.send("做三个方向", goal="", handle=TurnHandle())
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
                return calls(("quote_plan", {"steps": _three_logos()}))
            return reply("好")

        await _brand_turn(monkeypatch, first_script)
        assert brand._progress()["spent"] == 0.09

        changed = [
            _logo_plan(
                slot, width=1024, height=1024, edit_model="other-model",
                prompt=f"changed prompt {slot}", base=f"http://127.0.0.1/base-{slot}.png",
            )
            for slot in ("logo_a", "logo_b", "logo_c")
        ] + [_logo_plan(
            "logo_a", width=1024, height=1024, edit_model="other-model",
            prompt="changed prompt logo_a extra", base="http://127.0.0.1/base-logo_a.png",
        )]
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


def _quoted_generate(slot: str):
    """The generate that repeats the confirmed quote arguments, not a new prompt."""
    step = next(item for item in _short_logo_steps() if item["arguments"]["brand_slot"] == slot)
    return ("generate_image", dict(step["arguments"]))


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


async def test_short_quote_then_long_generates_submit_once_each(monkeypatch):
    """Quote once, then submit each slot with those same arguments."""
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
        # The remaining two slots are a new price, so the old grant is not reused.
        assert len(confirms) == 1
        assert [row["slot"] for row in confirms[0]["frozen_slots"]] == ["logo_b", "logo_c"]
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


def test_failed_generate_row_renders_the_tool_error_sentence():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    chat = (root / "src/ui/ChatMessage.tsx").read_text(encoding="utf-8")
    css = (root / "src/styles/overlays.css").read_text(encoding="utf-8")
    assert "function toolErrorLine" in chat
    assert 'data-testid="process-row-error"' in chat
    assert "ca-process__errtext" in css
