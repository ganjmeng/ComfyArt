"""#1002 / Refs #911: real stages with durable mocked chat + canvas dispatch. NO network or browser.

Fixture: gray headphones, 商品详情页，纯白无缝背景; preview uses the selected
setup-card aspect (default 1:1 -> 2048x2048), then selected 1/2/3 -> three 2048
squares. Measurements are not defaults.
"""
from __future__ import annotations

import copy

import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN, preview_url

from ComfyArt.api import bot_asks, bot_turns, chat_store, multi_angle as ma
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.skill_output import apply_generate

REF = "/api/view?filename=ma_subject_691.png&type=input"
DESC = "商品详情页，纯白无缝背景"


@pytest.fixture
def run(monkeypatch):
    rows = [{"id": "start", "role": "user", "blocks": [
        {"type": "skill", "name": ma.SKILL}, {"type": "text", "text": DESC},
        {"type": "image", "url": REF}]}]
    sent = []

    def update(chat, message, **fields):
        row = next(r for r in rows if r["id"] == message)
        row.update(copy.deepcopy(fields))
        return copy.deepcopy(row)

    def compare(chat, message, expected, blocks):
        row = next(r for r in rows if r["id"] == message)
        if row["blocks"] != expected:
            return False
        update(chat, message, blocks=blocks)
        return True

    async def submit(action, args, project, timeout, chat=""):
        sent.append((action, copy.deepcopy(args)))
        return {"ids": [f"holder:{len(sent)}"], "submitted": True}

    async def approval(label):
        return None

    monkeypatch.setattr(chat_store, "list_messages", lambda chat: copy.deepcopy(rows))
    monkeypatch.setattr(chat_store, "update_message", update)
    monkeypatch.setattr(chat_store, "compare_message_blocks", compare)
    monkeypatch.setattr(bot_turns, "ACTIVE_TURNS", {})
    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", approval)
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: None)
    monkeypatch.setattr(canvas, "unregistered_model", lambda *a: None)
    monkeypatch.setattr(canvas, "load_config", lambda: {"features": {}})
    token = BOT_CHAT_ID.set("chat-ma")
    try:
        yield rows, sent
    finally:
        BOT_CHAT_ID.reset(token)


def setup(rows, aspect="1:1", *, status="answered", source="single_front"):
    spec = bot_asks.validate_spec({"prompt": "setup"})
    block = {"type": "ask", "ask_id": "setup", "status": status, **spec, "answers": {
        ma.SOURCE: {"selected": [source]}, ma.ASPECT: {"selected": [aspect]}}}
    rows.append({"id": "setup-msg", "role": "assistant", "blocks": [block]})
    return block


def confirm_quote(rows, *, status="answered", selected=("start",)):
    """Mark the existing plan_quote / run_approval path as confirmed (no new UI)."""
    block = {"type": "ask", "ask_id": "quote", "status": status, "kind": "plan_quote",
             "prompt": "Start?", "options": [{"id": "start", "label": "Start"},
                                            {"id": "cancel", "label": "Cancel"}],
             "selected": list(selected),
             "answers": {"q": {"selected": list(selected)}}}
    rows.append({"id": "quote-msg", "role": "assistant", "blocks": [block]})
    return block


def choose(rows, selected=("1", "2", "3"), *, status="answered", other=""):
    spec = bot_asks.validate_spec({"prompt": "choose compositions"})
    block = {"type": "ask", "ask_id": "compositions", "status": status, **spec, "answers": {
        ma.COMPOSITIONS: {"selected": list(selected), "other_text": other}}}
    rows.append({"id": "composition-msg", "role": "assistant", "blocks": [block]})
    return block


def preview(rows, *, aspect="1:1"):
    setup(rows, aspect)
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None
    meta = args["_multi_angle"]
    assert ma.reserve(meta) is None
    ma.submitted(meta, {"ids": ["preview-holder"], "submitted": True})
    ma.record_wait({"results": [{"id": "preview-holder", "status": "done", "placed": True, "shapes": ["preview-shape"],
                                 "urls": [preview_url()]}]})
    return args


