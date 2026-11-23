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
    assert "质感" in mood["prompt"] and "数字" in mood["prompt"]
    a = brand.fill_default({"brand_slot": "logo_a", "prompt": "方向A"})
    b = brand.fill_default({"brand_slot": "logo_b", "prompt": "方向B"})
    c = brand.fill_default({"brand_slot": "logo_c", "prompt": "方向C"})
    assert "STRUCTURE LOCK A" in a["prompt"] and "single-line" in a["prompt"]
    assert "STRUCTURE LOCK B" in b["prompt"] and "circular seal" in b["prompt"]
    assert "STRUCTURE LOCK C" in c["prompt"] and "cup-shaped" in c["prompt"]
    assert "single-line" not in b["prompt"]
    assert "bird standing on a branch" in c["prompt"]
    spec = brand.fill_default({"brand_slot": "spec", "prompt": "规范"})
    cup = brand.fill_default({"brand_slot": "cup", "prompt": "杯"})
    assert "使用禁忌" in spec["prompt"] and "最小尺寸" in spec["prompt"]
    assert "Chinese brand name AND the English brand name" in cup["prompt"]
    assert "sleeve" in cup["prompt"] and "杯套" in cup["prompt"]
    assert "No bottom caption." in a["prompt"] and "No bottom caption." in b["prompt"] and "No bottom caption." in c["prompt"]
    again = brand.fill_default({"brand_slot": "logo_a", "prompt": a["prompt"]})
    assert again["prompt"].count("STRUCTURE LOCK A") == 1


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
    assert "矢量替换" in text and "色值为屏幕估算" in text
    assert "可直接投产" in text and "Never say" in text


def test_fallback_copy_does_not_name_one_brand():
    spec = _card1()
    blob = __import__("json").dumps(spec, ensure_ascii=False)
    assert "栖木" not in blob and "QIMU" not in blob and "枝桠" not in blob
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
        "杯子外形，符号是杯中的负空间",
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
        ("杯形负空间", "杯子外形，符号是杯中的负空间"),
    ]
    blob = __import__("json").dumps(card, ensure_ascii=False)
    assert "手刻印章" not in blob
    assert opts[0]["recommended"] is True
    assert [o.get("image_url") for o in opts] == ["/a.png", "/b.png", "/c.png"]
    assert "defaults" not in card["questions"][0]
    en = brand.normalize_card({"questions": [{
        "id": "bi_direction",
        "prompt": "Which logo direction should be the final mark (logo_primary)?",
        "options": [{"id": "A", "label": "Hand seal", "recommended": True},
                    {"id": "B", "label": "B"}, {"id": "C", "label": "C"}],
    }]}, "en")
    en_opts = en["questions"][0]["options"]
    assert [o["label"] for o in en_opts] == [
        "Single-line bird on a branch",
        "Wooden signboard and round seal",
        "Cup-shaped negative space",
    ]
    assert "bird perched on a branch" in en_opts[0]["description"]
    assert "round seal" in en_opts[1]["description"]
    assert "negative space" in en_opts[2]["description"]
    assert en_opts[0]["recommended"] is True


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
