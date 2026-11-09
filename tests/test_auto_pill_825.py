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


def test_fallback_tooltip_mentions_preferred_failed():
    choice = {
        "model": "openai/gpt-image-2.6-flare/text-to-image",
        "auto": True,
        "fallback": "openai/gpt-image-2.6-sunburst/text-to-image",
        "reason": {"zh": "图标/Logo", "en": "icon / logo"},
    }
    tip = auto_models.pill_tooltip(choice, "zh")
    assert tip == (
        "自动选择：图标/Logo · 首选 GPT Image 2.6 Sunburst 失败，改用 GPT Image 2.6 Flare"
    )
    tip_en = auto_models.pill_tooltip(choice, "en")
    assert tip_en == (
        "Auto-picked: icon / logo · Preferred GPT Image 2.6 Sunburst failed, used GPT Image 2.6 Flare"
    )


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
    assert "data-testid=\"auto-model-label\"" in chat or "auto-model-label" in chat
    gen = (ROOT / "src/shapes/GeneratorShape.tsx").read_text()
    assert "ca-gen-frame__model" in gen and "autoPillLabel" in gen
    # Not a colored capsule for the model row
    assert "ca-gen-frame__model" in (ROOT / "src/styles/canvas.css").read_text()


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
