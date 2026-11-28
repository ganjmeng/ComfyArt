"""First quote persists the plan and the setup snapshot; Start may submit.

Real LocalLlmProvider.send, real quote_detail, offline HTTP stand-in only.
No server, no image, no ledger file, no credential.
"""
from __future__ import annotations

import copy

import aiohttp
import pytest

from multi_angle_plan_fixture import HEADPHONES_PLAN

from ComfyArt.api import bot_asks, bot_turns, chat_store, multi_angle as ma, paid_guard, wavespeed
from ComfyArt.api.mcp_tools import bot_tools, canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest
from test_agent_budget_391 import calls, reply
from test_multi_angle_stages_911 import DESC, REF

PREVIEW = {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "refs": [REF],
           "multi_angle_stage": "preview"}
QUOTE_GATE = "确认报价"


class _Response:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = payload

    async def json(self, content_type=None):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    def __init__(self, records, catalog, mode):
        self.records = records
        self.catalog = catalog
        self.mode = mode

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        self.records.append(("GET", str(url).split("?", 1)[0], None))
        if not str(url).endswith("/api/v3/models"):
            raise aiohttp.ClientError("unexpected catalog request")
        return _Response(200, {"data": [self.catalog]})

    def post(self, url, **kwargs):
        body = kwargs.get("json")
        self.records.append(("POST", str(url).split("?", 1)[0], copy.deepcopy(body)))
        if not str(url).endswith("/api/v3/model/price"):
            raise aiohttp.ClientError("unexpected price request")
        if self.mode == "transport":
            raise aiohttp.ClientError("offline transport")
        if self.mode == "error":
            return _Response(200, {"code": 4005, "data": {}})
        return _Response(200, {"code": 200, "data": {"discounted_price": 0.1, "price": 0.2}})


def _session_factory(records, catalog, mode):
    def factory(*args, **kwargs):
        return _Session(records, catalog, mode)
    return factory


def _clear_price_cache():
    wavespeed._catalog["models"] = {}
    wavespeed._catalog["at"] = 0.0
    wavespeed._catalog.pop("stale", None)
    wavespeed._quotes.clear()