def test_setup_card_uses_existing_pager_without_preselect_or_reupload(run):
    rows, _ = run
    # Both questions are present even when a reference is already attached.
    card = bot_asks.validate_spec({"prompt": "setup"})
    assert [q["id"] for q in card["questions"]] == [ma.SOURCE, ma.ASPECT]
    assert card["page_count"] == 1 and card["allow_skip"] is True
    assert all(not q.get("defaults") for q in card["questions"])
    assert [o["id"] for o in card["questions"][1]["options"]] == list(ma.CARD_ASPECTS)
    setup(rows, status="pending")
    with pytest.raises(ValueError, match="existing"):
        bot_asks.validate_spec({"prompt": "setup again"})


@pytest.mark.parametrize("status", [None, "pending", "expired", "cancelled"])
@pytest.mark.asyncio
async def test_no_generate_before_setup_answer(run, status):
    rows, sent = run
    if status:
        setup(rows, status=status)
    result = await canvas._relay("generate_image")({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "prompt": "bypass"})
    assert result["submitted"] is False and result["kind"] == "multiAngleStage"
    assert sent == []


def test_preview_has_numbered_nine_panel_lineart_and_keeps_input(run):
    rows, sent = run
    args = preview(rows)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == (1152, 2048, "9:16", 1)
    assert args["refs"] == [REF] and args["ref_modes"] == ["content"]
    assert DESC not in args["prompt"]  # product: raw brief is final-only
    assert args["_multi_angle"]["description"] == DESC
    assert args["_multi_angle"]["source"] == "single_front"
    assert "ONE lineart preview" in args["prompt"] and "3x3 nine-panel" in args["prompt"]
    assert all(f"{i}:" in args["prompt"] for i in range(1, 10))
    card = bot_asks.validate_spec({"prompt": "choose"})
    assert card["questions"][0]["id"] == ma.COMPOSITIONS
    assert card["questions"][0]["max_selections"] == 9
    assert sent == []  # the helper only mutates mocked durable state


def test_no_composition_card_until_real_preview_completion(run):
    rows, _ = run
    setup(rows)
    with pytest.raises(ValueError, match="preview"):
        bot_asks.validate_spec({"prompt": "choose early"})
    args, _ = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    ma.reserve(args["_multi_angle"])
    ma.submitted(args["_multi_angle"], {"ids": ["p"]})
    for result in ({"results": []}, {"results": [{"id": "wrong", "shapes": ["s"]}]},
                   {"results": [{"id": "p", "status": "failed", "shapes": ["s"]}]},
                   {"results": [{"id": "p", "status": "running", "shapes": ["s"]}]}):
        ma.record_wait(result)
        with pytest.raises(ValueError, match="preview"):
            bot_asks.validate_spec({"prompt": "choose early"})


@pytest.mark.parametrize("status", [None, "pending", "expired", "cancelled"])
@pytest.mark.asyncio
async def test_unanswered_composition_blocks_paid_final(run, status):
    rows, sent = run
    preview(rows)
    if status:
        choose(rows, status=status)
    result = await canvas._relay("generate_image")({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "1"})
    assert result["submitted"] is False
    assert sent == []


@pytest.mark.parametrize("aspect,expected", [("1:1", (2048, 2048)), ("3:4", (1536, 2048)),
                                            ("16:9", (2048, 1152)), ("4:5", (1638, 2048))])
@pytest.mark.parametrize("ids", [("1",), ("2", "3"), ("1", "2", "3"), ("5", "9", "1", "7")])
def test_variable_final_aspects_counts_and_ids_with_ref_description_retained(run, aspect, expected, ids):
    rows, _ = run
    preview(rows, aspect=aspect)
    choose(rows, ids)
    for panel in ids:
        args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": panel,
                                    "ratio": "3:4", "width": 12, "height": 12, "count": 4, "refs": ["wrong"],
                                    "prompt": "wrong description"})
        assert blocked is None
        assert (args["width"], args["height"]) == expected and args["ratio"] == aspect
        # #1003 23:0x: the selected cell crop replaces the whole delivered grid as the composition ref.
        assert args["count"] == args["n"] == 1 and args["refs"] == [REF, args["_multi_angle"]["composition_crop"]["ref"]]
        assert "preview-shape" not in args["refs"]
        assert args["ref_modes"] == ["content", "composition"]
        assert DESC in args["prompt"] and "wrong description" not in args["prompt"]
        assert f"composition {panel}:" in args["prompt"]
        assert "ONE independent finished image" in args["prompt"]
    assert ma.selection("chat-ma") == list(ids)
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "0"})
    assert blocked["submitted"] is False


