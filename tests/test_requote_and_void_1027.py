"""#1027: two generic safety paths, offline, no WaveSpeed or LLM call.

1. A confirm card past its lifetime is re-issued by the shared quote/plan gate: the same frozen
   steps are priced again and a new live card replaces it. Nothing is submitted until Start on a
   live card. Any skill whose row sets always_confirm / confirm_ttl_s gets this; no skill is named
   in the code under test.
2. A submitted image that later fails with no charge kept is voided once, keyed by its generation
   id: the unit goes back to the run budget and the paid-guard cap, so its retry dispatches once
   and the confirmed units are not consumed twice. A failure that kept a charge, or whose text
   says nothing about money, stays counted.
"""
from __future__ import annotations

import json

import pytest

from ComfyArt.api import paid_guard
from ComfyArt.bot import agent_loop
from ComfyArt.bot.plan_quote import EXPIRED_TEXT, MAX_REQUOTES, REQUOTED_TEXT
from ComfyArt.bot.run_budget import ProgressTracker, StepObservation, generation_ids, void_ids

from test_brand_identity_1019 import SKILL, _call, _rig



# ---------------------------------------------------------------- 1. expiry -> requote

def _scripted_confirm(monkeypatch, rig, outcomes, seen):
    """_confirm_plan answers from `outcomes` in order; the last one repeats."""
    async def confirm(spec, turn, handle, **_kw):
        seen.append(spec)
        # Nothing may have been submitted before the card that said start.
        seen_submits.append(len(rig.paid_mcp()))
        return outcomes[min(len(seen) - 1, len(outcomes) - 1)]
    seen_submits: list[int] = []
    monkeypatch.setattr(rig.p, "_confirm_plan", confirm)
    return seen_submits


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_expired_card_is_reissued_and_only_the_new_start_dispatches(monkeypatch, budget):
    rig, _unused = _rig(monkeypatch, [[_call("1:1"), _call("1:1")]], budget=budget)
    seen: list = []
    submits = _scripted_confirm(monkeypatch, rig, ["expired", "start"], seen)
    prices = []

    async def price(model, inputs):
        prices.append(1)
        return (0.04, "quote", "test")

    monkeypatch.setattr(rig.p, "_price_one", price)
    res, events = await rig.send("做一个品牌", goal="")
    assert len(seen) == 2, "the expired card is replaced by exactly one new card"
    assert seen[0] is not seen[1]
    assert submits == [0, 0], "nothing is submitted while a card is open or after it expired"
    assert len(rig.paid_mcp()) == 2, "the new card's Start dispatches the frozen steps once"
    assert len(prices) >= 4, "the same steps were priced again, not a copied quote"
    notes = [e.text for e in events if e.t == "notify"]
    assert REQUOTED_TEXT["zh"] in notes
    assert not (res.error or "")


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_requote_is_bounded_and_ends_without_a_charge(monkeypatch, budget):
    rig, _unused = _rig(monkeypatch, [[_call("1:1")]], budget=budget)
    seen: list = []
    _scripted_confirm(monkeypatch, rig, ["expired"], seen)
    res, events = await rig.send("做一个品牌", goal="")
    assert len(seen) == MAX_REQUOTES + 1
    assert rig.paid_mcp() == []
    text = "\n".join(e.text for e in events if e.t == "delta" and e.text)
    assert EXPIRED_TEXT["zh"] in text or EXPIRED_TEXT["zh"] in (res.error or "")


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_a_cancel_on_the_new_card_submits_nothing(monkeypatch, budget):
    rig, _unused = _rig(monkeypatch, [[_call("1:1")]], budget=budget)
    seen: list = []
    _scripted_confirm(monkeypatch, rig, ["expired", "cancel"], seen)
    await rig.send("做一个品牌", goal="")
    assert len(seen) == 2 and rig.paid_mcp() == []


# ---------------------------------------------------------------- 2. void accounting

def _wait(rows):
    return {"status": "done", "results": rows}


