"""Dense-typography edits with reference images prefer the configured edit model.

The model id lives in api/auto_models.json (image_edit.dense_typography). The
router does not branch on a skill id. A ratio the skill filled is not an exact
pixel request, so the Qwen exact-size pin does not override this route. Pixels
the user themselves named still take that pin. Quote and submit use one pick.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from ComfyArt.api.auto_models import load_table, registered_runtime_fallback, short_name, table_runtime_fallback_choice
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID
from ComfyArt.api.mcp_tools.canvas import SPECS, quote_route, select_model
from ComfyArt.api.skill_size import RATIO_MODE
from ComfyArt.api.wavespeed import load_config
from ComfyArt.bot.guide import AGENT_GUIDE, IMAGE_PROMPT_RULES
from ComfyArt.bot.plan_quote import build_quote
from ComfyArt.bot.skill_output import OUTPUTS, apply_generate

GPT = "openai/gpt-image-2/edit"
FALLBACK = "google/nano-banana-pro/edit"
QWEN_EDIT = "wavespeed-ai/qwen-image-2.0/edit"
QWEN_T2I = "wavespeed-ai/qwen-image-2.0/text-to-image"
BRAND = "brand-identity-director"
PACKAGING = "product-to-packaging"
SHEET = "a brand guideline sheet with packed labels and dense typography"
USER = "做一张品牌规范卡"


def _row() -> dict:
    return load_table()["image_edit"]["dense_typography"]


def _route(args: dict, user_text: str = "") -> dict:
    prepared = apply_generate(dict(args), str(args.get("skill") or ""), user_text=user_text)
    choice = select_model("generate_image", prepared, user_text=user_text) or {}
    return choice


def test_config_names_the_model_and_its_fallback():
    row = _row()
    assert row["model"] == GPT
    assert row["fallback"] == FALLBACK


@pytest.mark.parametrize("skill", [BRAND, PACKAGING, "not-a-real-skill", ""])
def test_dense_typography_edit_with_refs_routes_to_the_configured_model(skill):
    """The same rule for every skill. The skill argument is not a branch."""
    args = {"prompt": SHEET, "refs": ["shape:logo", "shape:board"], "ratio": "16:9",
            "width": 2048, "height": 1152}
    if skill:
        args["skill"] = skill
    choice = _route(args, USER)
    assert choice.get("category") == "dense_typography"
    assert choice.get("edit_model") == _row()["model"] == GPT
    assert choice.get("model") == GPT
    assert "qwen" not in choice["model"]


def test_without_refs_is_not_forced_onto_this_model():
    choice = _route({"prompt": SHEET, "skill": BRAND, "ratio": "16:9"}, USER)
    assert choice.get("model") != GPT
    assert choice.get("edit_model") != GPT
    assert choice.get("category") != "dense_typography"


def test_without_dense_typography_is_not_forced_onto_this_model():
    plain = _route({"prompt": "a red cup on a wooden table", "refs": ["shape:a"],
                    "skill": BRAND, "ratio": "1:1"}, "画一个杯子")
    assert plain.get("model") != GPT and plain.get("category") != "dense_typography"
    # A pinned skill keeps its pin when the text is not dense typography.
    pinned = skill_pin_edit()
    kept = select_model("generate_image", {
        "prompt": "a kraft box on a white table", "refs": ["shape:a"],
        "skill": PACKAGING, "ratio": "3:4",
    }, user_text="做一张包装图")
    assert kept["model"] == pinned
    assert kept["model"] != GPT


def test_a_negated_guideline_is_not_dense_typography():
    choice = _route({
        "prompt": "a product photo, do not make a guideline sheet",
        "refs": ["shape:a"], "skill": BRAND,
    }, "不要规范卡，只要产品照片")
    assert choice.get("category") != "dense_typography"
    assert choice.get("model") != GPT


def test_pixels_copied_into_the_prompt_do_not_pin_qwen():
    """2048x1152 in the prompt and on the call is the skill table, not the user."""
    args = {"prompt": "guideline sheet at 2048x1152", "refs": ["shape:a"],
            "skill": BRAND, "ratio": "16:9", "width": 2048, "height": 1152}
    prepared = apply_generate(dict(args), BRAND, user_text=USER)
    assert "exact_size_pin" not in prepared
    assert prepared.get("model") != QWEN_T2I and prepared.get("edit_model") != QWEN_EDIT
    assert prepared.get("size_lock_mode") == RATIO_MODE
    choice = select_model("generate_image", prepared, user_text=USER)
    assert choice["edit_model"] == GPT


def test_explicit_user_pixels_keep_the_exact_size_pin():
    models = OUTPUTS[BRAND]["exact_size_models"]
    prepared = apply_generate(
        {"prompt": SHEET, "refs": ["shape:a"], "skill": BRAND, "ratio": "16:9"},
        BRAND, user_text="规范卡请按 1584x396 像素",
    )
    assert prepared["exact_size_pin"] is True
    assert prepared["edit_model"] == models["edit"] == QWEN_EDIT
    assert (prepared["width"], prepared["height"]) == (1584, 396)
    assert prepared.get("size_lock_mode") != RATIO_MODE
    choice = select_model("generate_image", prepared, user_text="规范卡请按 1584x396 像素")
    assert choice["category"] == "skill_size"
    assert choice["model"] == QWEN_EDIT
    quoted, _inputs = quote_route("generate_image", prepared, user_text="规范卡请按 1584x396 像素")
    assert quoted == QWEN_EDIT
    t2i = apply_generate(
        {"prompt": "a poster", "skill": BRAND, "ratio": "1:1"},
        BRAND, user_text="请输出 1024x1024",
    )
    assert t2i["exact_size_pin"] is True and t2i["model"] == OUTPUTS[BRAND]["exact_size_models"]["t2i"]
    assert select_model("generate_image", t2i, user_text="请输出 1024x1024")["model"] == t2i["model"]


def skill_pin_edit() -> str:
    from ComfyArt.api.auto_models import skill_pin
    return skill_pin(PACKAGING)["edit_model"]


def test_registered_fallback_is_nano_banana_pro_edit():
    choice = _route({"prompt": SHEET, "refs": ["shape:a"], "skill": "poster-workshop"}, USER)
    ids = {m["id"] for m in load_config()["features"]["image_edit"]["models"]}
    assert registered_runtime_fallback("image_edit", choice, ids) == FALLBACK
    failed = table_runtime_fallback_choice("image_edit", choice, GPT, ids)
    assert failed and failed["model"] == FALLBACK and failed.get("edit_model") is None
    # The submit path marks an edit fallback with edit_model. The row is what it reads.
    assert failed["fallback"] == GPT


async def _no_models(_feature):
    return []


async def test_quote_card_matches_the_routed_model_and_price():
    args = {"prompt": SHEET, "refs": ["shape:logo"], "skill": BRAND, "ratio": "16:9",
            "width": 2048, "height": 1152}
    prepared = apply_generate(dict(args), BRAND, user_text=USER)
    routed, inputs = quote_route("generate_image", prepared, user_text=USER)
    submit = select_model("generate_image", prepared, user_text=USER)
    assert routed == GPT
    assert (submit.get("edit_model") or submit.get("model")) == routed
    assert "exact_size_pin" not in prepared

    prices = {GPT: 0.07, QWEN_EDIT: 0.03, QWEN_T2I: 0.03}

    async def pricer(model, _inputs):
        return (prices.get(model, 0.01), "quote", "test")

    quote = await build_quote(
        [{"text": "规范卡", "tool": "generate_image", "model": "", "arguments": prepared}],
        "zh", threshold=0.0, pricer=pricer, models_for=_no_models, router=quote_route)
    assert quote is not None and len(quote.lines) == 1
    line = quote.lines[0]
    assert line.amount == prices[GPT]
    assert line.amount != prices[QWEN_EDIT]
    assert short_name(GPT) in line.text
    assert short_name(QWEN_EDIT) not in line.text
    # The quote inputs are the same call the submit prices (refs counted, ratio kept).
    assert inputs["images"] == ["ref-1"] and inputs.get("ratio") == prepared["ratio"]


def test_submit_uses_the_same_model_the_quote_priced(monkeypatch):
    sent: list[dict] = []

    async def submit(action, args, project, timeout, chat=""):
        sent.append(dict(args))
        return {"ids": ["holder"], "model": args.get("edit_model") or args.get("model")}

    async def no_approval(_label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)
    chat = f"dense-{uuid.uuid4().hex}"
    guard = GUARD_CHAT_ID.set(chat)
    bot = BOT_CHAT_ID.set(chat)
    try:
        args = {"prompt": SHEET, "refs": ["shape:logo"], "skill": PACKAGING, "ratio": "3:4"}
        prepared = apply_generate(dict(args), PACKAGING, user_text=USER)
        routed, _inputs = quote_route("generate_image", prepared, user_text=USER)
        asyncio.run(canvas.TOOLS["generate_image"]["handler"](args))
    finally:
        BOT_CHAT_ID.reset(bot)
        GUARD_CHAT_ID.reset(guard)
    assert len(sent) == 1
    body = sent[0]
    assert body.get("edit_model") == routed == GPT
    assert body.get("model") != QWEN_T2I
    assert body.get("size_lock_mode") == RATIO_MODE
    assert "exact_size_pin" not in body


def test_image_instructions_do_not_invent_color_dates_or_the_title_language():
    for text in (IMAGE_PROMPT_RULES, AGENT_GUIDE, SPECS["generate_image"]["description"]):
        assert "Do not invent hex or other color values when none were provided." in text
        assert "标志 / LOGO" in text
        assert "Do not invent dates or other facts that were not provided." in text
    # These lines are the shared prompt, not a brand brief or a lock.
    assert "STRUCTURE LOCK" not in IMAGE_PROMPT_RULES
    assert "brand-identity" not in IMAGE_PROMPT_RULES
