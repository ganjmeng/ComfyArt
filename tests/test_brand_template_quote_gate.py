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


async def test_stage2_guideline_board_without_preset_or_slot_stops_at_card1(monkeypatch):
    """No preset and no brand_slot, stage 2, phase still need_card1.

    fill_default blocks with the card-1 question. There is no quote card and
    nothing is submitted, including when a confirm answer would have been start.
    """
    brand.reset_for_tests()
    BOT_CHAT_ID.set("c")
    assert brand._progress()["phase"] == "need_card1"
    filled = apply_generate({
        "skill": brand.SKILL,
        "prompt": "guideline board for the chosen direction",
        "stage": 2,
    }, brand.SKILL)
    block = filled.get("_brand_block") or {}
    assert block.get("submitted") is False
    assert "问询卡 1" in str(block.get("error") or "")
    assert "Card 1 has not been answered" in str(block.get("error") or "")
    assert brand._progress()["phase"] == "need_card1"

    for start in (False, True):
        rig, asked = await _board_rig(monkeypatch, start=start)
        _res, events = await rig.send("选第一个方向，直接出规范板", goal="")
        texts = "\n".join(getattr(ev, "text", "") or "" for ev in events)
        assert _gens(rig) == []
        assert asked == [], asked
        assert not any(getattr(ev, "t", "") == "ask" for ev in events)
        assert "问询卡 1" in texts
        assert "确认费用" not in texts
        assert brand._progress()["phase"] == "need_card1"


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

    It is a template grant keyed by this call. It does not take the moodboard
    slot, write submitted_slots, or advance the phase.
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
    assert seen["stage"] is False and seen["slots"] == [], seen
    assert seen["session_calls"] >= 1, seen
    texts = "\n".join(
        str(line.get("text") or "")
        for spec in asked for line in (spec.get("lines") or [])
    )
    assert "情绪板 阶段 · 几何模板" in texts, texts
    assert "额外一张，不替换情绪板" in texts, texts
    assert brand_dispatch == [], brand_dispatch
    assert len(gens) == 1, gens
    assert gens[0].get("preset") == "geometric"
    assert not gens[0].get("brand_slot")
    grants = list(brand.template_grants().values())
    assert len(grants) == 1 and grants[0].get("type") == "template", grants
    assert grants[0].get("preset") == "geometric"
    assert grants[0].get("prompt") == "one direction"
    assert grants[0].get("used") is True
    assert "moodboard" not in brand.submitted_slots(1)
    assert brand._progress()["phase"] == "moodboard"


async def test_mixed_logo_batch_every_item_uses_grant_path(monkeypatch):
    """phase=logos: logo_a is the slot grant. The two presets are template grants."""
    rig, asked, brand_dispatch = await _active_rig(monkeypatch, _mixed_logos)
    _logos_phase()
    await rig.send("三个方向", goal="")
    gens = _gens(rig)
    assert asked and all(spec.get("brand_confirm") is True for spec in asked)
    texts = "\n".join(
        str(line.get("text") or "")
        for spec in asked for line in (spec.get("lines") or [])
    )
    assert "Logo 阶段 · 几何模板" in texts, texts
    assert "额外一张，不替换方向 A/B/C" in texts, texts
    assert len(brand_dispatch) == 1, brand_dispatch
    assert brand_dispatch[0].get("brand_slot") == "logo_a"
    logos = [row for row in gens if row.get("brand_slot") == "logo_a"]
    extras = [row for row in gens if row.get("preset") == "geometric" and not row.get("brand_slot")]
    assert len(logos) == 1 and len(extras) == 2, gens
    recorded = brand.submitted_slots(2)
    assert recorded == {"logo_a"}, recorded
    assert brand._progress()["phase"] == "logos"
    grants = list(brand.template_grants().values())
    assert len(grants) == 2, grants
    assert all(row.get("type") == "template" and row.get("used") is True for row in grants)


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


def _paid_prompts(rig):
    return [str((args or {}).get("prompt") or "") for _name, args in rig.paid_mcp()]