REFUNDED = {"id": "g1", "status": "error", "error": "生成失败，已退款", "charged": True, "refunded": True}
NOT_CHARGED = {"id": "g2", "status": "error", "error": "生成失败，未扣费", "charged": False, "refunded": False}
KEPT = {"id": "g3", "status": "error", "error": "生成失败，可能已扣费", "charged": True, "refunded": False}
SILENT = {"id": "g4", "status": "error", "error": "provider timeout", "charged": False, "refunded": False}
DECLINED = {"id": "g5", "status": "declined", "cancelled": True, "error": "已取消该生成，未扣费"}
DONE = {"id": "g6", "status": "done", "placed": True}


def test_void_ids_only_for_refunded_or_explicitly_uncharged_or_declined():
    got = void_ids(json.dumps(_wait([REFUNDED, NOT_CHARGED, KEPT, SILENT, DECLINED, DONE])))
    assert got == ["g1", "g2", "g5"]
    assert generation_ids(json.dumps({"ids": ["a", "b"]})) == ["a", "b"]
    assert generation_ids("not json") == []


def _obs(tool, args, result):
    return StepObservation(tool=tool, args_key=f"{tool}\x00{json.dumps(args)}", result=json.dumps(result))


def test_tracker_gives_the_unit_back_once_and_the_retry_fits_exactly_once():
    t = ProgressTracker()
    t.planned_images = 3
    t.over_budget([_obs("generate_image", {"count": 1, "prompt": f"p{i}"}, {"ids": [f"g{i}"]}) for i in (1, 2, 3)])
    assert t.gen_calls == 3
    t.over_budget([_obs("wait_generation", {"ids": ["g1", "g2", "g3"]}, _wait([REFUNDED, DONE | {"id": "g2"}, DONE | {"id": "g3"}]))])
    assert t.gen_calls == 2 and t.voided == ["g1"] and t.voided_new == ["g1"]
    # The same wait result seen again (resume, poll) gives nothing back twice.
    t.over_budget([_obs("wait_generation", {"ids": ["g1"]}, _wait([REFUNDED]))])
    assert t.gen_calls == 2 and t.voided == ["g1"]
    # One retry returns the count to the authorized total; it is not a second unit.
    t.over_budget([_obs("generate_image", {"count": 1, "prompt": "retry"}, {"ids": ["g7"]})])
    assert t.gen_calls == 3


def test_tracker_keeps_a_failure_that_kept_a_charge_and_a_silent_one():
    t = ProgressTracker()
    t.over_budget([_obs("generate_image", {"count": 1, "prompt": f"p{i}"}, {"ids": [f"g{i}"]}) for i in (3, 4)])
    t.over_budget([_obs("wait_generation", {}, _wait([KEPT, SILENT]))])
    assert t.gen_calls == 2 and t.voided == []


def test_tracker_ledger_survives_a_checkpoint_round_trip():
    t = ProgressTracker()
    t.over_budget([_obs("generate_image", {"count": 1, "prompt": "p"}, {"ids": ["g1"]})])
    t2 = ProgressTracker.restore(t.snapshot())
    t2.over_budget([_obs("wait_generation", {}, _wait([REFUNDED]))])
    assert t2.gen_calls == 0 and t2.voided == ["g1"]


