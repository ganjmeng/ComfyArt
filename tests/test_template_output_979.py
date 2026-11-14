"""#979 — template-level output contracts (product ruling #911 comment 6872615903).

The deliverable is per TEMPLATE, not per skill:
  brand-identity-director: 3×1024×1024 (1:1) direction proposals, then (after the
  user picks one) 1×2048×1152 (16:9) guideline board — 4 images total, two stages.
  packaging-design-director: t1 1×1536×2048 (3:4); t2 3×2048×1152 (16:9);
  t3 4 images (3×1536×2048 + 1×2048×1152); t4/t5 1×2048×1152 (16:9).

The same two existing tables carry the plan: src/skills.ts `SKILL_OUTPUT` (read by the
agent) and bot/skill_output.py `OUTPUTS` (server fill), with `run_hint` stating the plan
and `apply_generate` filling it when the model omits width/height/ratio. No second table.
"""
from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from ComfyArt.bot.skill_output import (
    OUTPUTS, PRESET_PLAN_SKILLS, apply_generate, is_single, plan_for,
    preset_from_text, run_hint, single_image_skip,
)

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists(),
    reason="needs node + node_modules",
)
BRAND = "brand-identity-director"
PACKAGING = "packaging-design-director"

# Product ruling, written as literals on purpose: reverting a table row to its old
# value (brand 1×16:9, packaging 1×1024×1024, t2 1×3:4, t3 1 image, ...) makes these red.
PACKAGING_EXPECTED = {
    "eco": {"images": 1, "calls": [(1536, 2048, "3:4")]},
    "gold": {"images": 3, "calls": [(2048, 1152, "16:9")] * 3},
    "playful": {"images": 4, "calls": [(1536, 2048, "3:4")] * 3 + [(2048, 1152, "16:9")]},
    "panels": {"images": 1, "calls": [(2048, 1152, "16:9")]},
    "shelf": {"images": 1, "calls": [(2048, 1152, "16:9")]},
}
BRAND_STAGE_CALLS = {
    1: [(1024, 1024, "1:1")] * 3,
    2: [(2048, 1152, "16:9")],
}


@lru_cache(maxsize=1)
def js_report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"output979-{os.getpid()}.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/preset978/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "../output979/main.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True,
                                    text=True, timeout=60).stdout)


def call_args(sid: str, preset: str = "", stage: object = 1, **extra) -> dict:
    """One model call that omitted width/height/ratio/count, like the mock e2e does."""
    args = {"skill": sid, "prompt": "a distinct direction"}
    if preset:
        args["preset"] = preset
    if stage != 1:
        args["stage"] = stage
    args.update(extra)
    return apply_generate(args, sid)


def test_templates_are_declared_in_the_existing_tables():
    assert PRESET_PLAN_SKILLS == {BRAND, PACKAGING}
    assert set((OUTPUTS[BRAND]["presets"] or {})) == {
        "geometric", "handmade", "tech", "beauty", "foodbev", "pet"}
    assert set((OUTPUTS[PACKAGING]["presets"] or {})) == {"eco", "gold", "playful", "panels", "shelf"}
    # Flat row = the skill's default template, never a square 1024 placeholder.
    assert (OUTPUTS[PACKAGING]["width"], OUTPUTS[PACKAGING]["height"],
            OUTPUTS[PACKAGING]["ratio"], OUTPUTS[PACKAGING]["images"]) == (1536, 2048, "3:4", 1)
    assert (OUTPUTS[BRAND]["width"], OUTPUTS[BRAND]["height"],
            OUTPUTS[BRAND]["ratio"], OUTPUTS[BRAND]["images"]) == (1024, 1024, "1:1", 4)


@needs_node
def test_ts_and_python_tables_agree_row_by_row():
    js = js_report()["skillOutput"]
    assert set(js) == set(OUTPUTS)
    for sid, row in OUTPUTS.items():
        got = js[sid]
        for key in ("width", "height", "images"):
            assert got[key] == row[key], (sid, key, got, row)
        assert got.get("ratio") == row.get("ratio"), (sid, "ratio", got, row)
        assert set(got.get("presets") or {}) == set(row.get("presets") or {}), sid
        for pid, plan in (row.get("presets") or {}).items():
            ts_plan = got["presets"][pid]
            if plan.get("stages"):
                assert ts_plan["stages"] == [
                    {k: s[k] for k in ("width", "height", "ratio", "images")} for s in plan["stages"]], (sid, pid)
            else:
                for key in ("width", "height", "ratio", "images"):
                    assert ts_plan.get(key) == plan.get(key), (sid, pid, key)


