"""#959: the product-to-packaging multi-step pre-quote equals each image's real submit.

The four default packaging images are one anchor (3:4) and three extensions (4:3),
each one Sunburst edit call at 2k with count 1 and 1 resp. 2 references. The quote
card must plan those four images in order (virtual image 1..4, never all image 1)
and price exactly the parameters that will be submitted, while previewing must not
consume the real execution sequence.

$0: a deliberately amplified MOCK price table (3:4 base $0.03, 4:3 base $0.05,
2k +$0.02, every extra reference +$0.01), mocked submit/approval, no real keys and
no supplier call. The mock totals prove calculation consistency only; they are not
a real quote or a charge.
"""
from __future__ import annotations

import asyncio
import copy
import os

import pytest

from ComfyArt.api import chat_store, paid_guard, portrait_studio as ps, product_packaging as pk
from ComfyArt.api import skill_param_guard as guard
from ComfyArt.api.auto_models import skill_pin
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.plan_quote import build_quote

SKILL = pk.SKILL
PRODUCT = "/api/view?filename=product-959.png&type=input"
ANCHOR_PLAN = "shape:anchor-planned"  # plan placeholder: the anchor does not exist when the quote runs
ANCHOR = "shape:anchor-959"           # the shape images 2-4 add after image 1 is placed
SUNBURST_EDIT = str(skill_pin(SKILL)["edit_model"])

# QA #959 mock table, deliberately amplified so a wrong tier/ratio/ref count is visible.
MOCK_UNIT = {"3:4": 0.03, "4:3": 0.05}
MOCK_2K = 0.02
MOCK_REF = 0.01

EXPECTED = [  # one row per image: index, role, ratio, resolution, refs, mock price
    (1, pk.ANCHOR_ROLE, "3:4", "2k", 1, 0.05),
    (2, pk.EXTENSION_ROLE, "4:3", "2k", 2, 0.08),
    (3, pk.EXTENSION_ROLE, "4:3", "2k", 2, 0.08),
    (4, pk.EXTENSION_ROLE, "4:3", "2k", 2, 0.08),
]

SENT: list[tuple[str, dict]] = []


def _mock_price(inputs: dict) -> float:
    """The #959 mock table over the fields the price table reads."""
    ratio = str(inputs.get("ratio") or "3:4")
    unit = MOCK_UNIT[ratio]
    if str(inputs.get("resolution") or "1k") == "2k":
        unit += MOCK_2K
    unit += MOCK_REF * max(0, len(inputs.get("images") or []) - 1)
    return round(unit, 6)


def _freeze(locks: dict) -> dict:
    return {k: {kk: list(vv) if isinstance(vv, list) else vv for kk, vv in v.items()} for k, v in locks.items()}


@pytest.fixture(autouse=True)
def _isolate():
    keys = ("WAVESPEED_API_KEY", "KIE_API_KEY", "DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN")
    saved = {k: os.environ.pop(k, None) for k in keys}
    turns = dict(paid_guard.TURNS)
    locks_ps = _freeze(ps._LOCKS)
    locks_pk = _freeze(pk._LOCKS)
    SENT.clear()
    try:
        yield
    finally:
        for k in list(paid_guard.TURNS):
            if k not in turns:
                paid_guard.TURNS.pop(k, None)
        ps._LOCKS.clear()
        ps._LOCKS.update(locks_ps)
        pk._LOCKS.clear()
        pk._LOCKS.update(locks_pk)
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


@pytest.fixture
def relay(monkeypatch):
    SENT.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, copy.deepcopy(dict(args))))
        return {"ids": [f"shape:g{len(SENT)}"], "submitted": True,
                "model": args.get("edit_model") or args.get("model")}

    async def approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", approval)