def test_paid_guard_cap_has_room_for_exactly_the_voided_images_retry():
    cid = "void-cap"
    guard = paid_guard.begin_turn(cid, text="做 2 张", provider_text="做 2 张", lang="zh")
    try:
        assert guard.cap == 2
        for gid in ("g1", "g2"):
            assert paid_guard.before_call(cid, "generate_image", {"count": 1}) is None
            paid_guard.after_call(cid, "generate_image", {"count": 1}, {"ids": [gid]}, True)
        assert paid_guard.before_call(cid, "generate_image", {"count": 1}), "cap reached: a third is refused"
        guard.stopped = ""  # the refusal above only probes; reopen the turn
        paid_guard.after_call(cid, "wait_generation", {}, _wait([REFUNDED | {"id": "g1"}]), True)
        paid_guard.after_call(cid, "wait_generation", {}, _wait([REFUNDED | {"id": "g1"}]), True)  # replay: no-op
        assert guard.used[guard.plan_item] == 1
        assert paid_guard.before_call(cid, "generate_image", {"count": 1}) is None
        paid_guard.after_call(cid, "generate_image", {"count": 1}, {"ids": ["g3"]}, True)
        assert guard.used[guard.plan_item] == 2
        guard.stopped = ""
        assert paid_guard.before_call(cid, "generate_image", {"count": 1}), "a second retry is not free"
    finally:
        paid_guard.end_turn(cid)


def test_paid_guard_keeps_a_failure_that_kept_a_charge():
    cid = "void-kept"
    guard = paid_guard.begin_turn(cid, text="做 1 张", provider_text="做 1 张", lang="zh")
    try:
        paid_guard.after_call(cid, "generate_image", {"count": 1}, {"ids": ["g3"]}, True)
        paid_guard.after_call(cid, "wait_generation", {}, _wait([KEPT]), True)
        assert guard.used[guard.plan_item] == 1
        assert paid_guard.before_call(cid, "generate_image", {"count": 1}), "the kept charge still counts"
    finally:
        paid_guard.end_turn(cid)


class _Store:
    def __init__(self):
        self.finished = []

    def finish_usage_event(self, eid, **kw):
        self.finished.append((eid, kw))


class _Ctx:
    """Only what paid_void touches."""
    def __init__(self):
        self.paid = {}
        self.store = _Store()
        self.events = []

        class _Used:
            credits = 0.12
        self.budget = type("B", (), {"used": _Used()})()

    def checkpoint(self, *a, **k):
        pass

    def usage_event(self, **kw):
        self.events.append(kw)


def test_paid_void_releases_one_images_share_and_marks_the_metering_row_once():
    ctx = _Ctx()
    ctx.paid["s1:a"] = {"status": "done", "price": 0.12, "ids": ["g1", "g2", "g3"], "tool": "generate_image",
                        "event_id": 7}
    agent_loop.paid_void(ctx, ["g2"])
    agent_loop.paid_void(ctx, ["g2"])  # replay: no second refund
    assert ctx.budget.used.credits == pytest.approx(0.08)
    assert ctx.paid["s1:a"]["status"] == "done" and ctx.paid["s1:a"]["voided"] == ["g2"]
    assert ctx.store.finished[-1][1]["amount_usd"] == pytest.approx(0.08)
    agent_loop.paid_void(ctx, ["g1", "g3"])
    assert ctx.budget.used.credits == pytest.approx(0.0)
    assert ctx.paid["s1:a"]["status"] == "void"
    assert ctx.store.finished[-1][1]["status"] == "void" and ctx.store.finished[-1][1]["amount_usd"] == 0.0


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_one_failed_image_of_a_confirmed_step_retries_once_without_a_new_charge(monkeypatch, budget):
    from test_agent_budget_391 import calls, reply
    first = [_call("1:1") for _ in range(3)]
    retry = dict(first[0])  # same quoted image again: the confirmed card covers it
    state = {"gens": 0}

    def script(messages, n):
        steps = [
            [("generate_image", a) for a in first],
            [("wait_generation", {"ids": ["g-1", "g-2", "g-3"]})],
            [("generate_image", retry)],
            [("wait_generation", {"ids": ["g-4"]})],
        ]
        if n < len(steps):
            out = calls(*steps[n])
            for tc in out["choices"][0]["message"]["tool_calls"]:
                tc["id"] = f"r{n}-{tc['id']}"
            return out
        return reply("完成")

    rig, seen = _rig(monkeypatch, [], budget=budget)
    rig.script = script

    def mcp(name, args, i):
        if name == "generate_image":
            state["gens"] += 1
            return json.dumps({"ids": [f"g-{state['gens']}"]})
        rows = []
        for gid in args.get("ids", []):
            rows.append({"id": gid, "status": "error", "error": "生成失败，已退款", "charged": True, "refunded": True}
                        if gid == "g-1" else {"id": gid, "status": "done", "placed": True})
        return json.dumps(_wait(rows))

    rig_mcp_calls = rig.mcp
    # _rig built the provider with its own mcp stub; swap in this scenario's.
    async def fake_call(session, endpoint, name, arguments):
        rig_mcp_calls.append((name, dict(arguments)))
        return mcp(name, arguments, len(rig_mcp_calls)), []

    monkeypatch.setattr(rig.p, "_mcp_call_tool", fake_call)
    trackers = []
    orig = ProgressTracker.over_budget

    def spy(self, obs):
        trackers.append(self)
        return orig(self, obs)

    monkeypatch.setattr(ProgressTracker, "over_budget", spy)
    res, _events = await rig.send("做一个品牌", goal="")
    assert len(rig.paid_mcp()) == 4, "three images plus exactly one retry"
    assert len(seen) == 1, "the retry is covered by the confirmed card: no second charge prompt"
    assert not (res.error or "")
    if budget:
        t = trackers[-1]
        assert t.voided == ["g-1"]
        assert t.gen_calls == 3, "the void image's unit was given back; the retry took it, not a fourth"