@needs_node
def test_template_ids_are_the_ones_the_page_actually_has():
    """The table keys must be the real template ids from applyRaw748, not invented ones."""
    ids = js_report()["presets"]
    assert [p["id"] for p in ids["packaging"]] == list(PACKAGING_EXPECTED)
    assert [p["id"] for p in ids["brand"]] == list(OUTPUTS[BRAND]["presets"])


def test_brand_is_three_proposals_then_one_guideline_board():
    for pid in OUTPUTS[BRAND]["presets"]:
        stage1 = plan_for(BRAND, pid, 1)
        stage2 = plan_for(BRAND, pid, 2)
        assert (stage1["width"], stage1["height"], stage1["ratio"], stage1["images"]) == (1024, 1024, "1:1", 3)
        assert (stage2["width"], stage2["height"], stage2["ratio"], stage2["images"]) == (2048, 1152, "16:9", 1)
        assert stage1["total_images"] == stage2["total_images"] == 4
        # Not the old "single landscape board" shape.
        assert not (stage1["images"] == 1 and stage1["width"] == 2048)


def test_packaging_five_templates_five_plans():
    for pid, want in PACKAGING_EXPECTED.items():
        plan = plan_for(PACKAGING, pid, 1)
        first = want["calls"][0]
        assert (plan["width"], plan["height"], plan["ratio"]) == first[:3], pid
        assert plan["total_images"] == want["images"], pid
        if pid == "playful":
            assert [s["images"] for s in plan["stages"]] == [3, 1]
            last = plan_for(PACKAGING, pid, 2)
            assert (last["width"], last["height"], last["ratio"], last["images"]) == (2048, 1152, "16:9", 1)


def test_apply_generate_fills_each_template_with_omitted_sizes():
    for pid, want in PACKAGING_EXPECTED.items():
        got = [call_args(PACKAGING, pid, stage=(2 if pid == "playful" and i == 3 else 1))
               for i in range(len(want["calls"]))]
        assert [(a["width"], a["height"], a["ratio"]) for a in got] == want["calls"], pid
        assert [a["count"] for a in got] == [1] * len(want["calls"]), pid
        assert all(a["size_lock"] is True for a in got), pid
        # A relay re-applies the function with the same args: it must not drift.
        again = [apply_generate(dict(a)) for a in got]
        assert [(a["width"], a["height"], a["ratio"], a["preset"], a["stage"]) for a in again] == \
            [(a["width"], a["height"], a["ratio"], a["preset"], a["stage"]) for a in got], pid


def test_apply_generate_fills_brand_stage_one_then_stage_two():
    for pid in OUTPUTS[BRAND]["presets"]:
        stage1 = [call_args(BRAND, pid) for _ in range(3)]
        assert [(a["width"], a["height"], a["ratio"], a["stage"]) for a in stage1] == \
            [(1024, 1024, "1:1", 1)] * 3, pid
        stage2 = apply_generate({"skill": BRAND, "preset": pid, "stage": 2}, BRAND)
        assert (stage2["width"], stage2["height"], stage2["ratio"]) == (2048, 1152, "16:9"), pid
        assert stage2["stage"] == 2 and stage2["count"] == 1 and stage2["size_lock"] is True


def test_a_stage_size_given_without_stage_is_honored():
    """The lock names each stage's size; a model that passes those pixels instead of stage=N still lands."""
    range_shot = apply_generate({"skill": PACKAGING, "preset": "playful",
                                 "width": 2048, "height": 1152, "prompt": "range"})
    assert (range_shot["width"], range_shot["height"], range_shot["ratio"], range_shot["stage"]) == \
        (2048, 1152, "16:9", 2)
    sku = apply_generate({"skill": PACKAGING, "preset": "playful",
                          "width": 1536, "height": 2048, "prompt": "sku"})
    assert (sku["width"], sku["height"], sku["stage"]) == (1536, 2048, 1)
    board = apply_generate({"skill": BRAND, "preset": "tech",
                            "width": 2048, "height": 1152, "prompt": "board"})
    assert (board["width"], board["height"], board["stage"]) == (2048, 1152, 2)
    # A made-up size is not a stage; the template's stage 1 still wins.
    wrong = apply_generate({"skill": PACKAGING, "preset": "playful",
                            "width": 1024, "height": 1024, "prompt": "x"})
    assert (wrong["width"], wrong["height"], wrong["stage"]) == (1536, 2048, 1)