def _chat():
    """One chat whose current task is product-to-packaging on an uploaded product photo."""
    chat = chat_store.create_chat(user="default", project="p959", provider="local-llm")
    chat_store.create_message(chat_id=chat["id"], role="user", blocks=[
        {"type": "skill", "name": SKILL},
        {"type": "image", "url": PRODUCT, "shape": "loose:0", "name": "product.png"},
        {"type": "text", "text": "用这张产品图做一套包装。"},
    ])
    answers = {"pk_product": {"selected": ["A"]}, "pk_color": {"selected": ["A"]},
               "pk_scope": {"selected": ["A"]}}
    chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=[{
        "type": "ask", "status": "answered", "ask_id": "a-pk-959",
        "questions": pk.card_questions(None, "zh"),
        "answers": answers,
    }])
    return chat, answers


def _seed(chat_id: str, answers: dict) -> None:
    """The card was answered this turn: the extension images follow its Q3 scopes."""
    token = BOT_CHAT_ID.set(chat_id)
    try:
        pk.record_card_answer(pk.card_spec(None, "zh"), answers)
    finally:
        BOT_CHAT_ID.reset(token)


def _steps() -> list[dict]:
    """The agent's four-step plan: same arguments it will pass to generate_image."""
    prompts = ["anchor: the package and the product in one key visual",
               "the outer box from several angles",
               "the label close up",
               "the unboxing with the inner tray"]
    steps = []
    for i, prompt in enumerate(prompts):
        refs = [PRODUCT] if i == 0 else [PRODUCT, ANCHOR_PLAN]
        steps.append({"text": f"图 {i + 1}", "tool": "generate_image", "model": "",
                      "arguments": {"prompt": prompt, "skill": SKILL, "refs": refs, "count": 1}})
    return steps


def _actual_calls() -> list[dict]:
    """What the agent submits after the user accepts: the anchor is a real shape for images 2-4."""
    steps = _steps()
    for i, step in enumerate(steps):
        if i:
            step["arguments"]["refs"] = [PRODUCT, ANCHOR]
    return [step["arguments"] for step in steps]


def _quote(chat_id: str, steps: list[dict]):
    """Build the quote; capture every routed step and what the price table was asked."""
    routed: list[dict] = []
    priced: list[tuple[str, dict]] = []

    def router(tool, args, position):
        model, inputs = canvas.quote_route(tool, args, position)
        routed.append({"position": position, "model": model, "inputs": copy.deepcopy(inputs)})
        return model, inputs

    async def pricer(model, inputs):
        priced.append((model, copy.deepcopy(inputs)))
        return _mock_price(inputs)

    async def models_for(feature):  # a packaging quote is pinned: it never falls back to a feature table
        raise AssertionError(f"must not price the dearest model of {feature}")

    token = BOT_CHAT_ID.set(chat_id)
    try:
        quote = asyncio.run(build_quote(steps, "zh", threshold=0.0, pricer=pricer,
                                        models_for=models_for, router=router))
    finally:
        BOT_CHAT_ID.reset(token)
    return quote, routed, priced


def _execute(chat_id: str, calls: list[dict]) -> None:
    token = BOT_CHAT_ID.set(chat_id)

    async def go():
        return [await canvas.TOOLS["generate_image"]["handler"](dict(a)) for a in calls]

    try:
        asyncio.run(go())
    finally:
        BOT_CHAT_ID.reset(token)


def _preview(chat_id: str, steps: list[dict]) -> list[dict]:
    """The validated args the quote walks, step by step (preview only: the turn does not move)."""
    token = BOT_CHAT_ID.set(chat_id)
    try:
        return [guard.preview_locked_args(step["arguments"], i) for i, step in enumerate(steps)]
    finally:
        BOT_CHAT_ID.reset(token)