# ---------------------------------------------------------------- narrowed requote

@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_requote_prices_only_the_steps_not_yet_submitted(monkeypatch, budget):
    """Image A is sent under its own Start. A later batch lists A, B, C again. When that batch's card
    expires, the new card quotes B and C only, and A is not sent a second time."""
    from test_agent_budget_391 import calls, reply
    a, b, c = _call("1:1"), _call("1:1"), _call("1:1")

    def script(messages, n):
        steps = [
            [("generate_image", a)],
            [("generate_image", a), ("generate_image", b), ("generate_image", c)],
        ]
        if n < len(steps):
            out = calls(*steps[n])
            for tc in out["choices"][0]["message"]["tool_calls"]:
                tc["id"] = f"q{n}-{tc['id']}"
            return out
        return reply("完成")

    rig, _unused = _rig(monkeypatch, [], budget=budget)
    rig.script = script
    cards: list = []
    quoted: list = []

    async def confirm(spec, turn, handle, **_kw):
        cards.append(spec)
        return "expired" if len(cards) == 2 else "start"

    monkeypatch.setattr(rig.p, "_confirm_plan", confirm)
    real = rig.p._quote_steps

    async def spy(steps, lang):
        quoted.append(len(steps))
        return await real(steps, lang)

    monkeypatch.setattr(rig.p, "_quote_steps", spy)
    await rig.send("做一个品牌", goal="")
    # card 1: image A. card 2: A, B, C (expired). card 3: B and C only.
    assert len(cards) == 3
    assert len(cards[0]["lines"]) == 1 and len(cards[1]["lines"]) == 3 and len(cards[2]["lines"]) == 2
    sent = [args["prompt"] for _n, args in rig.paid_mcp()]
    assert sent.count(a["prompt"]) == 1, "A was submitted once, under its own Start"
    assert b["prompt"] in sent and c["prompt"] in sent
    assert len(sent) == 3


# ---------------------------------------------------------------- explicit charged flag

def test_charged_reads_the_explicit_flag_before_the_status():
    assert paid_guard.charged({"error": "noise", "charged": True}) is True
    assert paid_guard.charged({"status": "failed", "charged": True, "refunded": False}) is True
    assert paid_guard.charged({"status": "failed", "charged": False}) is False
    assert paid_guard.charged({"status": "failed"}) is False       # no flag: status decides
    assert paid_guard.charged({"error": "x"}) is False
    assert paid_guard.charged({"ids": ["g"]}) is True
    assert paid_guard.charged(json.dumps({"error": "x", "charged": True})) is True


