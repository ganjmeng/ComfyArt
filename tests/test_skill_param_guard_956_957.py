"""#956 / #957: server validation of generate_image skill params. $0 mocks only.

Portrait-studio: missing skill or current shot is refused before submit.
When the current portrait task is still using an uploaded photo, omitting
refs/skill/shot together is also refused (no silent text-to-image).
Product-to-packaging that is using an uploaded product photo: missing refs is
refused before submit (no silent text-to-image). Applicability comes from the
current skill and answered cards, not from the agent-supplied skill alone.
Valid complete args still submit. Quotes use the validated actual parameters.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from ComfyArt.api import chat_store, paid_guard, portrait_studio as ps, product_packaging as pk
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.api import skill_param_guard as guard

PERSON = "/api/view?filename=person-956.png&type=input"
PRODUCT = "/api/view?filename=product-956.png&type=input"
PRODUCT_B = "/api/view?filename=product-b-956.png&type=input"

SENT: list = []


@pytest.fixture(autouse=True)
def _clean_turns():
    before = set(paid_guard.TURNS)
    locks_ps = dict(ps._LOCKS)
    locks_pk = dict(pk._LOCKS)
    yield
    for k in list(paid_guard.TURNS):
        if k not in before:
            paid_guard.TURNS.pop(k, None)
    ps._LOCKS.clear()
    ps._LOCKS.update(locks_ps)
    pk._LOCKS.clear()
    pk._LOCKS.update(locks_pk)


@pytest.fixture
def relay(monkeypatch):
    SENT.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args), chat))
        return {
            "ids": ["shape:gen956"],
            "submitted": True,
            "model": args.get("edit_model") or args.get("model") or "mock",
        }

    async def approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", approval)


def _chat(*, skill="", uploads=(), card="", answers=None, later_skill=""):
    chat = chat_store.create_chat(user="default", project="p956", provider="local-llm")
    blocks = []
    if skill:
        blocks.append({"type": "skill", "name": skill})
    for i, url in enumerate(uploads):
        blocks.append({"type": "image", "url": url, "shape": f"loose:{i}", "name": f"u{i}.png"})
    if blocks:
        blocks.append({"type": "text", "text": "start"})
        chat_store.create_message(chat_id=chat["id"], role="user", blocks=blocks)
    if card == "portrait":
        answers = answers or {
            "ps_shots": {"selected": ["A"]},
            "ps_outfit": {"selected": ["A"]},
            "ps_scene": {"selected": ["A"]},
        }
        chat_store.create_message(
            chat_id=chat["id"], role="assistant",
            blocks=[{
                "type": "ask", "status": "answered", "ask_id": "a-ps",
                "questions": ps.card_questions("zh"), "answers": answers,
            }],
        )
    elif card == "packaging":
        answers = answers or {
            "pk_product": {"selected": ["A"]},
            "pk_color": {"selected": ["A"]},
            "pk_scope": {"selected": ["A"]},
        }
        chat_store.create_message(
            chat_id=chat["id"], role="assistant",
            blocks=[{
                "type": "ask", "status": "answered", "ask_id": "a-pk",
                "questions": pk.card_questions(None, "zh"), "answers": answers,
            }],
        )
    if later_skill:
        chat_store.create_message(
            chat_id=chat["id"], role="user",
            blocks=[{"type": "skill", "name": later_skill}, {"type": "text", "text": "new task"}],
        )
    return chat


def _run(chat_id, args):
    token = BOT_CHAT_ID.set(chat_id)

    async def go():
        return await canvas.TOOLS["generate_image"]["handler"](dict(args))

    try:
        return asyncio.run(go())
    finally:
        BOT_CHAT_ID.reset(token)


def _refused(result, *missing):
    assert SENT == [], result
    assert result.get("submitted") is False
    assert result.get("generation_succeeded") is False
    assert result.get("charged") is False
    assert result.get("kind") == guard.KIND_MISSING
    got = result.get("missing") or []
    for name in missing:
        assert name in got, (name, result)
    assert result.get("error")
    assert result["error"] == result.get("user_message")
    return result


# --- context inference -----------------------------------------------------------------

def test_canonical_skill_accepts_localized_composer_names():
    assert guard.canonical_skill("portrait-studio") == "portrait-studio"
    assert guard.canonical_skill("摄影级人像生图工具") == "portrait-studio"
    assert guard.canonical_skill("Portrait Studio Generator") == "portrait-studio"
    assert guard.canonical_skill("product-to-packaging") == "product-to-packaging"
    assert guard.canonical_skill("产品到包装系统") == "product-to-packaging"
    assert guard.canonical_skill("Product-to-Packaging System") == "product-to-packaging"
    assert guard.canonical_skill("studio-model") == "studio-model"


def test_context_maps_localized_skill_chip_to_portrait(relay):
    chat = chat_store.create_chat(user="default", project="p956", provider="local-llm")
    chat_store.create_message(
        chat_id=chat["id"], role="user",
        blocks=[
            {"type": "skill", "name": "摄影级人像生图工具"},
            {"type": "image", "url": PERSON, "shape": "loose:0", "name": "p.png"},
            {"type": "text", "text": "帮我用这张照片做一组专业形象照。"},
        ],
    )
    ctx = guard.context_from_chat(chat["id"])
    assert ctx.skill == "portrait-studio" and ctx.portrait() is True
    result = _run(chat["id"], {"prompt": "portrait", "refs": [PERSON], "count": 1})
    _refused(result, "skill", "shot")


def test_context_uses_latest_skill_and_answered_cards_not_agent_skill():
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging",
                 later_skill="portrait-studio")
    # The later portrait start has no photo yet; uploads reset with the new skill.
    ctx = guard.context_from_chat(chat["id"])
    assert ctx.skill == "portrait-studio"
    assert ctx.portrait() is True
    assert ctx.packaging() is False
    assert ctx.packaging_uses_upload() is False

    chat2 = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    ctx2 = guard.context_from_chat(chat2["id"])
    assert ctx2.portrait() is True and ctx2.uploads == [PERSON]


# --- #957 portrait: missing skill / shot zero submit -----------------------------------

def test_portrait_missing_skill_is_refused_when_context_is_portrait(relay):
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {"prompt": "close-up portrait", "refs": [PERSON], "shot": "closeup", "count": 1})
    _refused(result, "skill")


def test_portrait_missing_shot_is_refused(relay):
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {
        "prompt": "close-up portrait", "skill": "portrait-studio", "refs": [PERSON], "count": 1,
    })
    _refused(result, "shot")


def test_portrait_invalid_shot_is_refused_not_guessed(relay):
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {
        "prompt": "portrait", "skill": "portrait-studio", "refs": [PERSON], "shot": "wide", "count": 1,
    })
    _refused(result, "shot")


def test_portrait_missing_skill_and_shot_refused_even_if_agent_omits_skill(relay):
    """The paid #927 failure: first generate_image dropped skill/shot. Context still applies."""
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {"prompt": "professional portrait", "refs": [PERSON], "count": 1})
    _refused(result, "skill", "shot")