async def _send(monkeypatch, *, mode="quote", choice="start", change_before_start=False,
               generate=True, through_second_quote=False, finals=None, second_choice="start",
               duplicate=False, extra_id="", selected=None, wait_finals=False, drop_before_wait=False,
               fail_panel="", timeout_panel=""):
    _clear_price_cache()
    model_id = wavespeed.load_config()["features"]["image_edit"]["default"]
    catalog = {
        "model_id": model_id,
        "base_price": 0.2,
        "api_schema": {"api_schemas": [{"request_schema": {"properties": {
            "images": {"type": "array"},
            "size": {"type": "string"},
        }}}]},
    }
    records = []
    sent = []
    seen_setup = []
    tools = []
    chat = chat_store.create_chat(user="default", project="quote-snapshot-1029", provider="local-llm")
    cid = chat["id"]
    chat_store.create_message(chat_id=cid, role="user", blocks=[
        {"type": "skill", "name": ma.SKILL}, {"type": "text", "text": DESC},
        {"type": "image", "url": REF}])
    assistant = chat_store.create_message(chat_id=cid, role="assistant", blocks=[], status="running")
    handle = TurnHandle()
    state = bot_turns._TurnState(handle, cid, assistant["id"])
    monkeypatch.setitem(bot_turns.ACTIVE_TURNS, cid, state)
    panels = list(finals) if finals is not None else (["1"] if through_second_quote else None)
    script = [calls(("ask_user", {"prompt": "setup"}))]
    if generate:
        script.append(calls(("generate_image", PREVIEW)))
    if panels is not None:
        final_calls = [("generate_image", {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                            "refs": [REF], "multi_angle_stage": "final",
                                            "composition_id": panel}) for panel in panels]
        if duplicate and panels:
            final_calls.append(final_calls[0])
        if extra_id:
            final_calls.append(("generate_image", {"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL,
                                                    "refs": [REF], "multi_angle_stage": "final",
                                                    "composition_id": extra_id}))
        script += [
            calls(("wait_generation", {"ids": ["holder:1"]})),
            calls(("ask_user", {"prompt": "compositions"})),
            calls(*final_calls),
        ]
        if drop_before_wait:
            script.append("DROP")
        if wait_finals:
            holders = [f"holder:{index + 2}" for index in range(len(panels))]
            script.append(calls(("wait_generation", {"ids": holders})))
    script.append(reply("done"))
    provider = LocalLlmProvider(base_url=lambda: "http://mock-no-network/v1")
    seen = {"n": 0}
    quotes_seen = {"n": 0}

    from ComfyArt.api import mcp

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        body = json_body or {}
        rpc = body.get("method")
        if rpc == "tools/list":
            return {"result": {"tools": [{"name": n, "inputSchema": {"type": "object", "properties": {}}}
                                          for n in ("ask_user", "generate_image", "wait_generation")]}}
        if rpc == "tools/call":
            params = body.get("params") or {}
            name = params.get("name")
            out = await mcp._tools_call({"name": name, "arguments": params.get("arguments") or {}})
            text = next((b.get("text") for b in (out or {}).get("content") or [] if b.get("type") == "text"), "")
            tools.append((name, text))
            return {"result": out or {"content": [{"type": "text", "text": ""}], "isError": True}}
        if not str(url).endswith("/chat/completions"):
            return {"data": [{"id": "mock-1029", "context_length": 32000}]}
        item = script[min(seen["n"], len(script) - 1)]
        seen["n"] += 1
        if item == "DROP":
            raise ConnectionError("offline drop before the next-turn wait")
        return item

    async def page(action, args, project, timeout, chat=""):
        sent.append((action, copy.deepcopy(args)))
        if action == "generate_image" and timeout_panel:
            gen_n = sum(1 for kind, _args in sent if kind == "generate_image")
            if gen_n == 2:
                raise TimeoutError("transport timeout")
        if action == "wait_generation":
            from multi_angle_plan_fixture import preview_url
            failed_ids = set()
            if fail_panel:
                token_now = BOT_CHAT_ID.set(cid)
                try:
                    entry = (ma._root(cid)[1].get(ma.LEDGER) or {}).get("final:" + fail_panel) or {}
                    failed_ids.update(str(i) for i in (entry.get("result") or {}).get("ids") or [])
                finally:
                    BOT_CHAT_ID.reset(token_now)
            rows = []
            for h in args.get("ids") or []:
                if str(h) in failed_ids:
                    rows.append({"id": h, "status": "failed", "generation_succeeded": False,
                                 "error": "injected failure", "placed": False})
                else:
                    rows.append({"id": h, "status": "done", "placed": True, "generation_succeeded": True,
                                 "delivered": 1, "shapes": [f"shape:{h}"], "urls": [preview_url()]})
            return {"results": rows}
        nth = sum(1 for kind, _args in sent if kind == "generate_image")
        return {"ids": [f"holder:{nth}"], "submitted": True}

    def answer_broadcast(event, payload):
        if event != "turn_ask":
            return
        if payload.get("kind") == "plan_quote":
            if change_before_start:
                _retarget_aspect(cid, "4:3")
            quotes_seen["n"] += 1
            this_choice = choice if quotes_seen["n"] == 1 else second_choice
            if this_choice == "start":
                bot_asks.validate_answer(payload, ["start"], "")
                bot_asks.resolve_ask(payload["ask_id"], "answered", selected=["start"])
            elif this_choice == "expired":
                bot_asks.resolve_ask(payload["ask_id"], "expired")
            else:
                bot_asks.validate_answer(payload, ["cancel"], "")
                bot_asks.resolve_ask(payload["ask_id"], "cancelled", selected=["cancel"])
            return
        ids = {q.get("id") for q in payload.get("questions") or []}
        if ma.COMPOSITIONS in ids:
            answers = {ma.COMPOSITIONS: {"selected": list(selected or panels or ["1"])}}
            bot_asks.validate_answer(payload, [], "", answers)
            bot_asks.resolve_ask(payload["ask_id"], "answered", answers=answers)
            return
        seen_setup.append(payload)
        answers = {ma.SOURCE: {"selected": ["single_front"]}, ma.ASPECT: {"selected": ["1:1"]}}
        bot_asks.validate_answer(payload, [], "", answers)
        bot_asks.resolve_ask(payload["ask_id"], "answered", answers=answers)

    events = []

    async def emit(event):
        events.append(event)

    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", _session_factory(records, catalog, mode))
    monkeypatch.setattr(wavespeed, "_key", lambda: "offline-stand-in")
    # #1019 no-key branch quotes from the table without the price API; this stand-in has a key.
    monkeypatch.setattr(wavespeed, "has_key", lambda: True)
    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(bot_tools, "broadcast", answer_broadcast)
    monkeypatch.setattr(canvas, "submit_command", page)
    token = BOT_CHAT_ID.set(cid)
    paid_guard.begin_turn(cid, text=DESC, provider_text=DESC)
    dropped = None
    previous_store = None
    if drop_before_wait:
        from ComfyArt.api.run_store_sqlite import SqliteRunStore
        from ComfyArt.bot.run_store import get_run_store, set_run_store
        previous_store = get_run_store()
        set_run_store(SqliteRunStore())
    try:
        result = await provider.send(TurnRequest(
            chat_id=cid,
            user_text=f"Use the ComfyArt skill '{ma.SKILL}' for this task. {DESC}",
            goal_text=DESC, lang="zh", mcp_endpoint="http://mock-no-network/mcp", model="mock-1029"),
            emit, handle)
        if drop_before_wait:
            dropped = result
            run_id = str((getattr(result, "run", None) or {}).get("run_id") or "")
            result = await provider.send(TurnRequest(
                chat_id=cid, user_text="", goal_text=DESC, lang="zh",
                mcp_endpoint="http://mock-no-network/mcp", model="mock-1029",
                resume_run_id=run_id), emit, handle)
    finally:
        if drop_before_wait:
            from ComfyArt.bot.run_store import set_run_store
            set_run_store(previous_store)
        paid_guard.end_turn(cid)
        BOT_CHAT_ID.reset(token)
        bot_turns.ACTIVE_TURNS.pop(cid, None)
        bot_asks.cancel_chat_asks(cid)
        _clear_price_cache()
    return {"cid": cid, "sent": sent, "http": records, "result": result, "dropped": dropped,
            "setup": seen_setup, "model_id": model_id, "tools": tools, "events": events}


