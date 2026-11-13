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
        {"model": QWEN_EDIT, "feature": "image_edit", "size_lock": True, "model_choice": incoming,
         "auto_model": True},
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
    assert "choiceMatchesCurrent" in gen
    # #953 QA HOLD: the cached record only counts for the model this job runs, and a pure
    # Auto record on a manual card must not self-corroborate as Auto.
    assert "autoProvenance" in gen and "skillRouted" in gen
    assert "typeof current !== 'string'" in gen
    panel = (ROOT / "src/ui/GenPanel.tsx").read_text()
    # A model-menu pick / Auto off overwrites the stale Auto record with a manual one;
    # Auto on drops it so the estimate derives Auto again.
    assert "manualModelChoice" in panel
    assert "choiceAfter" in panel
    assert "modelChoice: on ? null" in panel
    assert "modelChoice: choiceAfter(" in panel
    pill = (ROOT / "src/autoPill.ts").read_text()
    assert "export function manualModelChoice" in pill
    assert "auto: false" in pill


def test_mutation_dropping_relabel_would_mark_agent_fill_as_user_named(monkeypatch):
    """Must-red: if relabel_agent_filled_choice is a no-op, agent-filled before-after
    is once again recorded as「你指定了这个模型」."""
    monkeypatch.setattr(auto_models, "relabel_agent_filled_choice", lambda choice, *a, **k: choice)
    monkeypatch.setattr(canvas, "relabel_agent_filled_choice", lambda choice, *a, **k: choice)
    choice = _choice(_before_after(model=QWEN_EDIT), USER_TEXT_NO_MODEL)
    assert is_user_named_reason((choice or {}).get("reason")), choice
    # The four-case test above would fail under this monkeypatch (reason is user-named).
    assert (choice or {}).get("auto") is False


def test_plain_agent_filled_model_without_skill_is_not_a_user_pick():
    """Agent passed only a model id; the user did not name one and there is no skill."""
    flare = "openai/gpt-image-2.6-flare/text-to-image"
    args = {"prompt": "a cup of coffee", "model": flare}
    choice = _choice(args, "来一张咖啡桌面，模型你来选")
    assert choice["model"] == flare
    assert choice["auto"] is True
    assert not is_user_named_reason(choice.get("reason"))


def test_stale_display_metadata_must_not_override_submitted_model():
    """A leftover Auto model_choice must not replace the model the user just picked."""
    cfg = wavespeed.load_config()
    default = cfg["features"]["text_to_image"]["default"]
    alternate = next(
        m["id"] for m in cfg["features"]["text_to_image"]["models"]
        if m["id"] != default and "text-to-image" in m["id"]
    )
    incoming = {
        "model": default, "auto": True, "category": "default",
        "reason": {"zh": "自动选择", "en": "Auto picked it"},
    }
    base, _ = wavespeed.resolve_model_choice(
        "text_to_image", {"model": alternate, "prompt": "a poster"},
    )
    actual, choice = wavespeed.resolve_model_choice(
        "text_to_image",
        {"model": alternate, "prompt": "a poster", "model_choice": incoming, "auto_model": True},
    )
    assert actual == base == alternate
    assert choice and choice["model"] == alternate
    assert actual != default


def test_manual_pick_of_the_same_model_after_auto_is_manual():
    """#953 QA HOLD: Studio Auto estimate (Flare) → Auto off → user picks the same Flare id.

    The id is unchanged, so an id-only staleness check keeps the old Auto source. The
    source must follow the user's action: manual, no Auto reason, same submitted model.
    """
    flare = "openai/gpt-image-2.6-flare/text-to-image"
    stale_auto = {
        "model": flare, "auto": True, "category": "default",
        "reason": {"zh": "这是通用生图的默认模型", "en": "the default model for general image generation"},
    }
    manual = {"model": flare, "auto": False, "category": "user",
              "reason": {"zh": "你指定了这个模型", "en": "you named this model"}}
    # 1) the fixed page drops the stale record; the explicit model alone is a manual pick
    model, choice = wavespeed.resolve_model_choice(
        "text_to_image", {"model": flare, "prompt": "a cup of coffee on a table"})
    assert model == flare
    assert choice and choice["auto"] is False
    assert choice.get("category") == "user"
    assert is_user_named_reason(choice.get("reason"))
    # 2) a manual record for the same id survives as manual
    model2, choice2 = wavespeed.resolve_model_choice(
        "text_to_image",
        {"model": flare, "prompt": "a cup of coffee on a table", "model_choice": manual})
    assert model2 == flare
    assert choice2 and choice2["auto"] is False
    assert choice2.get("model") == flare
    assert is_user_named_reason(choice2.get("reason"))
    # 3) stale Auto display metadata without the caller's Auto flag must not self-corroborate:
    #    the model stays Flare and the source is the manual pick (this is the failure QA held).
    model3, choice3 = wavespeed.resolve_model_choice(
        "text_to_image",
        {"model": flare, "prompt": "a cup of coffee on a table", "model_choice": stale_auto})
    assert model3 == flare
    assert choice3 and choice3["auto"] is False
    assert choice3.get("category") == "user"
    assert is_user_named_reason(choice3.get("reason"))
    # 4) an Auto record is still valid when the caller says Auto routed it (Agent / Auto card).
    model4, choice4 = wavespeed.resolve_model_choice(
        "text_to_image",
        {"model": flare, "prompt": "a cup of coffee on a table", "model_choice": stale_auto,
         "auto_model": True})
    assert model4 == flare
    assert choice4 and choice4["auto"] is True


def test_generic_endpoint_word_is_not_a_user_named_model():
    mid = "openai/gpt-image-2.6-flare/text-to-image"
    assert not auto_models.user_named_this_model(mid, "做一张 text-to-image 海报，模型你来定")
    assert auto_models.user_named_this_model(QWEN_EDIT, "请用 Qwen Image 2.0 做图")


def test_quote_route_uses_cached_catalog_for_before_after(monkeypatch):
    """Real quote_route (no test-only router) must see the catalog and not invent 'you named'."""
    prev_models = wavespeed._catalog.get("models")
    prev_at = wavespeed._catalog.get("at")
    prev_stale = wavespeed._catalog.get("stale", None)
    wavespeed._catalog.update({"at": 1e18, "models": FIXTURE})
    wavespeed._catalog.pop("stale", None)
    monkeypatch.setattr(canvas, "_current_user_text", lambda: USER_TEXT_NO_MODEL)
    try:
        routed = canvas.quote_route("generate_image", _before_after(model=QWEN_EDIT))
        assert routed, "quote_route returned None"
        model, payload = routed
        choice = payload.get("_model_choice") or {}
        assert model == QWEN_EDIT
        assert choice.get("category") == "skill_size"
        assert choice.get("auto") is True
        assert not is_user_named_reason(choice.get("reason"))
        copy = quote_model_copy(choice, model, "en")
        assert "you named" not in copy.lower()
        assert "Auto ·" in copy
        assert "before-after" in copy or "1024" in copy
    finally:
        wavespeed._catalog["models"] = prev_models if prev_models is not None else {}
        wavespeed._catalog["at"] = prev_at if prev_at is not None else 0.0
        if prev_stale is None:
            wavespeed._catalog.pop("stale", None)
        else:
            wavespeed._catalog["stale"] = prev_stale