def test_portrait_valid_args_submit_normally(relay):
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {
        "prompt": "face close-up, casual look, solid studio backdrop",
        "skill": "portrait-studio", "refs": [PERSON], "shot": "closeup", "count": 1,
    })
    assert SENT, result
    action, args, passed = SENT[0]
    assert action == "generate_image"
    assert args["refs"] == [PERSON]
    assert args.get("count", 1) == 1
    assert "shot" not in args  # popped after lock
    assert passed == chat["id"]
    assert result.get("submitted") is True
    assert result.get("ids") == ["shape:gen956"]


def test_portrait_user_passed_shot_is_not_overridden(relay):
    """Card A is closeup/half/three_quarter; an explicit full shot is kept, not replaced."""
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {
        "prompt": "full body as the user asked",
        "skill": "portrait-studio", "refs": [PERSON], "shot": "full", "count": 1,
    })
    assert SENT, result
    prompt = SENT[0][1]["prompt"]
    assert ps.SHOT_LINE["full"] in prompt
    assert ps.SHOT_LINE["closeup"] not in prompt


def test_portrait_all_omitted_with_upload_is_refused_not_silent_t2i(relay):
    """#957 P0: chip + answered card + upload still in play; agent sends only prompt+count."""
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {"prompt": "professional portrait set", "count": 1})
    _refused(result, "refs", "skill", "shot")
    assert SENT == []
    # Do not auto-fill the uploaded photo or a shot onto the refused result or a submit.
    assert not result.get("refs") and not result.get("shot")
    err = (result.get("error") or "") + (result.get("user_message") or "")
    assert "text-to-image" in err.lower() or "文生图" in err


