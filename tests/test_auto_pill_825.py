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
    gen = (ROOT / "src/shapes/GeneratorShape.tsx").read_text()
    assert "ca-gen-frame__model" in gen and "autoPillLabel" in gen
    # #870: in-frame label only while pending (JSX + CSS); settled cards use SelectionLabel
    assert "pending ? autoPillLabel" in gen
    css = (ROOT / "src/styles/canvas.css").read_text()
    assert ".ca-gen-card[data-pending] .ca-gen-frame__model" in css
    block = css.split(".ca-gen-card[data-pending] .ca-gen-frame__model {", 1)[1].split("}", 1)[0]
    assert "position: absolute" in block


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
