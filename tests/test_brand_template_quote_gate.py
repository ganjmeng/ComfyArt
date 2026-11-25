"""A brand industry template uses the ordinary single-call quote gate.

``_dispatch_tools`` prices the call through ``_quote_steps`` / ``build_quote``
before any submit. Under the confirm line that quote is None and the call
runs, the same passthrough ``origin/main`` uses for one cheap generation.
Over the line ``_confirm_plan`` has to answer start. Skipping the brand
grant does not skip that gate. No WaveSpeed call.
"""
from __future__ import annotations

from ComfyArt.api import brand_identity as brand
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.skill_output import apply_generate
from test_agent_budget_391 import Rig, calls, reply

LOCK = (
    "Use the ComfyArt skill 'brand-identity-director' for this task.\n"
    "Output lock: template=geometric exactly 3 separate images"
)


def _turn(messages: list) -> str:
    for message in reversed(messages or []):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, list):
                content = " ".join(
                    str(part.get("text") or "") for part in content if isinstance(part, dict))
            return str(content or "")
    return ""


def _script(messages, n):
    """The #979 model: three direction proposals, then one guideline board."""
    last = _turn(messages)
    stage2 = "选第一个方向" in last
    if stage2:
        if n == 0:
            return calls(("generate_image", {
                "prompt": "guideline board for the chosen direction",
                "skill": brand.SKILL, "preset": "geometric", "stage": 2,
            }))
        return reply("规范板已生成。")
    if n < 3:
        return calls(("generate_image", {
            "prompt": f"logo direction {n + 1}",
            "skill": brand.SKILL,
        }))
    return reply("三个方向已出。")


def _gens(rig: Rig) -> list[dict]:
    return [args for name, args in rig.mcp if name == "generate_image"]