def test_portrait_partial_omissions_with_upload_are_refused(relay):
    """Any incomplete combo while the uploaded photo is in use is zero-submit."""
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    cases = [
        ({"prompt": "p", "skill": "portrait-studio", "shot": "closeup", "count": 1}, ("refs",)),
        ({"prompt": "p", "skill": "portrait-studio", "count": 1}, ("refs", "shot")),
        ({"prompt": "p", "shot": "closeup", "count": 1}, ("refs", "skill")),
        ({"prompt": "p", "refs": [PERSON], "count": 1}, ("skill", "shot")),
        ({"prompt": "p", "skill": "portrait-studio", "refs": [PERSON], "count": 1}, ("shot",)),
        ({"prompt": "p", "shot": "half", "refs": [PERSON], "count": 1}, ("skill",)),
    ]
    for args, missing in cases:
        SENT.clear()
        _refused(_run(chat["id"], args), *missing)
        assert SENT == []


def test_portrait_all_omitted_does_not_auto_fill_photo_or_shot(relay):
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {"prompt": "professional portrait set", "count": 1})
    _refused(result, "refs", "skill", "shot")
    assert SENT == []
    # The historical upload must not be injected into a submit.
    assert all(not (a[1] or {}).get("refs") for a in SENT)


def test_explicit_new_t2i_task_is_not_blocked(relay):
    """User starts a separate text-to-image task; do not apply leftover portrait-upload rules."""
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait",
                 later_skill="studio-model")
    result = _run(chat["id"], {"prompt": "a poster from a text brief", "count": 1})
    assert result.get("kind") != guard.KIND_MISSING, result
    assert SENT, result
    SENT.clear()
    # Fresh chat, no portrait context: bare t2i is allowed.
    chat2 = _chat()
    result = _run(chat2["id"], {"prompt": "a cat on a windowsill", "count": 1})
    assert result.get("kind") != guard.KIND_MISSING, result
    assert SENT, result


def test_portrait_without_upload_all_omitted_is_not_this_guard(relay):
    """The expanded rule applies only when the current portrait run is using an upload."""
    chat = _chat(skill="portrait-studio", uploads=(), card="portrait")
    result = _run(chat["id"], {"prompt": "professional portrait set", "count": 1})
    assert result.get("kind") != guard.KIND_MISSING, result


# --- #956 packaging: missing refs zero submit, no t2i ----------------------------------

def test_packaging_missing_refs_refused_when_upload_is_in_use(relay):
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    result = _run(chat["id"], {
        "prompt": "package plus product hero", "skill": "product-to-packaging", "count": 1,
    })
    _refused(result, "refs")
    # Agent skill omitted: still refused from current skill + upload, not from args.skill.
    SENT.clear()
    result = _run(chat["id"], {"prompt": "package plus product hero", "count": 1})
    _refused(result, "refs")


def test_packaging_valid_refs_submit_normally(relay):
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    result = _run(chat["id"], {
        "prompt": "the package and the product together",
        "skill": "product-to-packaging", "refs": [PRODUCT], "count": 1,
    })
    assert SENT, result
    args = SENT[0][1]
    assert args["refs"] == [PRODUCT]
    assert args.get("ratio") == "3:4"
    assert args.get("count", 1) == 1
    assert result.get("submitted") is True


def test_packaging_does_not_auto_pick_historical_uploads(relay):
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    # Missing refs: refused; the historical upload is not injected.
    _refused(_run(chat["id"], {"prompt": "hero", "skill": "product-to-packaging", "count": 1}), "refs")
    assert all("refs" not in (a[1] or {}) or not a[1].get("refs") for a in SENT)


def test_packaging_explicit_refs_are_not_replaced_with_historical_upload(relay):
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    result = _run(chat["id"], {
        "prompt": "use the new product photo the user just named",
        "skill": "product-to-packaging", "refs": [PRODUCT_B], "count": 1,
    })
    assert SENT, result
    assert SENT[0][1]["refs"] == [PRODUCT_B]
    assert PRODUCT not in SENT[0][1]["refs"]


def test_packaging_multi_refs_keep_order(relay):
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT, PRODUCT_B], card="packaging")
    result = _run(chat["id"], {
        "prompt": "anchor", "skill": "product-to-packaging",
        "refs": [PRODUCT, PRODUCT_B], "count": 1,
    })
    assert SENT, result
    assert SENT[0][1]["refs"] == [PRODUCT, PRODUCT_B]


def test_packaging_without_upload_does_not_require_refs(relay):
    """Only when the run is explicitly using an uploaded product photo."""
    chat = _chat(skill="product-to-packaging", uploads=(), card="packaging")
    result = _run(chat["id"], {"prompt": "invent a box from a brief", "skill": "product-to-packaging", "count": 1})
    assert result.get("kind") != guard.KIND_MISSING, result
    assert SENT, result


# --- scope isolation and a later task --------------------------------------------------