def test_unselected_and_unknown_template_use_the_skill_default_and_say_so():
    # No template: packaging runs the default 主款 (eco), 1×1536×2048, not 1024×1024.
    bare = apply_generate({"skill": PACKAGING, "prompt": "pack shot"})
    assert (bare["width"], bare["height"], bare["ratio"], bare["count"]) == (1536, 2048, "3:4", 1)
    assert bare["preset"] == "eco"
    unknown = apply_generate({"skill": PACKAGING, "preset": "not-a-template", "prompt": "pack shot"})
    assert (unknown["width"], unknown["height"], unknown["preset"]) == (1536, 2048, "eco")
    hint = run_hint(PACKAGING, "做包装")
    assert "skill default template" in hint and "template=eco" in hint
    # Brand with no/unknown template still runs the staged plan, never one landscape board.
    for preset in ("", "nope"):
        hint = run_hint(BRAND, "", preset_id=preset)
        assert "template=geometric" in hint and "skill default template" in hint
        assert "3 separate images" in hint and "2048" in hint and "16:9" in hint
        stage2 = apply_generate({"skill": BRAND, "stage": 2}, BRAND)
        assert (stage2["width"], stage2["height"]) == (2048, 1152)
        assert stage2["preset"] == "geometric"


def test_run_hint_states_each_templates_count_and_size():
    for pid, want in PACKAGING_EXPECTED.items():
        hint = run_hint(PACKAGING, "", preset_id=pid)
        assert preset_from_text(hint) == pid, hint
        assert f"template={pid}" in hint
        first = want["calls"][0]
        assert f"width={first[0]}" in hint and f"height={first[1]}" in hint and f"ratio={first[2]}" in hint
        assert f"exactly {want['images']} separate images" in hint or (
            want["images"] == 1 and "exactly once" in hint), pid
    playful = run_hint(PACKAGING, "", preset_id="playful")
    assert "stage 2" in playful and "4 separate images" in playful and "2048" in playful
    brand = run_hint(BRAND, "", preset_id="tech")
    assert "NOT one landscape board" in brand
    assert "3 separate images" in brand and "width=1024 height=1024 ratio=1:1" in brand
    assert "width=2048 height=1152 ratio=16:9" in brand
    assert "never a 5th" in brand and "stage=2" in brand


def test_uploaded_reference_does_not_override_the_template_size():
    """#693: the upload is optional. An upload is not a ratio request; only the user's words are."""
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1024, 1280), (200, 180, 160)).save(buf, format="PNG")
    ref = buf.getvalue()
    gold = apply_generate({"skill": PACKAGING, "preset": "gold", "refs": ["shape:ref"], "prompt": "x"},
                          PACKAGING, user_text="做三张方向板", ref_image=ref)
    assert (gold["width"], gold["height"], gold["ratio"]) == (2048, 1152, "16:9")
    brand = apply_generate({"skill": BRAND, "preset": "tech", "refs": ["shape:ref"], "prompt": "x"},
                           BRAND, user_text="做方向提案", ref_image=ref)
    assert (brand["width"], brand["height"], brand["ratio"]) == (1024, 1024, "1:1")
    # #905 before-after still follows the reference card when the user names no ratio.
    from ComfyArt.bot.skill_output import apply_generate as ag
    ba = ag({"skill": "before-after", "refs": ["shape:ref"], "prompt": "x"}, "before-after",
            user_text="做前后对比", ref_image=ref)
    assert (ba["width"], ba["height"], ba["ratio"]) == (1024, 1280, "4:5")


def test_user_ratio_still_wins_over_the_template_default():
    # #905: a template default is a default. The user naming a ratio overrides size, not count.
    gold = apply_generate({"skill": PACKAGING, "preset": "gold", "prompt": "3 boards"},
                          PACKAGING, user_text="做成 3:4 的三张方向板")
    assert (gold["width"], gold["height"], gold["ratio"]) == (1536, 2048, "3:4")
    playful = [apply_generate({"skill": PACKAGING, "preset": "playful", "stage": s,
                               "prompt": "x"}, PACKAGING, user_text="全部用 1:1 方图")
               for s in (1, 1, 1, 2)]
    assert [(a["width"], a["height"], a["ratio"]) for a in playful] == [(1536, 1536, "1:1")] * 4
    brand = apply_generate({"skill": BRAND, "preset": "tech", "stage": 1, "prompt": "x"},
                           BRAND, user_text="规范板要横版 16:9")
    assert (brand["width"], brand["height"], brand["ratio"]) == (2048, 1152, "16:9")
    # The hint also states the user's ratio, so the agent is not told the template default.
    hint = run_hint(PACKAGING, "做成 3:4 的三张方向板", preset_id="gold")
    assert "user named ratio 3:4" in hint and "width=1536 height=2048" in hint