async def test_expired_grant_does_not_submit(monkeypatch):
    """A grant 700s past its deadline does not pay the next generate."""
    from test_brand_identity_1019 import _live_brand_run, _logos_ready, _quoted_generate, _short_logo_steps
    brand.reset_for_tests()
    token = BOT_CHAT_ID.set("c")
    clock = {"t": 1_700_000_000.0}
    monkeypatch.setattr(brand, "_clock", lambda: clock["t"])
    try:
        _logos_ready()

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _short_logo_steps()}))
            clock["t"] += 700
            return calls(_quoted_generate("logo_a"))

        rig, _res, _events, confirms, _submits = await _live_brand_run(monkeypatch, script)
        assert confirms
        assert rig.paid_mcp() == []
        assert "logo_a" not in brand.submitted_slots(2)
    finally:
        BOT_CHAT_ID.reset(token)


async def test_unquoted_prompt_does_not_submit(monkeypatch):
    """A prompt that was not on the confirmed quote is not submitted in its place."""
    from test_brand_identity_1019 import _live_brand_run, _logos_ready, _short_logo_steps
    brand.reset_for_tests()
    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        changed = "unquoted prompt that must not be sent"

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _short_logo_steps()}))
            return calls(("generate_image", {
                "prompt": changed,
                "skill": brand.SKILL,
                "preset": "geometric",
            }))

        rig, _res, _events, confirms, _submits = await _live_brand_run(monkeypatch, script)
        assert confirms
        assert rig.paid_mcp() == []
        assert changed not in _paid_prompts(rig)
        assert "logo_a" not in brand.submitted_slots(2)
    finally:
        BOT_CHAT_ID.reset(token)


async def test_fourth_unquoted_call_cannot_take_logo_a(monkeypatch):
    """A generate beyond the quoted slots does not submit and does not take logo_a."""
    from test_brand_identity_1019 import _live_brand_run, _logos_ready, _short_logo_steps
    brand.reset_for_tests()
    token = BOT_CHAT_ID.set("c")
    try:
        _logos_ready()
        extra = "fourth call beyond the quoted slots"

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": _short_logo_steps()}))
            return calls(("generate_image", {
                "prompt": extra,
                "skill": brand.SKILL,
                "preset": "geometric",
            }))

        rig, _res, _events, confirms, _submits = await _live_brand_run(monkeypatch, script)
        assert confirms
        assert rig.paid_mcp() == []
        assert extra not in _paid_prompts(rig)
        assert "logo_a" not in brand.submitted_slots(2)
    finally:
        BOT_CHAT_ID.reset(token)


def _line_text(asked) -> str:
    return "\n".join(
        str(line.get("text") or "")
        for spec in asked for line in (spec.get("lines") or [])
    )


async def test_preset_submit_leaves_logo_a_for_its_own_card(monkeypatch):
    """A confirmed template extra does not take logo_a. logo_a still quotes and submits."""
    which = {"step": "preset"}

    def script(messages, n):
        if n != 0:
            return reply("done")
        if which["step"] == "preset":
            return calls(("generate_image", {
                "prompt": "extra mark", "skill": brand.SKILL, "preset": "geometric",
            }))
        return calls(("generate_image", {
            "prompt": "logo a", "skill": brand.SKILL, "brand_slot": "logo_a",
        }))

    rig, asked, brand_dispatch = await _active_rig(monkeypatch, script)
    _logos_phase()
    await rig.send("加一张几何", goal="")
    assert len(_gens(rig)) == 1
    assert _gens(rig)[0].get("preset") == "geometric"
    assert not _gens(rig)[0].get("brand_slot")
    assert "Logo 阶段 · 几何模板" in _line_text(asked)
    assert "额外一张，不替换方向 A/B/C" in _line_text(asked)
    assert brand.submitted_slots(2) == set()
    assert brand._progress()["phase"] == "logos"
    which["step"] = "logo"
    rig.n = 0
    rig.mcp.clear()
    asked.clear()
    brand_dispatch.clear()
    await rig.send("出方向 A", goal="")
    assert any(spec.get("brand_confirm") is True for spec in asked), asked
    assert len(_gens(rig)) == 1 and _gens(rig)[0].get("brand_slot") == "logo_a"
    assert brand.submitted_slots(2) == {"logo_a"}
    assert brand._progress()["phase"] == "logos"