def test_other_skills_are_not_subject_to_these_rules(relay):
    chat = _chat(skill="studio-model", uploads=[PERSON], card="")
    result = _run(chat["id"], {"prompt": "a studio look", "skill": "studio-model", "refs": [PERSON], "count": 1})
    assert result.get("kind") != guard.KIND_MISSING, result
    assert SENT, result
    SENT.clear()
    # No current special skill: omitting refs / shot is not this guard's refusal.
    chat2 = _chat()
    result = _run(chat2["id"], {"prompt": "a cat", "count": 1})
    assert result.get("kind") != guard.KIND_MISSING, result
    assert SENT, result


def test_agent_skill_alone_does_not_apply_packaging_refs_rule(relay):
    """A stray skill=product-to-packaging in some other (or empty) chat is not enough."""
    chat = _chat()
    result = _run(chat["id"], {"prompt": "a box", "skill": "product-to-packaging", "count": 1})
    assert result.get("kind") != guard.KIND_MISSING, result
    assert SENT, result


def test_same_chat_new_skill_drops_previous_packaging_rule(relay):
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging",
                 later_skill="studio-model")
    result = _run(chat["id"], {"prompt": "studio after the packaging task", "count": 1})
    assert result.get("kind") != guard.KIND_MISSING, result
    assert SENT, result


# --- quotes use validated actual parameters -------------------------------------------

def test_quote_route_blocks_missing_packaging_refs():
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    token = BOT_CHAT_ID.set(chat["id"])
    try:
        routed = canvas.quote_route("generate_image", {
            "prompt": "hero", "skill": "product-to-packaging", "count": 1,
        })
    finally:
        BOT_CHAT_ID.reset(token)
    assert routed is not None and routed[0] == ""
    assert (routed[1] or {}).get("param_blocked", {}).get("kind") == guard.KIND_MISSING
    assert "refs" in (routed[1] or {}).get("param_blocked", {}).get("missing", [])


def test_quote_route_uses_validated_lock_params_for_complete_args():
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    token = BOT_CHAT_ID.set(chat["id"])
    try:
        routed = canvas.quote_route("generate_image", {
            "prompt": "hero", "skill": "product-to-packaging", "refs": [PRODUCT], "count": 3,
        })
    finally:
        BOT_CHAT_ID.reset(token)
    assert routed and routed[0]
    model, inputs = routed
    assert inputs.get("ratio") == "3:4"
    assert inputs.get("images") == ["ref-1"]
    assert inputs.get("count") == 1
    assert "param_blocked" not in (inputs or {})


@pytest.mark.asyncio
async def test_build_quote_does_not_price_silent_t2i_when_refs_missing():
    from ComfyArt.bot.plan_quote import build_quote

    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    token = BOT_CHAT_ID.set(chat["id"])

    async def pricer(model, inputs):
        raise AssertionError(f"must not price a fallback call: {model} {inputs}")

    async def models_for(feature):
        raise AssertionError(f"must not fall back to dearest {feature}")

    try:
        quote = await build_quote(
            [{"tool": "generate_image", "text": "anchor",
              "arguments": {"prompt": "hero", "skill": "product-to-packaging", "count": 1}}],
            "zh", threshold=0.01, pricer=pricer, models_for=models_for, router=canvas.quote_route,
        )
    finally:
        BOT_CHAT_ID.reset(token)
    assert quote is not None
    assert quote.lines and quote.lines[0].amount == 0.0 and quote.lines[0].unpriced
    assert "refs" in quote.lines[0].text.lower() or "refs" in quote.lines[0].text


# --- mutations: dropping the hook must turn the refusal tests red ---------------------

def test_mutation_removing_preflight_would_submit_missing_params(relay, monkeypatch):
    """Must-red: if preflight is a no-op, the #927/#930 missing-param cases would submit."""
    monkeypatch.setattr(guard, "preflight", lambda *a, **k: None)
    chat_ps = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    _run(chat_ps["id"], {"prompt": "portrait", "refs": [PERSON], "count": 1})
    assert SENT, "mutation: omitted skill/shot should submit if the guard is removed"
    SENT.clear()
    chat_pk = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    _run(chat_pk["id"], {"prompt": "hero", "skill": "product-to-packaging", "count": 1})
    assert SENT, "mutation: omitted refs should submit (silent t2i) if the guard is removed"


def test_mutation_trusting_agent_skill_alone_would_miss_omitted_skill(relay, monkeypatch):
    """Must-red: if applicability only looks at args.skill, omitting skill bypasses the guard."""
    monkeypatch.setattr(guard, "_portrait_applies", lambda ctx, args: str((args or {}).get("skill") or "") == ps.SKILL)
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {"prompt": "portrait", "refs": [PERSON], "shot": "closeup", "count": 1})
    assert SENT, result
    assert result.get("kind") != guard.KIND_MISSING