def test_single_image_skip_is_template_aware_not_skill_aware():
    assert single_image_skip("generate_image", PACKAGING, "en", 1) and \
        single_image_skip("generate_image", PACKAGING, "en", 1, "eco")
    for pid in ("gold", "playful"):
        for generated in (1, 2, 3):
            assert single_image_skip("generate_image", PACKAGING, "en", generated, pid) is None, pid
    for generated in (1, 2, 3):
        assert single_image_skip("generate_image", BRAND, "en", generated) is None
    assert is_single(PACKAGING) is True  # default template is 主款
    assert is_single(PACKAGING, "gold") is False and is_single(PACKAGING, "playful") is False
    assert is_single(BRAND, "tech") is False


def test_compose_carries_the_template_id_into_the_lock():
    from ComfyArt.api.bot_send import compose_provider_text, parse_preset_id
    assert parse_preset_id({"id": " gold ", "prompt": "x"}) == "gold"
    assert parse_preset_id({"prompt": "x"}) == "" and parse_preset_id(None) == ""
    provider = compose_provider_text("做包装", skill_name=PACKAGING, preset_prompt="模板正文", preset_id="gold")
    assert "Selected template instructions" in provider
    assert "template=gold" in provider
    assert preset_from_text(provider) == "gold"


def test_template_lock_ratios_are_not_read_as_user_intent():
    """#978/HOLD: the hint names 1:1/16:9, but only the user's own words may pick a ratio."""
    from ComfyArt.api.bot_send import compose_provider_text
    from ComfyArt.bot.skill_output import user_ratio
    for sid, preset, want in ((BRAND, "geometric", (1024, 1024)),
                              (PACKAGING, "gold", (2048, 1152)),
                              (PACKAGING, "playful", (1536, 2048))):
        provider = compose_provider_text("按模板做", skill_name=sid, preset_prompt="模板正文", preset_id=preset)
        assert "1:1" in provider or "16:9" in provider
        assert user_ratio(sid, provider) is None, (sid, preset, provider)
        args = apply_generate({"skill": sid, "prompt": "x"}, sid, user_text=provider)
        # the template's stage-1 size still applies, not one of the hint's other stage ratios
        assert (args["width"], args["height"]) == want, args
    # The same provider text with the user naming a ratio still follows the user.
    provider = compose_provider_text("做成 4:5", skill_name=PACKAGING, preset_prompt="模板正文", preset_id="gold")
    assert user_ratio(PACKAGING, provider) == "4:5"


def test_template_prompts_and_plans_agree():
    """Changing a feed prompt's count/ratio without its plan (or the reverse) fails here."""
    copy = json.loads((ROOT / "src/data/copy-748.json").read_text(encoding="utf-8"))
    pkg = copy[PACKAGING]["templates"]
    assert "生成 1 张包装主视面确认稿" in pkg["1"]["prompt"]["zh"]
    assert plan_for(PACKAGING, "eco")["images"] == 1
    assert "生成 3 张 16:9 包装方向板" in pkg["2"]["prompt"]["zh"]
    assert plan_for(PACKAGING, "gold")["images"] == 3 and plan_for(PACKAGING, "gold")["ratio"] == "16:9"
    t3 = pkg["3"]["prompt"]["zh"]
    assert "生成 3 个 SKU 的包装图各 1 张" in t3 and "共 4 张" in t3
    assert plan_for(PACKAGING, "playful")["total_images"] == 4
    assert [s["images"] for s in plan_for(PACKAGING, "playful")["stages"]] == [3, 1]
    assert "生成 1 张包装概念面板" in pkg["4"]["prompt"]["zh"]
    assert plan_for(PACKAGING, "panels")["images"] == 1
    assert "生成 1 张货架陈列图" in pkg["5"]["prompt"]["zh"]
    assert plan_for(PACKAGING, "shelf")["images"] == 1
    brand = copy[BRAND]["templates"]
    for key in ("1", "2", "3", "4", "5", "6"):
        text = brand[key]["prompt"]["zh"]
        assert "生成 3 张标志方向提案" in text and "再生成 1 张标志规范板" in text, key
    # Every template prompt's count matches the plan; no prompt promises a different total.
    for pid in OUTPUTS[BRAND]["presets"]:
        assert plan_for(BRAND, pid, 1)["images"] == 3
        assert plan_for(BRAND, pid, 2)["images"] == 1


def test_legacy_rows_are_unchanged():
    for sid, row in OUTPUTS.items():
        if sid in PRESET_PLAN_SKILLS:
            continue
        assert "presets" not in row and "stages" not in row, sid
        # The five #707/#974 rows plus clothing-swap keep their product-locked values.
        if sid == "linkedin-banner":
            assert (row["width"], row["height"], row["images"]) == (1584, 396, 1)
        else:
            assert row.get("ratio") and row["images"] >= 1, sid