async def _rig(monkeypatch, *, price: float):
    brand.reset_for_tests()
    BOT_CHAT_ID.set("template-gate")
    rig = Rig(monkeypatch, _script)
    asked: list[dict] = []
    original = LocalLlmProvider._confirm_plan

    async def local_price(model, inputs):
        return (price, "quote", "test")

    async def watch(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        return await original(self, spec, turn, handle, **kwargs)

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", watch)
    return rig, asked


async def test_template_preset_without_confirmation_does_not_submit(monkeypatch):
    """Over the confirm line, nobody answering the card submits nothing."""
    rig, asked = await _rig(monkeypatch, price=0.60)
    await rig.send(LOCK, goal="")
    assert asked, "the template call never reached _confirm_plan"
    assert _gens(rig) == []


async def test_template_preset_confirmation_submits_three_then_one(monkeypatch):
    """Under the line, the ordinary gate passes the call through: 3, then 1.

    This is the #979 path. The model names no preset and no size. The output
    lock selects geometric, and no confirm card is required for a known price
    under the line.
    """
    rig, asked = await _rig(monkeypatch, price=0.04)
    await rig.send(LOCK, goal="")
    first = _gens(rig)
    assert len(first) == 3, first
    assert asked == []
    assert [(a.get("width"), a.get("height"), a.get("ratio"), a.get("preset"), a.get("stage"))
            for a in first] == [(1024, 1024, "1:1", "geometric", 1)] * 3

    rig.n = 0
    rig.mcp.clear()
    await rig.send("选第一个方向，直接出规范板", goal="")
    second = _gens(rig)
    assert len(second) == 1, second
    assert asked == []
    assert (second[0].get("width"), second[0].get("height"), second[0].get("ratio"),
            second[0].get("preset"), second[0].get("stage")) == (2048, 1152, "16:9", "geometric", 2)


async def test_template_preset_start_is_what_submits_the_over_line_call(monkeypatch):
    """The same over-line call submits only after _confirm_plan returns start."""
    rig, asked = await _rig(monkeypatch, price=0.60)

    async def start(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        return "start"

    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", start)
    await rig.send(LOCK, goal="")
    gens = _gens(rig)
    assert asked, "start was not a confirm-gate answer"
    assert len(gens) == 3, gens
    assert all(a.get("preset") == "geometric" and not a.get("brand_slot") for a in gens)


def _keep_preset_beside_slot(args, current_skill, **kwargs):
    """Leave the model's preset on a call that also names a brand slot.

    ``fill_default`` drops ``preset`` before ``brand_call`` reads the args. Putting
    it back is what lets a template-first reorder of that predicate be visible:
    ``geometric`` stays on the args, and ``brand_slot`` must still win.
    """
    sent_preset = str((args or {}).get("preset") or "")
    sent_slot = str((args or {}).get("brand_slot") or "")
    out = apply_generate(args, current_skill, **kwargs)
    if (sent_slot and brand.is_template(sent_preset) and isinstance(out, dict)
            and out.get("brand_slot")):
        out["preset"] = sent_preset
    return out


def _slot_and_preset(messages, n):
    if n == 0:
        return calls(("generate_image", {
            "prompt": "moodboard",
            "skill": brand.SKILL,
            "brand_slot": "moodboard",
            "preset": "geometric",
        }))
    return reply("done")


async def _slot_rig(monkeypatch, *, start: bool):
    assert brand.is_template("geometric")
    brand.reset_for_tests()
    BOT_CHAT_ID.set("c")
    rig = Rig(monkeypatch, _slot_and_preset)
    asked: list[dict] = []
    brand_dispatch: list[dict] = []
    original_confirm = LocalLlmProvider._confirm_plan
    original_brand = LocalLlmProvider._dispatch_one_confirmed_brand

    async def local_price(model, inputs):
        return (0.04, "quote", "test")

    async def watch_confirm(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        if start:
            return "start"
        return await original_confirm(self, spec, turn, handle, **kwargs)

    async def watch_brand(self, it, *args, **kwargs):
        brand_dispatch.append(dict(it.get("args") or {}))
        return await original_brand(self, it, *args, **kwargs)

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    monkeypatch.setattr("ComfyArt.bot.skill_output.apply_generate", _keep_preset_beside_slot)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", watch_confirm)
    monkeypatch.setattr(LocalLlmProvider, "_dispatch_one_confirmed_brand", watch_brand)
    return rig, asked, brand_dispatch


async def test_slot_and_template_without_confirmation_does_not_submit(monkeypatch):
    """brand_slot plus a template preset is still a brand grant, not a cheap passthrough.

    The price is under the confirm line. A template with no slot would submit.
    This call must show the brand card and submit nothing until Start.
    """
    rig, asked, brand_dispatch = await _slot_rig(monkeypatch, start=False)
    await rig.send("做品牌", goal="")
    assert _gens(rig) == []
    assert brand_dispatch == []
    assert asked and all(spec.get("brand_confirm") is True for spec in asked)


async def test_slot_and_template_submits_only_through_brand_start(monkeypatch):
    """Start on that brand card is what submits, through the confirmed-brand dispatch."""
    rig, asked, brand_dispatch = await _slot_rig(monkeypatch, start=True)
    await rig.send("做品牌", goal="")
    gens = _gens(rig)
    assert asked and all(spec.get("brand_confirm") is True for spec in asked)
    assert len(brand_dispatch) == 1, brand_dispatch
    assert brand_dispatch[0].get("brand_slot") == "moodboard"
    assert brand_dispatch[0].get("preset") == "geometric"
    assert brand.is_template(brand_dispatch[0].get("preset"))
    assert len(gens) == 1, gens
    assert gens[0].get("brand_slot") == "moodboard"
    assert "moodboard" in brand.submitted_slots(1)


def _stage2_board(messages, n):
    """Guideline board: skill only, stage 2, no preset and no brand_slot."""
    if n == 0:
        return calls(("generate_image", {
            "prompt": "guideline board for the chosen direction",
            "skill": brand.SKILL,
            "stage": 2,
        }))
    return reply("done")


async def _board_rig(monkeypatch, *, start: bool):
    brand.reset_for_tests()
    BOT_CHAT_ID.set("c")
    rig = Rig(monkeypatch, _stage2_board)
    asked: list[dict] = []
    original_confirm = LocalLlmProvider._confirm_plan

    async def local_price(model, inputs):
        return (0.04, "quote", "test")

    async def watch_confirm(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        if start:
            return "start"
        return await original_confirm(self, spec, turn, handle, **kwargs)

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", watch_confirm)
    return rig, asked


async def test_stage2_guideline_board_without_preset_or_slot_uses_quote_card(monkeypatch):
    """No preset and no brand_slot, stage 2: the brand default stage.

    The price is under the confirm line. The call must still enter the brand
    quote card and submit nothing. Start is what submits it.
    """
    held = await _board_rig(monkeypatch, start=False)
    rig, asked = held
    await rig.send("选第一个方向，直接出规范板", goal="")
    assert _gens(rig) == []
    assert asked and all(spec.get("brand_confirm") is True for spec in asked)

    rig, asked = await _board_rig(monkeypatch, start=True)
    await rig.send("选第一个方向，直接出规范板", goal="")
    gens = _gens(rig)
    assert asked and all(spec.get("brand_confirm") is True for spec in asked)
    assert len(gens) == 1, gens
    assert not gens[0].get("preset")
    assert gens[0].get("brand_slot") == "moodboard"


def _moodboard_phase():
    """Card 1 answered: the default path is on the moodboard, nothing submitted."""
    from test_brand_wrapup_1027 import _card1
    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
        "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]},
    })


def _logos_phase():
    """Moodboard placed and card 2 accepted. The open stage is the three logos."""
    from ComfyArt.api.bot_asks import validate_spec
    from ComfyArt.bot.skill_output import apply_generate
    _moodboard_phase()
    mood = apply_generate({"skill": brand.SKILL, "prompt": "board"}, brand.SKILL)
    brand.record_submitted(mood, {"ids": ["h-mood"]})
    brand.record_wait({"results": [{"id": "h-mood", "shapes": ["shape:mood"], "urls": ["/m.png"]}]})
    brand.record_card_answer(validate_spec({
        "questions": [{"id": "bi_moodboard", "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
                       "options": [{"id": "A", "label": "就这版，通过"}]}],
    }), {"bi_moodboard": {"selected": ["A"]}})


def _preset_during_stage(messages, n):
    if n == 0:
        return calls(("generate_image", {
            "prompt": "one direction",
            "skill": brand.SKILL,
            "preset": "geometric",
        }))
    return reply("done")


def _mixed_logos(messages, n):
    if n == 0:
        return calls(
            ("generate_image", {
                "prompt": "logo a", "skill": brand.SKILL, "brand_slot": "logo_a",
            }),
            ("generate_image", {
                "prompt": "direction b", "skill": brand.SKILL, "preset": "geometric",
            }),
            ("generate_image", {
                "prompt": "direction c", "skill": brand.SKILL, "preset": "geometric",
            }),
        )
    return reply("done")


async def _active_rig(monkeypatch, script):
    brand.reset_for_tests()
    BOT_CHAT_ID.set("c")
    rig = Rig(monkeypatch, script)
    asked: list[dict] = []
    brand_dispatch: list[dict] = []
    original_brand = LocalLlmProvider._dispatch_one_confirmed_brand

    async def local_price(model, inputs):
        return (0.04, "quote", "test")

    async def watch_confirm(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        return "start"

    async def watch_brand(self, it, *args, **kwargs):
        brand_dispatch.append(dict(it.get("args") or {}))
        return await original_brand(self, it, *args, **kwargs)

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", watch_confirm)
    monkeypatch.setattr(LocalLlmProvider, "_dispatch_one_confirmed_brand", watch_brand)
    return rig, asked, brand_dispatch


async def test_preset_during_active_default_stage_uses_grant_path(monkeypatch):
    """One geometric generate, no brand_slot, while the moodboard stage is open.

    The quote is stamped with the open slot, so after Start this is a grant
    submit. It must not be a plain 1024 run_mcp of the template.
    """
    rig, asked, brand_dispatch = await _active_rig(monkeypatch, _preset_during_stage)
    _moodboard_phase()
    seen = {"stage": False, "slots": [], "session_calls": 0}
    real_stage = brand.steps_are_brand_stage
    real_open = brand.session_default_stage_open

    def watch_stage(steps):
        result = real_stage(steps)
        slots = []
        for step in steps or []:
            args = step.get("arguments") if isinstance(step, dict) else None
            if isinstance(args, dict) and args.get("brand_slot"):
                slots.append(str(args["brand_slot"]))
        if result:
            seen["stage"] = True
            seen["slots"] = slots
        return result

    def watch_open():
        seen["session_calls"] += 1
        return real_open()

    monkeypatch.setattr(brand, "steps_are_brand_stage", watch_stage)
    monkeypatch.setattr(brand, "session_default_stage_open", watch_open)
    await rig.send("出一张", goal="")
    gens = _gens(rig)
    assert seen["stage"] is True and seen["slots"] == ["moodboard"], seen
    assert seen["session_calls"] == 0, seen
    assert asked and all(spec.get("brand_confirm") is True for spec in asked)
    assert len(brand_dispatch) == 1, brand_dispatch
    assert brand_dispatch[0].get("preset") == "geometric"
    assert not brand_dispatch[0].get("brand_slot")
    assert len(gens) == 1, gens
    assert gens[0].get("brand_slot") == "moodboard"
    assert (gens[0].get("width"), gens[0].get("height")) == (2048, 1152)
    assert "moodboard" in brand.submitted_slots(1)


async def test_mixed_logo_batch_every_item_uses_grant_path(monkeypatch):
    """phase=logos: logo_a plus two preset calls. None of them may take plain run_mcp."""
    rig, asked, brand_dispatch = await _active_rig(monkeypatch, _mixed_logos)
    _logos_phase()
    await rig.send("三个方向", goal="")
    gens = _gens(rig)
    assert asked and all(spec.get("brand_confirm") is True for spec in asked)
    assert len(brand_dispatch) == 3, brand_dispatch
    assert all(row.get("skill") == brand.SKILL for row in brand_dispatch)
    assert brand_dispatch[0].get("brand_slot") == "logo_a"
    assert brand_dispatch[1].get("preset") == "geometric" and not brand_dispatch[1].get("brand_slot")
    assert brand_dispatch[2].get("preset") == "geometric" and not brand_dispatch[2].get("brand_slot")
    assert gens and all(row.get("brand_slot") for row in gens)
    assert all((row.get("width"), row.get("height")) != (1024, 1024) for row in gens)
    recorded = brand.submitted_slots(2)
    assert {str(row.get("brand_slot")) for row in gens} <= recorded


async def _under_line(monkeypatch):
    """A known under-line price. Production confirm is left in place."""
    rig = Rig(monkeypatch, _script)
    asked: list[dict] = []
    original = LocalLlmProvider._confirm_plan

    async def local_price(model, inputs):
        return (0.04, "quote", "test")

    async def watch(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        return await original(self, spec, turn, handle, **kwargs)

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", watch)
    return rig, asked


async def _assert_template_passthrough(rig, asked):
    await rig.send(LOCK, goal="")
    first = _gens(rig)
    assert asked == [], asked
    assert len(first) == 3, first
    assert [(a.get("width"), a.get("height"), a.get("preset"), a.get("brand_slot"))
            for a in first] == [(1024, 1024, "geometric", None)] * 3
    rig.n = 0
    rig.mcp.clear()
    await rig.send("选第一个方向，直接出规范板", goal="")
    second = _gens(rig)
    assert asked == [], asked
    assert len(second) == 1, second
    assert (second[0].get("width"), second[0].get("height"), second[0].get("preset"),
            second[0].get("brand_slot")) == (2048, 1152, "geometric", None)


async def test_other_session_template_stays_on_the_quote_gate(monkeypatch):
    """Chat A on logos must not pull chat B's template generate onto the grant path.

    B's turn is bound with brand_progress_scope. A's phase stays on the other key.
    """
    brand.reset_for_tests()
    BOT_CHAT_ID.set("chat-a")
    _logos_phase()
    assert brand._progress()["phase"] == "logos"
    token = brand.brand_progress_scope("chat-b")
    try:
        assert brand._progress()["phase"] == "need_card1"
        rig, asked = await _under_line(monkeypatch)
        await _assert_template_passthrough(rig, asked)
    finally:
        brand.reset_brand_progress_scope(token)
    assert brand._progress()["phase"] == "logos"


async def test_finished_brand_session_template_stays_on_the_quote_gate(monkeypatch):
    """After the default path is done, the same chat's template call is a normal quote."""
    from test_brand_wrapup_1027 import _place, _reach_finals, _submit_finals
    brand.reset_for_tests()
    BOT_CHAT_ID.set("chat-done")
    _reach_finals()
    for slot in _submit_finals():
        _place(slot)
    assert brand._progress()["phase"] == "done"
    rig, asked = await _under_line(monkeypatch)
    await _assert_template_passthrough(rig, asked)
    assert brand._progress()["phase"] == "done"