def test_a_charged_failure_counts_toward_the_cap_and_is_not_given_back():
    cid = "charged-failure"
    guard = paid_guard.begin_turn(cid, text="做 1 张", provider_text="做 1 张", lang="zh")
    try:
        # The call itself came back as a failure that kept the charge (noise rejected after billing).
        paid_guard.after_call(cid, "generate_image", {"count": 1},
                              {"status": "failed", "error": "noise", "charged": True}, True)
        assert guard.used[guard.plan_item] == 1
        assert paid_guard.before_call(cid, "generate_image", {"count": 1}), "no free retry on a kept charge"
    finally:
        paid_guard.end_turn(cid)


# ---------------------------------------------------------------- fallback needs its own card

from test_model_fallback_236 import FLARE, PORTRAIT, SEEDREAM, _gens, _turn, page  # noqa: E402,F401
from ComfyArt.bot.local_llm import LocalLlmProvider  # noqa: E402


@pytest.mark.parametrize("answer, models", [("start", [SEEDREAM, FLARE]), ("cancel", [SEEDREAM]),
                                            ("expired", [SEEDREAM])])
async def test_fallback_model_switch_gets_a_new_card_and_submits_only_after_start(monkeypatch, page, answer, models):
    cards: list = []

    async def confirm(self, spec, turn, handle, **_kw):
        cards.append(spec)
        # The first card (the original submit) is approved; the switched model's card gets `answer`.
        return "start" if len(cards) == 1 else answer

    monkeypatch.setattr(LocalLlmProvider, "_threshold", lambda self: 0.0)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", confirm)
    await _turn(monkeypatch, [("generate_image", {"prompt": PORTRAIT})], user_text="画写实人像")
    assert [a.get("model") for a in _gens(page)] == models
    assert len(cards) == 2, "the failed call's confirmation is not reused for the switched model"
    assert cards[0].get("confirmation_id") is None or cards[0] is not cards[1]


# ---------------------------------------------------------------- approved quote_plan releases its calls