def test_selection_dedup_and_custom_number_entry(run):
    rows, _ = run
    preview(rows)
    choose(rows, ("1", "2", "1"), other="2，3、9")
    assert ma.selection("chat-ma") == ["1", "2", "3", "9"]
    with pytest.raises(ValueError, match="existing composition"):
        bot_asks.validate_spec({"prompt": "repeat card"})


@pytest.mark.parametrize("other", ["10", "new angle please", "1 then charge 9"])
def test_invalid_custom_entry_fails_closed(run, other):
    rows, _ = run
    preview(rows)
    choose(rows, (), other=other)
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked["submitted"] is False


@pytest.mark.asyncio
async def test_actual_fixture_dispatch_and_durable_replay_no_duplicate_paid_submit(run):
    rows, sent = run
    setup(rows)
    confirm_quote(rows)
    relay = canvas._relay("generate_image")
    args = {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview", "ratio": "9:16", "prompt": DESC}
    first = await relay(args)
    assert len(sent) == 1
    assert (sent[0][1]["width"], sent[0][1]["height"], sent[0][1]["ratio"]) == (1152, 2048, "9:16")
    # Simulate a fresh turn/process: no module lock/cache, everything comes from stored blocks.
    result = await relay(args)
    assert result["ids"] == first["ids"] and result["multi_angle_replay"]
    assert len(sent) == 1
    ma.record_wait({"results": [{"id": first["ids"][0], "status": "done", "placed": True, "shapes": ["preview"],
                                 "urls": [preview_url()]}]})
    choose(rows)
    for panel in ("1", "2", "3"):
        final = {"multi_angle_stage": "final", "composition_id": panel}  # omitted skill inferred safely
        placed = await relay(final)
        repeated = await relay(final)
        assert repeated["ids"] == placed["ids"]
    assert len(sent) == 4
    assert [(a["width"], a["height"], a["count"]) for _, a in sent[1:]] == [(2048, 2048, 1)] * 3
    assert sent[0][1]["refs"] == [REF]
    assert all(a["refs"][0] == REF and len(a["refs"]) == 2 and "ma-cell" in a["refs"][1] and DESC in a["prompt"] for _, a in sent[1:])
    assert all("preview" not in a["refs"] for _, a in sent[1:])  # #1003: never the whole grid
    assert all("_multi_angle" not in a and "multi_angle_stage" not in a and "composition_id" not in a for _, a in sent)


@pytest.mark.asyncio
async def test_uncertain_timeout_and_explicit_failure_never_resubmit(run, monkeypatch):
    rows, sent = run
    setup(rows)
    confirm_quote(rows)

    async def uncertain(*args, **kwargs):
        sent.append("reserved")
        raise TimeoutError("outcome unknown")

    monkeypatch.setattr(canvas, "submit_command", uncertain)
    args = {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"}
    with pytest.raises(TimeoutError):
        await canvas._relay("generate_image")(args)
    result = await canvas._relay("generate_image")(args)
    assert result["submitted"] is False and len(sent) == 1
    # Explicit failure is also retained; the agent cannot invent a retry/new request id.
    _, root = ma._root("chat-ma")
    ma.submitted({"key": "preview"}, {"status": "failed", "submitted": False})
    again = await canvas._relay("generate_image")(args)
    assert again["status"] == "failed" and len(sent) == 1


def test_reference_required_but_text_only_allowed_and_attached_never_discarded(run):
    rows, _ = run
    rows[0]["blocks"] = [b for b in rows[0]["blocks"] if b["type"] != "image"]
    root = setup(rows)
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None and args["refs"] == []
    root["answers"][ma.SOURCE]["selected"] = ["description"]
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None and args["refs"] == []
    assert DESC not in args["prompt"] and args["_multi_angle"]["description"] == DESC


def test_quote_is_pure_and_matches_submit_stage_size(run, monkeypatch):
    rows, _ = run
    setup(rows, "3:4")
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: {"model": "mock", "auto": True})
    before = copy.deepcopy(rows)
    model, inputs = canvas.quote_route("generate_image", {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "ratio": "9:16"}, catalog={})
    assert model == "mock" and (inputs["width"], inputs["height"], inputs["ratio"]) == (1152, 2048, "9:16")
    assert rows == before
    assert "_multi_angle" not in inputs


def test_current_skill_cannot_be_bypassed_and_new_run_does_not_inherit_ledger(run):
    rows, _ = run
    preview(rows)
    _, blocked = ma.prepare({"skill": "pose-fission", "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked["submitted"] is False
    rows.append({"id": "new-ma", "role": "user", "blocks": [{"type": "skill", "name": ma.SKILL}]})
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert "source/aspect" in blocked["error"]
    assert ma._root("chat-ma") == (None, None)


def test_unrelated_skills_asks_and_size_locks_unchanged(run):
    rows, _ = run
    rows[0]["blocks"] = [{"type": "skill", "name": "pose-fission"}]
    raw = {"skill": "pose-fission", "prompt": "pose"}
    assert ma.prepare(raw) == (raw, None)
    spec = {"prompt": "unrelated", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]}
    assert ma.normalize_card(spec) == spec
    locked = apply_generate(raw)
    assert (locked["width"], locked["height"], locked["count"]) == (1536, 2048, 1)
    approval = {"kind": "run_approval", **spec}
    rows[0]["blocks"] = [{"type": "skill", "name": ma.SKILL}]
    assert ma.normalize_card(approval) == approval


@pytest.mark.asyncio
async def test_two_concurrent_replays_reserve_only_one_submit(run, monkeypatch):
    import asyncio
    rows, sent = run
    setup(rows)
    confirm_quote(rows)
    entered, release = asyncio.Event(), asyncio.Event()

    async def submit(*args, **kwargs):
        sent.append("one")
        entered.set()
        await release.wait()
        return {"ids": ["one-holder"], "submitted": True}

    monkeypatch.setattr(canvas, "submit_command", submit)
    relay = canvas._relay("generate_image")
    args = {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"}
    first = asyncio.create_task(relay(args))
    try:
        await asyncio.wait_for(entered.wait(), timeout=2)
        second = await relay(args)
        assert second["submitted"] is False and len(sent) == 1
    finally:
        release.set()
        await first


@pytest.mark.parametrize("name,description", [("Multi-Angle Image Generator", "PDP, white seamless"),
                                               ("多角度图像生成器", "商品详情页，纯白无缝背景")])
def test_localized_skill_names_and_original_description_propagate(run, name, description):
    rows, _ = run
    rows[0]["blocks"][0]["name"] = name
    rows[0]["blocks"][1]["text"] = description
    preview(rows)
    choose(rows, ("3",))
    args, blocked = ma.prepare({"multi_angle_stage": "final", "composition_id": "3", "prompt": "replacement"})
    assert blocked is None and description in args["prompt"]
    assert "replacement" not in args["prompt"]
    assert args["refs"][0] == REF


def test_reservation_persistence_failure_blocks_dispatch(run, monkeypatch):
    rows, sent = run
    setup(rows)
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None
    monkeypatch.setattr(chat_store, "compare_message_blocks", lambda *a, **k: False)
    with pytest.raises(ValueError, match="persist"):
        ma.reserve(args["_multi_angle"])
    assert sent == []


@pytest.mark.parametrize("expired", ["expired", "cancelled"])
def test_expired_cards_can_be_reasked_without_repeating_paid_preview(run, expired):
    rows, _ = run
    setup(rows, status=expired)
    spec = bot_asks.validate_spec({"prompt": "retry unanswered setup"})
    assert [q["id"] for q in spec["questions"]] == [ma.SOURCE, ma.ASPECT]
    # A fresh setup is the current root, not the earlier expired one.
    rows.append({"id": "new-setup", "role": "assistant", "blocks": [{
        "type": "ask", "ask_id": "new-setup", "status": "answered", **spec,
        "answers": {ma.SOURCE: {"selected": ["single_front"]}, ma.ASPECT: {"selected": ["3:4"]}}}]})
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    assert blocked is None and args["ratio"] == "9:16"
    assert (args["width"], args["height"]) == (1152, 2048)
    assert args["_multi_angle"]["setup_snapshot"]["final"]["ratio"] == "3:4"
    meta = args["_multi_angle"]
    ma.reserve(meta)
    ma.submitted(meta, {"ids": ["preview-once"]})
    ma.record_wait({"results": [{"id": "preview-once", "status": "done", "placed": True, "shapes": ["s"]}]})
    choose(rows, status=expired)
    again = bot_asks.validate_spec({"prompt": "retry unanswered compositions"})
    assert again["questions"][0]["id"] == ma.COMPOSITIONS
    _, replay = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert replay["ids"] == ["preview-once"]


def test_setup_answer_cannot_drift_after_preview_was_reserved(run):
    rows, _ = run
    preview(rows)
    choose(rows)
    rows[1]["blocks"][0]["answers"][ma.ASPECT]["selected"] = ["3:4"]
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]


@pytest.mark.parametrize("overrides", [{"placed": False}, {"generation_succeeded": False}, {"delivered": 0},
                                       {"delivered": 2}, {"shapes": ["one", "two"]}, {"placed": None}])
def test_actual_placed_single_preview_required_not_just_done_status(run, overrides):
    rows, _ = run
    setup(rows)
    args, _ = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    ma.reserve(args["_multi_angle"])
    ma.submitted(args["_multi_angle"], {"ids": ["p"]})
    row = {"id": "p", "status": "done", "placed": True, "shapes": ["s"], **overrides}
    ma.record_wait({"results": [row]})
    with pytest.raises(ValueError, match="preview"):
        bot_asks.validate_spec({"prompt": "cannot choose until actually placed"})


def test_stale_ledger_write_cannot_erase_newer_state(run):
    rows, _ = run
    setup(rows)
    args, _ = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL})
    ma.reserve(args["_multi_angle"])
    before = copy.deepcopy(rows)
    with pytest.raises(ValueError, match="concurrently"):
        ma._save("chat-ma", {"preview": {"status": "new"}}, {})
    assert rows == before