def _retarget_aspect(cid: str, aspect: str) -> None:
    state = bot_turns.ACTIVE_TURNS.get(cid)
    if state is not None:
        for block in state.blocks:
            answers = block.get("answers") or {}
            if isinstance(answers.get(ma.ASPECT), dict):
                answers[ma.ASPECT]["selected"] = [aspect]
    for row in chat_store.list_messages(cid):
        blocks = copy.deepcopy(row.get("blocks") or [])
        changed = False
        for block in blocks:
            answers = block.get("answers") or {}
            if isinstance(answers.get(ma.ASPECT), dict):
                answers[ma.ASPECT]["selected"] = [aspect]
                changed = True
        if changed:
            chat_store.update_message(cid, row["id"], blocks=blocks)


def _posts(records):
    return [item for item in records if item[0] == "POST"]


def _gets(records):
    return [item for item in records if item[0] == "GET"]


@pytest.mark.asyncio
async def test_real_send_confirmed_start_submits_one_preview(monkeypatch):
    out = await _send(monkeypatch)
    gets, posts = _gets(out["http"]), _posts(out["http"])
    assert len(gets) == 1 and gets[0][1].endswith("/api/v3/models")
    assert len(posts) == 1 and posts[0][1].endswith("/api/v3/model/price")
    assert set(posts[0][2]) == {"model_id", "input"}
    assert isinstance(posts[0][2]["input"], dict)
    assert posts[0][2]["model_id"] == out["model_id"]
    setup = out["setup"][0]
    source, aspect = setup["questions"]
    assert source["id"] == ma.SOURCE and aspect["id"] == ma.ASPECT
    assert not source.get("defaults") and not aspect.get("defaults")
    assert aspect["allow_other"] is False and source["allow_other"] is True
    assert all(not q.get("selected") for q in setup["questions"])
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        root = ma._root(out["cid"])[1]
        ledger = root[ma.LEDGER]
        assert root["answers"][ma.SOURCE]["selected"] == ["single_front"]
        panels = ledger["composition_plan"]["panels"]
        assert len(panels) == 9 and all(panel.get("content") for panel in panels)
        assert ledger["setup_snapshot"]["aspect"]["selected"] == ["1:1"]
        preview = ledger["setup_snapshot"]["preview"]
        assert (preview["width"], preview["height"], preview["ratio"]) == (1152, 2048, "9:16")
        quotes = [b for row in chat_store.list_messages(out["cid"]) for b in row["blocks"]
                  if b.get("kind") == "plan_quote"]
        assert quotes and quotes[-1]["status"] == "answered"
        assert all(line["source"] == "quote" for line in quotes[-1]["lines"])
    finally:
        BOT_CHAT_ID.reset(token)
    assert len(out["sent"]) == 1, (out["tools"], getattr(out["result"], "error", None))
    page = out["sent"][0][1]
    assert (page["width"], page["height"], page["ratio"]) == (1152, 2048, "9:16")
    assert (page.get("edit_model") or page.get("model")) == out["model_id"]
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        _retarget_aspect(out["cid"], "3:4")
        blocked = await canvas._relay("generate_image")(dict(PREVIEW))
    finally:
        BOT_CHAT_ID.reset(token)
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]
    assert len(out["sent"]) == 1