def test_quote_plan_equals_the_actual_submit_for_all_four_images(relay):
    chat, answers = _chat()
    _seed(chat["id"], answers)
    steps = _steps()
    preview = _preview(chat["id"], steps)
    quote, routed, priced = _quote(chat["id"], steps)

    assert quote is not None and len(quote.lines) == 4
    assert [r["position"] for r in routed] == [0, 1, 2, 3]
    # The old #959 defect: four previews all image 1 at 3:4/1k, $0.15 vs $0.29 actual.
    assert [r["inputs"]["image_index"] for r in routed] == [1, 2, 3, 4]
    assert quote.total == round(sum(row[5] for row in EXPECTED), 4) == 0.29
    assert quote.total == round(sum(line.amount for line in quote.lines), 4)

    _execute(chat["id"], _actual_calls())
    assert [action for action, _ in SENT] == ["generate_image"] * 4

    for i, (index, role, ratio, resolution, refs, price) in enumerate(EXPECTED):
        got = routed[i]["inputs"]
        sent = SENT[i][1]
        # --- preview plan: index / role / aspect / resolution / refs / model / price ---
        assert routed[i]["model"] == SUNBURST_EDIT and routed[i]["model"] == sent.get("edit_model")
        assert (got["image_index"], got["image_role"]) == (index, role)
        assert (got["ratio"], got["resolution"]) == (ratio, resolution)
        assert len(got["images"]) == refs
        assert (priced[i][0], priced[i][1]["ratio"], priced[i][1]["resolution"]) == (SUNBURST_EDIT, ratio, resolution)
        assert len(priced[i][1]["images"]) == refs
        assert quote.lines[i].amount == price == _mock_price(priced[i][1])
        # --- real submit (i+1-th call): identical spec; the preview annotations are not sent ---
        assert index == i + 1
        assert sent["ratio"] == ratio
        assert sent["edit_resolution"] == resolution
        assert sent["count"] == 1
        assert len(sent["refs"]) == refs
        assert sent["refs"][0] == PRODUCT
        assert "image_index" not in sent and "image_role" not in sent
        assert _mock_price({"ratio": sent["ratio"], "resolution": sent["edit_resolution"],
                            "images": sent["refs"]}) == price

    # refs order: the uploaded product photo stays first; the second ref is the planned
    # anchor placeholder in the quote and the placed anchor shape at submit.
    assert preview[0]["refs"] == SENT[0][1]["refs"] == [PRODUCT]
    for i in (1, 2, 3):
        assert preview[i]["refs"] == [PRODUCT, ANCHOR_PLAN]
        assert SENT[i][1]["refs"] == [PRODUCT, ANCHOR]
    # same prompt plan (the "This image shows:" line comes from the answered card)
    assert [p["prompt"] for p in preview] == [sent["prompt"] for _, sent in SENT]


def test_preview_does_not_consume_the_real_execution_sequence(relay):
    chat, answers = _chat()
    _seed(chat["id"], answers)
    before = _freeze(pk._LOCKS)

    first, routed_first, _ = _quote(chat["id"], _steps())
    assert pk._LOCKS == before, "a quote must not create, advance or rewrite the turn lock"
    # A repeated quote (the user reopens the card) walks the same plan again, not 5..8.
    second, routed_second, _ = _quote(chat["id"], _steps())
    assert pk._LOCKS == before
    assert [r["inputs"]["image_index"] for r in routed_first] == [1, 2, 3, 4]
    assert [r["inputs"]["image_index"] for r in routed_second] == [1, 2, 3, 4]
    assert ([r["inputs"]["ratio"] for r in routed_first]
            == [r["inputs"]["ratio"] for r in routed_second] == ["3:4", "4:3", "4:3", "4:3"])
    assert first.total == second.total == 0.29

    _execute(chat["id"], _actual_calls())
    # The real submits are the 1st..4th call of the turn, in plan order (the preview did not move them).
    assert [sent["ratio"] for _, sent in SENT] == ["3:4", "4:3", "4:3", "4:3"]
    assert all("image_index" not in sent for _, sent in SENT)


def test_quote_still_refuses_missing_refs_without_a_price(relay):
    """#958 protection stays: an incomplete packaging call is param_blocked, not priced as t2i."""
    chat, answers = _chat()
    _seed(chat["id"], answers)
    steps = _steps()
    for step in steps:
        step["arguments"].pop("refs")
    quote, routed, priced = _quote(chat["id"], steps)
    assert priced == []
    assert quote is not None and all(line.unpriced for line in quote.lines)
    assert all("param_blocked" in (r["inputs"] or {}) for r in routed if r["model"] == "")
    assert SENT == []