def test_mutation_ignoring_upload_context_would_allow_packaging_t2i(relay, monkeypatch):
    monkeypatch.setattr(guard, "_packaging_refs_required", lambda ctx: False)
    chat = _chat(skill="product-to-packaging", uploads=[PRODUCT], card="packaging")
    result = _run(chat["id"], {"prompt": "hero", "count": 1})
    assert SENT, result
    assert result.get("kind") != guard.KIND_MISSING


def test_quote_route_blocks_portrait_all_omitted_when_upload_in_use():
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    token = BOT_CHAT_ID.set(chat["id"])
    try:
        routed = canvas.quote_route("generate_image", {
            "prompt": "professional portrait set", "count": 1,
        })
    finally:
        BOT_CHAT_ID.reset(token)
    assert routed is not None and routed[0] == ""
    blocked = (routed[1] or {}).get("param_blocked") or {}
    assert blocked.get("kind") == guard.KIND_MISSING
    for name in ("refs", "skill", "shot"):
        assert name in (blocked.get("missing") or []), blocked


def test_mutation_ignoring_portrait_upload_would_allow_silent_t2i(relay, monkeypatch):
    """Must-red: if upload context is ignored, the all-omitted portrait call would t2i."""
    monkeypatch.setattr(guard.GenContext, "portrait_uses_upload", lambda self: False)
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    result = _run(chat["id"], {"prompt": "professional portrait set", "count": 1})
    assert SENT, result
    assert result.get("kind") != guard.KIND_MISSING


@pytest.mark.parametrize("text", [
    '结束刚才的人像任务，不要使用之前上传的照片。这是全新的独立文生图请求：画一张山间湖泊风景，不要人物，也不要参考图。',
    'End the previous portrait task. Do not use the uploaded photo. This is a new independent text-to-image request: draw a mountain lake landscape, no person and no reference image.',
    "结束形象照任务，另做一张无参考图的猫咪海报。",
    "请结束当前形象照任务，不使用上传的照片，生成一张山水画。",
    "End the portrait task. Create a new landscape without reference images.",
    "Please stop this portrait session; generate a cat poster, no photos.",
])
def test_text_only_same_chat_transition_allows_new_t2i(relay, text):
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    chat_store.create_message(chat_id=chat["id"], role="user", blocks=[{"type": "text", "text": text}])
    ctx = guard.context_from_chat(chat["id"])
    assert not ctx.portrait() and not ctx.uploads and not ctx.card
    result = _run(chat["id"], {"prompt": "cat poster", "count": 1})
    assert SENT and result.get("kind") != guard.KIND_MISSING, result
    assert not SENT[0][1].get("refs") and not SENT[0][1].get("shot")
    chat_store.create_message(chat_id=chat["id"], role="user", blocks=[{"type": "text", "text": "再换成蓝色 / make it blue"}])
    SENT.clear()
    result = _run(chat["id"], {"prompt": "blue cat poster", "count": 1})
    assert SENT and result.get("kind") != guard.KIND_MISSING, result


@pytest.mark.parametrize("role,text", [
    ("user", "继续形象照，背景换蓝色。"),
    ("user", "Continue the portrait; change the background."),
    ("user", "不要结束形象照任务，另做一张无参考图的海报。"),
    ("user", "Do not end the portrait task. Create a new image without reference images."),
    ("user", "生成一张无参考图的海报。"),
    ("user", "结束形象照任务。"),
    ("assistant", "结束形象照任务，另做一张无参考图的海报。"),
    ("tool", "End the portrait task. Create a new image without reference images."),
])
def test_ongoing_portrait_or_nonuser_cannot_release_guard(relay, role, text):
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    chat_store.create_message(chat_id=chat["id"], role=role, blocks=[{"type": "text", "text": text}])
    _refused(_run(chat["id"], {"prompt": "new image without references", "count": 1}), "refs", "skill", "shot")


def test_portrait_chip_after_text_switch_restores_guard(relay):
    chat = _chat(skill="portrait-studio", uploads=[PERSON], card="portrait")
    chat_store.create_message(chat_id=chat["id"], role="user", blocks=[{
        "type": "text", "text": "结束形象照任务，另做一张无参考图的海报。"}])
    chat_store.create_message(chat_id=chat["id"], role="user", blocks=[
        {"type": "skill", "name": "portrait-studio"},
        {"type": "image", "url": PERSON}, {"type": "text", "text": "重新拍形象照"}])
    _refused(_run(chat["id"], {"prompt": "portrait", "count": 1}), "refs", "skill", "shot")