@pytest.mark.asyncio
async def test_real_send_reaches_composition_selection_and_second_quote(monkeypatch):
    """Default send continues: preview, composition answer, then the finals quote."""
    out = await _send(monkeypatch, through_second_quote=True)
    posts = _posts(out["http"])
    assert len(_gets(out["http"])) == 1
    assert len(posts) == 2, posts
    assert all(set(body) == {"model_id", "input"} and isinstance(body["input"], dict)
               for _method, _url, body in posts)
    assert posts[0][2] != posts[1][2]
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        rows = chat_store.list_messages(out["cid"])
        quotes = [b for row in rows for b in row["blocks"] if b.get("kind") == "plan_quote"]
        compositions = [b for row in rows for b in row["blocks"]
                        if any(q.get("id") == ma.COMPOSITIONS for q in b.get("questions") or [])]
        ledger = ma._root(out["cid"])[1][ma.LEDGER]
    finally:
        BOT_CHAT_ID.reset(token)
    assert len(quotes) == 2, out["tools"]
    assert all(q["status"] == "answered" and q.get("selected") == ["start"] for q in quotes)
    assert all(line["source"] == "quote" for q in quotes for line in q["lines"])
    assert compositions and compositions[-1]["status"] == "answered"
    assert compositions[-1]["answers"][ma.COMPOSITIONS]["selected"] == ["1"]
    assert ledger["preview"].get("delivered") is True
    assert ledger["setup_snapshot"]["aspect"]["selected"] == ["1:1"]
    generates = [args for action, args in out["sent"] if action == "generate_image"]
    assert len(generates) == 2, out["tools"]
    assert (generates[0]["width"], generates[0]["height"], generates[0]["ratio"]) == (1152, 2048, "9:16")
    assert (generates[1]["width"], generates[1]["height"], generates[1]["ratio"]) == (2048, 2048, "1:1")
    assert len(generates[1]["refs"]) == 2


@pytest.mark.asyncio
async def test_changed_aspect_before_start_does_not_submit(monkeypatch):
    out = await _send(monkeypatch, change_before_start=True)
    assert out["sent"] == [], out["tools"]
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        blocked = await canvas._relay("generate_image")(dict(PREVIEW))
    finally:
        BOT_CHAT_ID.reset(token)
    assert blocked["submitted"] is False and "changed after submission" in blocked["error"]
    assert QUOTE_GATE not in blocked["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("choice", ["cancel", "expired"])
async def test_cancel_or_expired_quote_submits_nothing(monkeypatch, choice):
    # #1027: an expired card is re-issued as a new card; here that new card is cancelled, so
    # neither card submits anything. (Start on the new card submits: see test_requote_and_void_1027.)
    out = await _send(monkeypatch, choice=choice, second_choice="cancel")
    assert out["sent"] == []
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        blocked = await canvas._relay("generate_image")(dict(PREVIEW))
    finally:
        BOT_CHAT_ID.reset(token)
    assert blocked["submitted"] is False and out["sent"] == []
    assert QUOTE_GATE in blocked["error"]
    assert "changed after submission" not in blocked["error"]


@pytest.mark.asyncio
async def test_no_quote_card_does_not_submit(monkeypatch):
    out = await _send(monkeypatch, generate=False)
    assert out["http"] == [] and out["sent"] == []
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        blocked = await canvas._relay("generate_image")(dict(PREVIEW))
    finally:
        BOT_CHAT_ID.reset(token)
    assert blocked["submitted"] is False and out["sent"] == []
    assert QUOTE_GATE in blocked["error"]
    assert "changed after submission" not in blocked["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,posts", [("error", 1), ("transport", 2)])
async def test_failed_price_estimate_is_not_a_confirmed_quote(monkeypatch, mode, posts):
    out = await _send(monkeypatch, mode=mode)
    assert len(_gets(out["http"])) == 1
    assert len(_posts(out["http"])) == posts
    assert all(set(item[2]) == {"model_id", "input"} and isinstance(item[2]["input"], dict)
               for item in _posts(out["http"]))
    assert out["sent"] == []
    token = BOT_CHAT_ID.set(out["cid"])
    try:
        quotes = [b for row in chat_store.list_messages(out["cid"]) for b in row["blocks"]
                  if b.get("kind") == "plan_quote"]
        assert quotes and quotes[-1]["lines"][0]["source"] == "estimate"
        ledger = ma._root(out["cid"])[1][ma.LEDGER]
        assert ledger.get("composition_plan") and "preview" not in ledger
        blocked = await canvas._relay("generate_image")(dict(PREVIEW))
    finally:
        BOT_CHAT_ID.reset(token)
    assert blocked["submitted"] is False and out["sent"] == []
    assert QUOTE_GATE in blocked["error"]
    assert "changed after submission" not in blocked["error"]