@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_approved_quote_plan_releases_exactly_the_quoted_calls(monkeypatch, budget):
    """QA ff7386b2 loop: quote_plan lists the model's own arguments; the tool call gets the skill's
    sizes and model pin filled in. The approved plan must still match that call (no refusal, no
    second identical card), and a call that was not quoted is still refused."""
    from ComfyArt.bot.local_llm import _PLAN_REFUSE
    from test_agent_budget_391 import calls, reply
    mood, logo1, logo2, stray = _call("16:9"), _call("1:1"), _call("1:1"), _call("1:1")

    def plan(*items):
        return {"steps": [{"text": f"step {i}", "tool": "generate_image", "arguments": a}
                          for i, a in enumerate(items)]}

    def script(messages, n):
        steps = [
            [("quote_plan", plan(mood))],
            [("generate_image", mood)],
            [("quote_plan", plan(logo1, logo2))],
            [("generate_image", logo1), ("generate_image", logo2)],
            [("generate_image", stray)],  # never quoted: the strict gate refuses it
        ]
        if n < len(steps):
            out = calls(*steps[n])
            for tc in out["choices"][0]["message"]["tool_calls"]:
                tc["id"] = f"p{n}-{tc['id']}"
            return out
        return reply("完成")

    rig, cards = _rig(monkeypatch, [], budget=budget)
    rig.script = script
    priced = []
    real = rig.p._quote_steps

    async def spy(steps, lang):
        priced.append([s.get("model") for s in steps])
        return await real(steps, lang)

    monkeypatch.setattr(rig.p, "_quote_steps", spy)
    _res, events = await rig.send("做一个品牌", goal="")
    sent = [args["prompt"] for _n, args in rig.paid_mcp()]
    assert sent == [mood["prompt"], logo1["prompt"], logo2["prompt"]], "approved calls run; the unquoted one does not"
    assert len(cards) == 2, "one card per quote_plan, never re-issued in a loop"
    results = [e.text for e in events if e.t == "tool_result" and e.text]
    assert sum(_PLAN_REFUSE["zh"] in r or _PLAN_REFUSE["en"] in r for r in results) == 1
    # Ratio-only calls are not pinned to Qwen. The card names the model that will run.
    from ComfyArt.api.auto_models import short_name
    from ComfyArt.api.mcp_tools.canvas import quote_route
    from ComfyArt.bot.skill_output import OUTPUTS, apply_generate
    prepared = apply_generate(dict(mood), SKILL, user_text="做一个品牌")
    routed, _inputs = quote_route("generate_image", prepared, user_text="做一个品牌")
    qwen = OUTPUTS[SKILL]["exact_size_models"]["t2i"]
    assert routed and routed != qwen
    assert all(m != qwen for models in priced for m in models), priced
    label = short_name(routed)
    assert cards and all(label in line["text"] for line in cards[0]["lines"])


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_staged_task_quotes_and_releases_one_segment_at_a_time(monkeypatch, budget):
    """Product ruling (#1027): a staged task is not forced to quote the whole run. Segment 1
    (moodboard) is quoted, started and dispatched on the next LLM step; the user answers a card;
    segment 2 (three directions) is quoted, started and dispatched. Two different cards, no
    repeated card, no plan-gate refusal. The calls carry `skill` like the real agent's do."""
    import json as _json
    from ComfyArt.bot.local_llm import _PLAN_REFUSE
    from test_agent_budget_391 import calls, reply
    mood = _call("16:9")
    logos = [_call("1:1"), _call("1:1"), _call("1:1")]
    ask = {"questions": [{"id": "pick", "prompt": "情绪板方向可以吗？", "page": 1,
                          "options": [{"id": "A", "label": "可以"}, {"id": "B", "label": "再调"}]}]}

    def plan(*items):
        return {"steps": [{"text": f"step {i}", "tool": "generate_image", "arguments": a}
                          for i, a in enumerate(items)]}

    def script(messages, n):
        steps = [
            [("quote_plan", plan(mood))],                       # segment 1 quote
            [("generate_image", mood)],                         # next LLM step after Start
            [("ask_user", ask)],                                # the card that segment 2 depends on
            [("quote_plan", plan(*logos))],                     # segment 2 quote
            [(("generate_image", a)) for a in logos],           # next LLM step after Start
        ]
        if n < len(steps):
            out = calls(*steps[n])
            for tc in out["choices"][0]["message"]["tool_calls"]:
                tc["id"] = f"s{n}-{tc['id']}"
            return out
        return reply("完成")

    rig, cards = _rig(monkeypatch, [], budget=budget)
    rig.script = script

    async def fake_call(session, endpoint, name, arguments):
        rig.mcp.append((name, dict(arguments)))
        if name == "ask_user":
            return _json.dumps({"status": "answered", "answers": {"pick": {"selected": ["A"]}}}), []
        return _json.dumps({"ids": [f"h-{len(rig.mcp)}"]}), []

    monkeypatch.setattr(rig.p, "_mcp_call_tool", fake_call)
    _res, events = await rig.send("做一个品牌", goal="")
    names = [n for n, _a in rig.mcp]
    sent = [args["prompt"] for _n, args in rig.paid_mcp()]
    assert sent == [mood["prompt"]] + [a["prompt"] for a in logos]
    assert names.index("ask_user") < [i for i, n in enumerate(names) if n == "generate_image"][1], \
        "segment 2 runs only after the card is answered"
    assert len(cards) == 2, "one card per segment"
    assert _json.dumps(cards[0], sort_keys=True, default=str) != _json.dumps(cards[1], sort_keys=True, default=str)
    results = [e.text for e in events if e.t == "tool_result" and e.text]
    assert not any(_PLAN_REFUSE["zh"] in r or _PLAN_REFUSE["en"] in r for r in results)