async def test_template_confirm_is_not_reused_across_turns(monkeypatch):
    """The next identical preset call asks again. Cancel submits nothing."""
    answers = {"n": 0}

    def script(messages, n):
        if n == 0:
            return calls(("generate_image", {
                "prompt": "same extra", "skill": brand.SKILL, "preset": "geometric",
            }))
        return reply("done")

    brand.reset_for_tests()
    BOT_CHAT_ID.set("c")
    rig = Rig(monkeypatch, script)
    asked: list[dict] = []

    async def local_price(model, inputs):
        return (0.04, "quote", "test")

    async def watch_confirm(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        answers["n"] += 1
        return "start" if answers["n"] == 1 else "cancel"

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", watch_confirm)
    _logos_phase()
    await rig.send("第一张", goal="")
    assert len(rig.paid_mcp()) == 1
    rig.n = 0
    await rig.send("再来一张同样的", goal="")
    assert len(asked) == 2, asked
    assert len(rig.paid_mcp()) == 1


async def test_changed_template_prompt_does_not_reuse_confirm(monkeypatch):
    """A different prompt is not covered by the previous template grant."""
    which = {"prompt": "first extra"}

    def script(messages, n):
        if n != 0:
            return reply("done")
        return calls(("generate_image", {
            "prompt": which["prompt"], "skill": brand.SKILL, "preset": "geometric",
        }))

    answers = {"n": 0}
    brand.reset_for_tests()
    BOT_CHAT_ID.set("c")
    rig = Rig(monkeypatch, script)
    asked: list[dict] = []

    async def local_price(model, inputs):
        return (0.04, "quote", "test")

    async def watch_confirm(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        answers["n"] += 1
        return "start" if answers["n"] == 1 else "cancel"

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", watch_confirm)
    _logos_phase()
    await rig.send("第一张", goal="")
    which["prompt"] = "changed extra that must not submit"
    rig.n = 0
    await rig.send("换一句", goal="")
    prompts = [args.get("prompt") for _name, args in rig.paid_mcp()]
    assert "changed extra that must not submit" not in prompts
    assert len(asked) == 2
    assert len(rig.paid_mcp()) == 1


async def test_expired_template_grant_blocks_without_a_new_confirm(monkeypatch):
    """An unused template grant past 700s does not authorize a submit."""
    def script(messages, n):
        if n == 0:
            return calls(("generate_image", {
                "prompt": "timed extra", "skill": brand.SKILL, "preset": "geometric",
            }))
        return reply("done")

    rig, _asked, _dispatch = await _active_rig(monkeypatch, script)
    _logos_phase()
    await rig.send("加一张", goal="")
    _name, args = rig.paid_mcp()[0]
    saved = brand._progress()["template_grants"]
    for grant in saved.values():
        grant["used"] = False
    assert brand.template_submit_block(args, now=float(next(iter(saved.values()))["expires_at"]) + 100) == "expired"
    assert len(rig.paid_mcp()) == 1
    assert brand.submitted_slots(2) == set()


async def test_template_grant_write_failure_is_readable(monkeypatch):
    """A grant that cannot be saved shows the user sentence and submits nothing."""
    def script(messages, n):
        if n == 0:
            return calls(("generate_image", {
                "prompt": "unsaved extra", "skill": brand.SKILL, "preset": "geometric",
            }))
        return reply("done")

    rig, _asked, _dispatch = await _active_rig(monkeypatch, script)
    _logos_phase()

    def boom():
        raise brand.BrandGrantPersistError("disk")

    monkeypatch.setattr(brand, "_persist_grants", boom)
    _res, events = await rig.send("加一张", goal="")
    texts = "\n".join(getattr(ev, "text", "") or "" for ev in events)
    assert "确认没有保存成功" in texts, texts
    assert rig.paid_mcp() == []
    assert brand.template_grants() == {}
    assert brand._progress()["phase"] == "logos"
