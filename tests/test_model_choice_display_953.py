"""#953: task history and quote-card copy must not say「你指定了这个模型」
unless the user themselves named the model.

Four cases, each checked on the model_choice record (task-history pill) and
on the quote-card wording: agent-filled, Auto, skill-fixed, user-named.
Selection (the model that will run) is unchanged when the user names a model.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ComfyArt.api import auto_models, wavespeed
from ComfyArt.api.auto_models import (
    USER_NAMED_REASON,
    is_user_named_reason,
    pill_label,
    pill_tooltip,
    quote_model_copy,
)
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.skill_size import VERIFIED
from ComfyArt.bot.plan_quote import build_quote


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
QWEN = VERIFIED["text_to_image"]
QWEN_EDIT = VERIFIED["image_edit"]
USER_TEXT_NO_MODEL = "帮我做个前后对比，暗疮和肉色不均"
USER_TEXT_NAMED = "请用 Qwen Image 2.0 做前后对比"


def _before_after(*, model: str | None = None, refs: bool = True) -> dict:
    args = {
        "prompt": "beauty before after comparison card",
        "skill": "before-after",
        "width": 1024,
        "height": 1280,
        "ratio": "4:5",
    }
    if refs:
        args["refs"] = ["shape:ref"]
    if model:
        args["model"] = model
    return args


def _choice(args, user_text: str = USER_TEXT_NO_MODEL):
    return canvas.select_model(
        "generate_image", dict(args), catalog=FIXTURE, cfg=wavespeed.load_config(),
        user_text=user_text,
    )


def _pill_and_quote(choice: dict, lang: str = "zh") -> tuple[str | None, str | None, str]:
    label = pill_label(choice)
    tip = pill_tooltip(choice, lang)
    copy = quote_model_copy(choice, str(choice.get("model") or ""), lang)
    return label, tip, copy


def test_agent_filled_model_keeps_model_but_not_user_named_copy():
    """Agent passed a model id; the user did not name one. Model stays; copy is skill/Auto."""
    args = _before_after(model=QWEN_EDIT)
    choice = _choice(args, USER_TEXT_NO_MODEL)
    assert choice and not choice.get("block"), choice
    assert choice["model"] == QWEN_EDIT  # selection unchanged
    assert choice["auto"] is True
    assert choice.get("category") != "user"
    assert not is_user_named_reason(choice.get("reason"))
    assert "你指定了这个模型" not in (choice["reason"].get("zh") or "")
    assert "you named this model" not in (choice["reason"].get("en") or "")
    assert "before-after" in (choice["reason"].get("zh") or "")
    label, tip, copy = _pill_and_quote(choice, "zh")
    assert label and label.startswith("Auto ·")
    assert tip and "你指定了这个模型" not in tip
    assert "before-after" in tip or "before-after" in copy
    assert "你指定了这个模型" not in copy
    en_copy = quote_model_copy(choice, QWEN_EDIT, "en")
    assert "you named this model" not in en_copy


def test_auto_path_uses_auto_copy():
    """No skill pin and no named model: Auto copy on the pill and the quote card."""
    args = {"prompt": "a cup of coffee on a table"}
    choice = _choice(args, "来一张咖啡桌面")
    assert choice and choice["auto"] is True
    assert choice.get("category") != "user"
    assert not is_user_named_reason(choice.get("reason"))
    label, tip, copy = _pill_and_quote(choice, "zh")
    assert label and label.startswith("Auto ·")
    assert tip and tip.startswith("自动选择")
    assert "你指定了这个模型" not in (tip or "") and "你指定了这个模型" not in copy
    en_tip = pill_tooltip(choice, "en")
    assert en_tip and en_tip.startswith("Auto-picked")
    assert "you named this model" not in (en_tip or "")


def test_skill_fixed_before_after_uses_skill_size_copy():
    """before-after Auto path is skill_size; task history and quote card use that reason."""
    args = _before_after(model=None)
    choice = _choice(args, USER_TEXT_NO_MODEL)
    assert choice and not choice.get("block"), choice
    assert choice["auto"] is True
    assert choice["category"] == "skill_size"
    assert choice.get("skill") == "before-after"
    assert not is_user_named_reason(choice.get("reason"))
    assert "before-after" in choice["reason"]["zh"] and "1024" in choice["reason"]["zh"]
    label, tip, copy = _pill_and_quote(choice, "zh")
    assert label and label.startswith("Auto ·")
    assert tip and "before-after" in tip and "你指定了这个模型" not in tip
    assert "before-after" in copy and "你指定了这个模型" not in copy
    # #825: skill tooltip has no 自动选择 prefix
    assert not tip.startswith("自动选择")


def test_user_named_model_keeps_user_reason_and_wins():
    """The user named the model in their message: keep「你指定了这个模型」and that model."""
    args = _before_after(model=QWEN_EDIT)
    choice = _choice(args, USER_TEXT_NAMED)
    assert choice and not choice.get("block"), choice
    assert choice["model"] == QWEN_EDIT
    assert choice["auto"] is False
    assert choice["category"] == "user"
    assert is_user_named_reason(choice.get("reason"))
    label, tip, copy = _pill_and_quote(choice, "zh")
    # #825: manual pick shows the name only, no Auto prefix and no reason popup
    assert label and not label.startswith("Auto")
    assert tip is None
    assert "你指定了这个模型" not in copy
    assert "Auto ·" not in copy


async def test_quote_card_copy_for_the_four_cases():
    """Quote-card line text follows the same four-way wording (no user-named sentence on the card)."""

    async def pricer(model, inputs):
        return 0.05

    async def no_models(feature):
        return []

    async def quote_for(args, lang, user_text):
        # Stamp user_text onto the turn via select_model; build_quote reads select_model.
        # For exact-size skills, pass catalog through a wrapper router that only prices.
        def router(tool, arguments):
            choice = canvas.select_model(
                tool, dict(arguments), catalog=FIXTURE, cfg=wavespeed.load_config(),
                user_text=user_text,
            ) or {}
            model = str(choice.get("edit_model") or choice.get("model") or "")
            if not model:
                return None
            payload = {k: v for k, v in choice.items() if k != "_exact_args"}
            return model, {"_model_choice": payload}

        return await build_quote(
            [{"text": "前后对比", "tool": "generate_image", "model": "", "arguments": args}],
            lang, threshold=0.0, pricer=pricer, models_for=no_models, router=router,
        )

    agent = await quote_for(_before_after(model=QWEN_EDIT), "zh", USER_TEXT_NO_MODEL)
    assert agent and "你指定了这个模型" not in agent.lines[0].text
    assert "Auto ·" in agent.lines[0].text
    assert "before-after" in agent.lines[0].text

    auto = await quote_for({"prompt": "a cup of coffee on a table"}, "zh", "来一张咖啡")
    assert auto and "你指定了这个模型" not in auto.lines[0].text
    assert "Auto ·" in auto.lines[0].text

    skill = await quote_for(_before_after(model=None), "zh", USER_TEXT_NO_MODEL)
    assert skill and "你指定了这个模型" not in skill.lines[0].text
    assert "Auto ·" in skill.lines[0].text and "before-after" in skill.lines[0].text

    named = await quote_for(_before_after(model=QWEN_EDIT), "zh", USER_TEXT_NAMED)
    assert named and "你指定了这个模型" not in named.lines[0].text
    assert "Auto ·" not in named.lines[0].text


def test_resolve_model_choice_keeps_incoming_skill_size_reason():
    """Estimate/submit must not overwrite a skill_size record with the user-named reason."""
    incoming = {
        "model": QWEN_EDIT,
        "auto": True,
        "category": "skill_size",
        "skill": "before-after",
        "reason": {
            "zh": "before-after 需要 1024×1280，" + QWEN_EDIT + " 的 size 字段能按这个宽高提交",
            "en": "before-after needs 1024×1280, and this model accepts that exact size",
        },
    }
    model, choice = wavespeed.resolve_model_choice(
        "image_edit",
        {"model": QWEN_EDIT, "feature": "image_edit", "size_lock": True, "model_choice": incoming},
    )
    assert model == QWEN_EDIT
    assert choice and choice["auto"] is True
    assert choice["category"] == "skill_size"
    assert not is_user_named_reason(choice.get("reason"))


def test_resolve_model_choice_auto_model_flag_is_not_user_named():
    model, choice = wavespeed.resolve_model_choice(
        "image_edit",
        {"model": QWEN_EDIT, "feature": "image_edit", "auto_model": True, "size_lock": True,
         "skill": "before-after"},
    )
    assert model == QWEN_EDIT
    assert choice and choice["auto"] is True
    assert not is_user_named_reason(choice.get("reason"))


def test_studio_manual_pick_without_skill_still_user_named():
    """A studio / tool pick with no skill and no auto_model stays the #825 user-named record."""
    default = wavespeed.load_config()["features"]["text_to_image"]["default"]
    model, choice = wavespeed.resolve_model_choice(
        "text_to_image", {"model": default, "prompt": "a poster"},
    )
    assert model == default
    assert choice and choice["auto"] is False
    assert choice["reason"] == USER_NAMED_REASON


def test_frontend_does_not_invent_user_named_reason_for_a_skill_input():
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert "skillPinReason(skill)" in chat
    assert "#953" in chat
    gen = (ROOT / "src/generate.ts").read_text()
    assert "attachModelChoice" in gen and "applyModelChoice" in gen
    panel = (ROOT / "src/ui/GenPanel.tsx").read_text()
    assert "clobber" in panel and "#953" in panel


def test_mutation_dropping_relabel_would_mark_agent_fill_as_user_named(monkeypatch):
    """Must-red: if relabel_agent_filled_choice is a no-op, agent-filled before-after
    is once again recorded as「你指定了这个模型」."""
    monkeypatch.setattr(auto_models, "relabel_agent_filled_choice", lambda choice, *a, **k: choice)
    monkeypatch.setattr(canvas, "relabel_agent_filled_choice", lambda choice, *a, **k: choice)
    choice = _choice(_before_after(model=QWEN_EDIT), USER_TEXT_NO_MODEL)
    assert is_user_named_reason((choice or {}).get("reason")), choice
    # The four-case test above would fail under this monkeypatch (reason is user-named).
    assert (choice or {}).get("auto") is False