@pytest.mark.asyncio
async def test_positive_app_stack_scripted_agent_real_asks_persistence_and_placements(monkeypatch):
    """#1002 positive backend Full App slice; LLM and page/supplier are mocked.

    Real LocalLlmProvider loop -> MCP dispatcher -> ask futures + SQL chat store
    -> canvas relay -> persisted stage ledger. No browser or external network.
    Four selected finals deliberately exceed the legacy default four paid units
    once the intermediate preview is included.
    """
    import json
    from ComfyArt.api import mcp, paid_guard
    from ComfyArt.api.mcp_tools import bot_tools
    from ComfyArt.bot.local_llm import LocalLlmProvider
    from ComfyArt.bot.providers import TurnHandle, TurnRequest
    from test_agent_budget_391 import calls, reply

    chat = chat_store.create_chat(user="default", project="mock-1002", provider="local-llm")
    cid = chat["id"]
    chat_store.create_message(chat_id=cid, role="user", blocks=[
        {"type": "skill", "name": ma.SKILL}, {"type": "text", "text": DESC},
        {"type": "image", "url": REF}])
    assistant = chat_store.create_message(chat_id=cid, role="assistant", blocks=[], status="running")
    handle = TurnHandle()
    state = bot_turns._TurnState(handle, cid, assistant["id"])
    monkeypatch.setitem(bot_turns.ACTIVE_TURNS, cid, state)
    trace, sent, seen, quote_approvals = [], [], [], []
    holder_shapes = {}
    args_preview = {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "refs": [REF], "multi_angle_stage": "preview"}
    script = [calls(("ask_user", {"prompt": "setup"})),
              calls(("generate_image", args_preview)),
              calls(("wait_generation", {"ids": ["holder:1"]})),
              calls(("ask_user", {"prompt": "compositions"}))]
    for i in range(1, 5):
        script += [calls(("generate_image", {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "refs": [REF],
                          "multi_angle_stage": "final", "composition_id": str(i)})),
                   calls(("wait_generation", {"ids": [f"holder:{i + 1}"]}))]
    script += [reply("已完成所选的四张独立成品。")]
    provider = LocalLlmProvider(base_url=lambda: "http://mock-no-network/v1")

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if (json_body or {}).get("method") == "tools/list":
            return {"result": {"tools": [{"name": n, "inputSchema": {"type": "object", "properties": {}}}
                                          for n in ("ask_user", "generate_image", "wait_generation")]}}
        if not url.endswith("/chat/completions"):
            return {"data": [{"id": "mock-1002", "context_length": 32000}]}
        seen.append(json_body["messages"])
        return script[len(seen) - 1]

    async def real_mcp(session, endpoint, name, arguments):
        trace.append(name)
        out = await mcp._tools_call({"name": name, "arguments": arguments})
        assert out is not None
        return next(b["text"] for b in out["content"] if b["type"] == "text"), []

    async def page_supplier(action, args, project, timeout, chat=""):
        if action == "generate_image":
            sent.append(copy.deepcopy(args))
            holder = f"holder:{len(sent)}"
            holder_shapes[holder] = f"shape:delivered:{len(sent)}"
            return {"ids": [holder], "submitted": True}
        assert action == "wait_generation"
        return {"results": [{"id": h, "status": "done", "placed": True, "generation_succeeded": True,
                             "delivered": 1, "shapes": [holder_shapes[h]],
                             "urls": [preview_url() if h == "holder:1" else f"mock://{h}"]}
                            for h in args["ids"]]}

    def answer_broadcast(event, payload):
        if event != "turn_ask":
            return
        if payload.get("kind") == "plan_quote":
            bot_asks.validate_answer(payload, ["start"], "")
            bot_asks.resolve_ask(payload["ask_id"], "answered", selected=["start"])
            quote_approvals.append(payload["ask_id"])
            return
        questions = payload["questions"]
        ids = {q["id"] for q in questions}
        if ma.ASPECT in ids or ma.SOURCE in ids:
            answers = {ma.ASPECT: {"selected": ["1:1"]}}
            if ma.SOURCE in ids:
                answers[ma.SOURCE] = {"selected": ["single_front"]}
        else:
            answers = {ma.COMPOSITIONS: {"selected": ["1", "2", "3", "4"]}}
        bot_asks.validate_answer(payload, [], "", answers)
        bot_asks.resolve_ask(payload["ask_id"], "answered", answers=answers)

    async def window(*a):
        return 32000

    async def no_price(*a, **k):
        # A missing price is not a Start card. This stack confirms a real quotation.
        return 0.01

    async def no_models(*a):
        return [("mock/edit", 0.01)]

    async def emit(event):
        pass

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", real_mcp)
    monkeypatch.setattr(provider, "_context_window", window)
    monkeypatch.setattr(provider, "_price_call", no_price)
    monkeypatch.setattr(provider, "_price_one", no_price)
    monkeypatch.setattr(provider, "_models_for", no_models)
    monkeypatch.setattr(provider, "_run_store", lambda: None)
    monkeypatch.setattr(bot_tools, "broadcast", answer_broadcast)
    monkeypatch.setattr(canvas, "submit_command", page_supplier)
    monkeypatch.setattr(canvas, "select_model", lambda *a, **k: None)
    monkeypatch.setattr(canvas, "unregistered_model", lambda *a, **k: None)
    monkeypatch.setattr(canvas, "load_config", lambda: {"features": {}})
    token = BOT_CHAT_ID.set(cid)
    paid_guard.begin_turn(cid, text=DESC, provider_text=DESC)
    try:
        result = await provider.send(TurnRequest(chat_id=cid, user_text=f"Use the ComfyArt skill '{ma.SKILL}' for this task. {DESC}",
                                                goal_text=DESC, lang="zh", mcp_endpoint="http://mock-no-network/mcp", model="mock-1002"), emit, handle)
        assert len(sent) == 5, (trace, seen[-1], result)
        assert trace[:4] == ["ask_user", "generate_image", "wait_generation", "ask_user"]
        assert (sent[0]["width"], sent[0]["height"], sent[0]["ratio"]) == (1152, 2048, "9:16")
        assert all((a["width"], a["height"], a["count"]) == (2048, 2048, 1) for a in sent[1:])
        assert all(a["refs"][0] == REF and len(a["refs"]) == 2 and "ma-cell" in a["refs"][1] and DESC in a["prompt"] for a in sent[1:])
        assert all("shape:delivered:1" not in a["refs"] for a in sent[1:])  # #1003: never the whole grid
        stored = chat_store.list_messages(cid)
        asks = [b for row in stored for b in row["blocks"] if b["type"] == "ask" and b.get("kind") == "question"]
        assert quote_approvals, "A priced plan_quote card must be confirmed before generate"
        quote_cards = [b for row in stored for b in row["blocks"] if b.get("kind") == "plan_quote"]
        assert all(b["status"] == "answered" and b["selected"] == ["start"] for b in quote_cards)
        assert len(asks) == 2 and all(a["status"] == "answered" for a in asks)
        ledger = asks[0][ma.LEDGER]
        assert ledger["preview"]["delivered"] is True
        assert all(ledger[f"final:{i}"]["delivered"] for i in range(1, 5))
        # New provider turn, same persisted run: replay returns existing result,
        # without losing state when the original ask-owner turn has ended.
        bot_turns.ACTIVE_TURNS.pop(cid)
        used_before = dict(paid_guard.TURNS[cid].used)
        replay = await mcp._tools_call({"name": "generate_image", "arguments": {
            "composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "4"}})
        again = json.loads(replay["content"][0]["text"])
        assert again["ids"] == ["holder:5"] and len(sent) == 5
        assert paid_guard.TURNS[cid].used == used_before
        # A fresh explicit skill start is different from ordinary continuation.
        chat_store.create_message(chat_id=cid, role="user", blocks=[{"type": "text", "text": "继续核对"}])
        assert ma._root(cid)[1][ma.LEDGER]["preview"]["delivered"]
        chat_store.create_message(chat_id=cid, role="user", blocks=[{"type": "skill", "name": ma.SKILL}])
        assert ma._root(cid) == (None, None)
    finally:
        paid_guard.end_turn(cid)
        BOT_CHAT_ID.reset(token)
        bot_turns.ACTIVE_TURNS.pop(cid, None)
        bot_asks.cancel_chat_asks(cid)


@pytest.mark.parametrize("user_text,selected,expected_cap,blocked", [
    ("继续", ("1", "2", "3", "4", "5", "6", "7", "8", "9"), 9, False),
    ("做3张", ("1", "2", "3"), 4, False),
    ("做3张", ("1", "2", "3", "4"), 3, True),
])
def test_selected_final_cap_resumes_without_changing_other_skill_or_dollar_guards(run, user_text, selected, expected_cap, blocked):
    from ComfyArt.api import paid_guard
    rows, _ = run
    preview(rows)
    choose(rows, selected)
    guard = paid_guard.begin_turn("chat-ma", text=user_text, provider_text=user_text)
    if user_text == "做3张":
        guard.used[guard.plan_item] = 1  # same-turn preview; 3 means three FINAL images
    try:
        args, result = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "1"})
        assert (result is not None) == blocked
        if not blocked:
            ma.allow_selected_cap(args, "chat-ma")
        assert guard.cap == expected_cap
    finally:
        paid_guard.end_turn("chat-ma")


def test_real_sql_compare_and_swap_refuses_stale_paid_reservation():
    chat = chat_store.create_chat(user="default", project="cas-1002", provider="local-llm")
    before = [{"type": "text", "text": "setup"}]
    row = chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=before)
    winner = [{"type": "text", "text": "reserved by first writer"}]
    loser = [{"type": "text", "text": "stale second writer must not overwrite"}]
    assert chat_store.compare_message_blocks(chat["id"], row["id"], before, winner) is True
    assert chat_store.compare_message_blocks(chat["id"], row["id"], before, loser) is False
    assert chat_store.list_messages(chat["id"])[0]["blocks"] == winner
