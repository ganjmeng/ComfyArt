"""#391 EL review (12d24d4) + tester HOLD: one test per defect. Everything mocked: no real LLM, no paid call."""
from __future__ import annotations

import asyncio
import json
import re

import aiohttp
import pytest

from ComfyArt.bot import agent_loop
from ComfyArt.bot.run_budget import SUB_REASONS, StopReason, messages_tokens

from test_agent_budget_391 import Clock, Rig, calls, card, expire_leases, reply, stop_of, store  # noqa: F401

GEN = ("generate_image", {"prompt": "cat", "model": "m"})


def usage_reply(msg, prompt_tokens):
    msg["usage"] = {"prompt_tokens": prompt_tokens, "completion_tokens": 5}
    return msg


# 1. paid dedupe keys on the per-call id, never on params -------------------------------------------------

async def test_same_params_n_generations_give_n_paid_calls_and_n_results(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(GEN, GEN, GEN) if n == 0 else reply("好了"), store=store,
            prices={"generate_image": 0.1}, mcp=lambda name, a, i: json.dumps({"id": f"shape:g{i}"}))
    res, _ = await r.send("画 3 张猫", goal="")
    assert len(r.paid_mcp()) == 3
    paid = [e for e in store.list_usage_events(run_id=res.run["run_id"]) if e["kind"] == "paid_call"]
    assert len(paid) == 3 and {e["status"] for e in paid} == {"done"}
    assert len({e["call_id"] for e in paid}) == 3
    assert res.run["log"]["credits_usd"] == pytest.approx(0.3) and res.run["log"]["paid_calls"] == 3


async def test_same_params_across_steps_are_new_calls(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(GEN) if n < 2 else reply("好了"), store=store,
            prices={"generate_image": 0.1}, mcp=lambda name, a, i: json.dumps({"id": f"shape:g{i}"}))
    res, _ = await r.send("画 2 张猫", goal="")
    assert len(r.paid_mcp()) == 2 and stop_of(res)["reason"] == "done"


# 2. usage event written in the same DB transaction as the pending checkpoint --------------------------------

def test_pending_checkpoint_and_usage_are_one_transaction(store):
    store.create_run(run_id="r1", chat_id="c", message_id="", mode="interactive", goal="")
    assert store.acquire_lease("r1", "me", 60)
    usage = dict(owner_id="local", workspace_id="local", kind="paid_call", tool="generate_image",
                 amount_usd=0.5, call_id="s0:t0", status="pending", reason="test")
    # not our lease: neither the checkpoint nor the usage row is written
    assert store.save_checkpoint_with_usage("r1", "other", status="running", step=1, state={"x": 1}, usage=usage) is None
    assert store.list_usage_events(run_id="r1") == []
    # a failing usage insert rolls back the checkpoint too
    import ComfyArt.api.run_store_sqlite as m
    orig = m.SqliteRunStore._usage_row if hasattr(m.SqliteRunStore, "_usage_row") else None
    boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db"))  # noqa: E731
    if orig is not None:
        m.SqliteRunStore._usage_row = staticmethod(boom)
    else:
        m._usage_row, orig_mod = boom, m._usage_row
    try:
        with pytest.raises(RuntimeError):
            store.save_checkpoint_with_usage("r1", "me", status="running", step=2, state={"x": 2}, usage=usage)
    finally:
        if orig is not None:
            m.SqliteRunStore._usage_row = orig
        else:
            m._usage_row = orig_mod
    assert store.get_run("r1")["step"] != 2 and store.list_usage_events(run_id="r1") == []
    eid = store.save_checkpoint_with_usage("r1", "me", status="running", step=3, state={"x": 3}, usage=usage)
    assert eid is not None and store.get_run("r1")["step"] == 3
    (ev,) = store.list_usage_events(run_id="r1")
    assert (ev["status"], ev["call_id"]) == ("pending", "s0:t0")


async def test_crash_after_pending_leaves_the_pending_usage_row(monkeypatch, store):
    from test_agent_budget_391 import Crash
    r = Rig(monkeypatch, [calls(GEN)], store=store, prices={"generate_image": 0.5}, mcp=lambda n, a, i: Crash())
    with pytest.raises(Crash):
        await r.send("画一张猫")
    (run,) = store.list_runs(chat_id="c")
    (ev,) = [e for e in store.list_usage_events(run_id=run["id"]) if e["kind"] == "paid_call"]
    assert ev["status"] == "pending" and run["state"]["paid"]  # durable together


# 3. heartbeat lease renewal during long calls ----------------------------------------------------------------

async def test_long_call_over_60s_keeps_the_lease(monkeypatch, store):
    now = [10_000.0]
    store._clock = lambda: now[0]
    monkeypatch.setattr(agent_loop.RunContext, "heartbeat_s", lambda self: 0.01)
    r = Rig(monkeypatch, lambda m, n: calls(GEN) if n == 0 else reply("好了"), store=store,
            prices={"generate_image": 0.1})
    stolen = []
    inner = r.p._mcp_call_tool

    async def slow(session, endpoint, name, arguments):
        if name == "generate_image":
            (run,) = store.list_runs(chat_id="c")
            for _ in range(15):          # 150 s of fake time, lease_s = 60
                now[0] += 10
                await asyncio.sleep(0.03)
                stolen.append(store.acquire_lease(run["id"], "intruder", 60))
        return await inner(session, endpoint, name, arguments)
    monkeypatch.setattr(r.p, "_mcp_call_tool", slow)
    res, _ = await r.send("画一张猫", goal="")
    assert stolen and not any(stolen)
    assert stop_of(res)["reason"] == "done"


# 4. restart recovery only touches runs whose lease expired ----------------------------------------------------

def test_restart_pauses_only_expired_leases(store):
    now = [5_000.0]
    store._clock = lambda: now[0]
    for rid in ("live", "dead", "free"):
        store.create_run(run_id=rid, chat_id="c", message_id="", mode="interactive", goal="")
    store.acquire_lease("live", "a", 600)
    store.acquire_lease("dead", "b", 10)
    now[0] += 60
    assert store.mark_interrupted() >= 1
    st = {rid: store.get_run(rid)["status"] for rid in ("live", "dead")}
    assert st == {"live": "running", "dead": "paused"}


# 5. read-only / poll steps are exempt from the repeat rule (still capped at 8) ---------------------------------

def _poll_script(polls):
    wait = ("wait_generation", {"id": "j1"})

    def s(m, n):
        if n == 0:
            return calls(GEN)
        if n <= polls:
            return calls(wait)
        return reply("好了")
    return s


@pytest.mark.parametrize("polls", [3, 8])
async def test_up_to_8_identical_polls_are_not_stuck(monkeypatch, store, polls):
    r = Rig(monkeypatch, _poll_script(polls), store=store, prices={"generate_image": 0.1},
            mcp=lambda n, a, i: json.dumps({"id": "shape:g1"}) if n == "generate_image" else json.dumps({"status": "running"}))
    res, _ = await r.send("画一张猫", goal="")
    assert stop_of(res)["reason"] == "done", stop_of(res)


async def test_more_than_8_polls_is_stuck(monkeypatch, store):
    r = Rig(monkeypatch, _poll_script(20), store=store, prices={"generate_image": 0.1},
            mcp=lambda n, a, i: json.dumps({"id": "shape:g1"}) if n == "generate_image" else json.dumps({"status": "running"}))
    res, _ = await r.send("画一张猫", goal="")
    s = stop_of(res)
    assert (s["reason"], s["sub"]) == ("stuck", "readonly_limit")
    # cap: >8 consecutive read-only steps -> one nudge (counters reset), then stuck on the next 9
    assert res.run["log"]["steps"] == 1 + 9 + 9


# 6. tokens: input + output + reasoning + image, per request -----------------------------------------------------

async def test_billed_tokens_cover_every_request_prompt(monkeypatch, store):
    pts = [1200, 1500, 1900]
    r = Rig(monkeypatch, lambda m, n: usage_reply(calls(("add_text", {"text": f"x{n}"})) if n < 2 else reply("好了"),
                                                  pts[n]), store=store)
    res, _ = await r.send("加字", goal="")
    assert res.run["log"]["tokens"] >= sum(pts)


async def test_billed_tokens_without_provider_usage_count_each_request(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("add_text", {"text": "a"})), calls(("add_text", {"text": "b"})), reply("好了")],
            store=store)
    res, _ = await r.send("加字", goal="")
    assert res.run["log"]["tokens"] >= sum(messages_tokens(m) for m in r.requests)


# enum + copy ----------------------------------------------------------------------------------------------------

def test_stop_enum_is_locked():
    assert {s.value for s in StopReason} == {"done", "budget", "stuck", "hard_cap", "user_stop", "error"}
    assert "self_check_failed" in SUB_REASONS[StopReason.STUCK]
    assert "quote_declined" in SUB_REASONS[StopReason.USER_STOP]
    assert "unattended_skipped" in SUB_REASONS[StopReason.BUDGET]
    flat = json.dumps({k.value: sorted(v) for k, v in SUB_REASONS.items()})
    assert "paid_confirm" not in flat and "stalled" not in flat


LOCKED = {
    "done": ("已完成", "生成了 {n} 张，已放到画布上", None, None),
    "budget": ("预算用完了", "已完成 {n}/{m}，继续大约需要 {x} 积分", "继续", "先到这里"),
    "hard_cap": ("先停在这里了", "已完成 {n}/{m}，继续大约需要 {x} 积分", "继续", "先到这里"),
    "stuck": ("卡住了", "卡在：{step}", "换个说法再试", None),
    "stuck:self_check_failed": ("结果未通过自检", "已交付 {n} 张，还差：{miss}", "继续", None),
    "user_stop": ("已停止", "已保留生成的 {n} 张", "继续", None),
    "user_stop:quote_declined": ("已取消", "未扣费，已保留生成的 {n} 张", "继续", None),
    "error:network": ("网络断开了", "已保留生成的 {n} 张", "重试", None),
    "error": ("出错了", "{reason}", "重试", None),
}


def test_card_copy_is_the_locked_table():
    assert {k: v["zh"] for k, v in agent_loop.CARD_COPY.items()} == LOCKED
    for key, v in agent_loop.CARD_COPY.items():
        text = "".join(x or "" for x in v["zh"])
        assert not re.search(r"Steps|Tokens|Credits|Time|上限|/300|300", text), key


async def test_card_has_collapsed_plain_details_without_caps(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), policy={"hard_cap_steps": 4},
            store=store)
    res, ev = await r.send("画 4 张猫")
    c = card(ev)
    assert c["copy"]["zh"]["title"] == "先停在这里了" and c["copy"]["zh"]["secondary"] == "先到这里"  # no estimate: sentence hidden, buttons kept
    assert c["copy"]["zh"]["body"] == c["copy"]["zh"]["body"].replace("上限", "") and "4 步" not in c["copy"]["zh"]["body"]
    zh = c["details"]["zh"]
    assert [x.split(" ")[0] for x in zh] == ["步数", agent_loop.DETAIL_TOKEN_LABEL["zh"], "积分", "用时"]
    assert not any(re.search(r"[A-Za-z]", x.split(" ")[0]) for x in zh)   # no English label on the zh card
    assert zh[0] == "步数 4" and not any("/" in x for x in zh)
    assert "budget" not in c and "hard_cap" not in json.dumps(c["details"])


async def test_stuck_card_names_the_step(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("get_canvas", {})), store=store)
    res, ev = await r.send("画一张猫")
    c = card(ev)
    assert stop_of(res)["reason"] == "stuck"
    body = c["copy"]["zh"]["body"]
    assert body.startswith("卡在：") and len(body) > len("卡在：")
    assert c["copy"]["zh"]["primary"] == "换个说法再试" and c["copy"]["action"] == "rephrase"


async def test_quote_declined_card_is_neutral_and_free(monkeypatch, store):
    r = Rig(monkeypatch, [calls(GEN), reply("好")], store=store, prices={"generate_image": 9.0},
            policy={"credits_usd": 1.0}, confirm=False)
    res, ev = await r.send("画一张猫")
    s = stop_of(res)
    assert (s["reason"], s["sub"]) == ("user_stop", "quote_declined") and not res.error
    c = card(ev)
    assert c["copy"]["tone"] == "neutral" and c["copy"]["zh"]["title"] == "已取消"
    assert c["copy"]["zh"]["body"].startswith("未扣费") and r.paid_mcp() == []


# refresh / network drop: the run is resumable from its checkpoint -----------------------------------------------

async def test_network_drop_then_refresh_resumes_from_checkpoint(monkeypatch, store):
    def s(m, n):
        if n < 2:
            return calls(("add_text", {"text": f"x{n}"}))
        raise aiohttp.ClientConnectionError("connection reset")
    r = Rig(monkeypatch, s, store=store)
    res, ev = await r.send("加字", goal="")
    rid = (res.run or {}).get("run_id") or store.list_runs(chat_id="c")[0]["id"]
    run = store.get_run(rid)        # what a refreshed page reads back
    assert run["status"] == "paused" and run["step"] >= 2
    r2 = Rig(monkeypatch, [calls(("add_text", {"text": "x2"})), reply("好了")], store=store)
    res2, _ = await r2.send("", resume=rid)
    assert stop_of(res2)["reason"] == "done"
    assert [a["text"] for _, a in r2.mcp] == ["x2"] and res2.run["log"]["steps"] >= 3


# EL 6441143985: the card never shows an estimate / ratio / unit it does not have ---------------------------------

def test_detail_lines_are_the_locked_copy():
    assert agent_loop.DETAIL_TOKEN_LABEL["zh"] == "模型用量"
    assert agent_loop._DETAIL_LABEL["zh"] == ("步数", "模型用量", "积分", "用时")
    assert agent_loop._DETAIL_LABEL["zh"][1] is agent_loop.DETAIL_TOKEN_LABEL["zh"]   # one key, one-line swap


async def test_no_estimate_means_no_credits_sentence_and_keeps_both_buttons(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), policy={"hard_cap_steps": 3},
            store=store)
    res, ev = await r.send("画 4 张猫")
    c = card(ev)["copy"]
    assert c["zh"]["body"] == "已完成 0/4" and "积分" not in c["zh"]["body"] and "credits" not in c["en"]["body"]
    assert (c["zh"]["primary"], c["zh"]["secondary"]) == ("继续", "先到这里")
    assert (c["en"]["primary"], c["en"]["secondary"]) == ("Continue", "Stop here")


async def test_real_estimate_keeps_the_locked_sentence(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(GEN), policy={"hard_cap_steps": 2}, store=store,
            prices={"generate_image": 0.1}, mcp=lambda name, a, i: json.dumps({"id": f"shape:g{i}"}))
    res, ev = await r.send("画 4 张猫")
    c = card(ev)["copy"]["zh"]
    assert re.fullmatch(r"已完成 \d/4，继续大约需要 [1-9]\d* 积分", c["body"]), c["body"]
    assert (c["primary"], c["secondary"]) == ("继续", "先到这里")


async def test_no_image_target_budget_card_asks(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), policy={"hard_cap_steps": 3},
            store=store)
    res, ev = await r.send("加字", goal="")
    zh = card(ev)["copy"]["zh"]["body"]
    assert zh == "预算到了，要继续吗？" and "/" not in zh
    c = card(ev)["copy"]["zh"]
    assert (c["primary"], c["secondary"]) == ("继续", "先到这里")


async def test_chat_done_body_is_neutral(monkeypatch, store):
    r = Rig(monkeypatch, [reply("你好，有什么可以帮你？")], store=store)
    res, ev = await r.send("你好", goal="")
    assert any(e.t == "run_stop" for e in ev), "chat turn must still emit its done card"
    assert card(ev)["copy"]["zh"]["body"] == "已完成"


@pytest.mark.parametrize("kind", ["video", "text", ""])
def test_done_never_says_images_without_an_image_target(kind):
    for lk, want in (("zh", "已完成"), ("en", "Done")):
        got = agent_loop._card_body("done", lk, n=2, m=2 if kind else None, x=None, kind=kind,
                                    step="", miss="", reason="")
        assert got == want
    assert agent_loop._card_body("done", "zh", n=2, m=2, x=None, kind="image", step="", miss="",
                                 reason="") == "生成了 2 张，已放到画布上"


async def test_network_card_copy(monkeypatch, store):
    def s(m, n):
        if n < 1:
            return calls(GEN)
        raise aiohttp.ClientConnectionError("reset")
    r = Rig(monkeypatch, s, store=store, prices={"generate_image": 0.1},
            mcp=lambda name, a, i: json.dumps({"id": f"shape:g{i}"}))
    res, ev = await r.send("画 2 张猫")
    c = card(ev)["copy"]
    assert (c["key"], c["zh"]["title"], c["zh"]["primary"]) == ("error:network", "网络断开了", "重试")
    assert re.fullmatch(r"已保留生成的 \d+ 张", c["zh"]["body"]) and c["action"] == "retry"


# #393 product ruling: the UI only shows integer credits, ceil, one shared formatter ------------------------------

@pytest.mark.parametrize("usd,want", [(0, 0), (0.0, 0), (0.0001, 1), (0.009, 1), (0.01, 1), (0.011, 2),
                                      (0.07, 7), (0.32, 32), (0.321, 33), (1.0, 100), (2.345, 235),
                                      (0.004, 1), (0.29999, 30),
                                      # product ruling: round to micro-dollars first, then integer ceil
                                      (0.30000001, 30), (0.300001, 31)])
def test_ui_credits_is_integer_ceil(usd, want):
    from ComfyArt.bot.run_budget import ui_credits
    got = ui_credits(usd)
    assert got == want and isinstance(got, int)


async def test_details_credits_are_integer_ceil_not_dollars(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(GEN) if n == 0 else reply("好了"), store=store,
            prices={"generate_image": 0.321}, mcp=lambda name, a, i: json.dumps({"id": f"shape:g{i}"}))
    res, ev = await r.send("画 1 张猫")
    zh = card(ev)["details"]["zh"]
    assert "积分 33" in zh, zh
    assert not any("$" in x or "." in x.split(" ")[1] for x in zh if x.startswith("积分"))


async def test_details_zero_spend_shows_zero(monkeypatch, store):
    r = Rig(monkeypatch, [calls(("add_text", {"text": "x"})), reply("好了")], store=store)
    res, ev = await r.send("加字", goal="")
    assert "积分 0" in card(ev)["details"]["zh"]


async def test_budget_card_estimate_is_integer_ceil_credits(monkeypatch, store):
    from ComfyArt.bot.run_budget import ui_credits
    r = Rig(monkeypatch, lambda m, n: calls(GEN), policy={"hard_cap_steps": 2}, store=store,
            prices={"generate_image": 0.0333}, mcp=lambda name, a, i: json.dumps({"id": f"shape:g{i}"}))
    res, ev = await r.send("画 4 张猫")
    c = card(ev)
    m = re.search(r"继续大约需要 (\d+) 积分$", c["copy"]["zh"]["body"])
    assert m and int(m.group(1)) == ui_credits(c["estimate"]["credits"]) and "$" not in c["copy"]["zh"]["body"]


async def test_quote_card_shows_credits_not_dollars():
    from ComfyArt.bot.local_llm import LocalLlmProvider
    seen = {}

    class Fake:
        async def _confirm_plan(self, spec, turn, handle):
            seen.update(spec)
            return "start"
    for lang, unit in (("zh", "积分"), ("en", "credits")):
        assert await LocalLlmProvider._confirm_over_quote(Fake(), None, None, lang, "生成图片", 0.321, 0.004)
        assert "$" not in seen["prompt"] and f"33 {unit}" in seen["prompt"] and f"1 {unit}" in seen["prompt"]


# #393 product ruling: 已取消 → 继续 shows the quote card again; nothing is charged before the confirm ------------

def _paid_events(store, rid):
    return [e for e in store.list_usage_events(run_id=rid) if e["kind"] == "paid_call"]


@pytest.mark.parametrize("agree", [True, False])
async def test_cancelled_continue_requotes_before_any_charge(monkeypatch, store, agree):
    r = Rig(monkeypatch, [calls(GEN), reply("好")], store=store, prices={"generate_image": 9.0},
            policy={"credits_usd": 1.0}, confirm=False)
    res, ev = await r.send("画一张猫")
    rid = res.run["run_id"]
    c = card(ev)
    assert c["copy"]["key"] == "user_stop:quote_declined" and c["can_continue"]
    assert (c["copy"]["zh"]["primary"], c["copy"]["zh"]["secondary"]) == ("继续", None)   # only 继续
    assert store.get_run(rid)["status"] == "paused" and _paid_events(store, rid) == []
    r2 = Rig(monkeypatch, [calls(GEN), reply("好了")], store=store, prices={"generate_image": 9.0},
             policy={"credits_usd": 1.0})
    seen: list = []

    async def quote(turn, handle, lang, name, p, left):
        # the quote card is up: no paid call went out, no usage event, nothing charged yet
        st = store.get_run(rid)["state"]["budget"]
        seen.append((name, p, list(r2.paid_mcp()), _paid_events(store, rid), st["used"]["credits"]))
        return agree
    monkeypatch.setattr(r2.p, "_confirm_over_quote", quote)
    res2, ev2 = await r2.send("继续", resume=rid)
    assert len(seen) == 1, "继续 must show the quote card first"
    name, price, paid, events, used = seen[0]
    assert (name, price) == ("generate_image", 9.0) and paid == [] and events == [] and used == 0
    if agree:
        assert len(r2.paid_mcp()) == 1 and [e["amount_usd"] for e in _paid_events(store, rid)] == [9.0]
    else:
        assert r2.paid_mcp() == [] and _paid_events(store, rid) == [] and res2.run["log"]["credits_usd"] == 0
        assert card(ev2)["copy"]["key"] == "user_stop:quote_declined"


async def test_details_sub_cent_spend_shows_one_credit_never_lt1(monkeypatch, store):
    r = Rig(monkeypatch, lambda m, n: calls(GEN) if n == 0 else reply("好了"), store=store,
            prices={"generate_image": 0.004}, mcp=lambda name, a, i: json.dumps({"id": f"shape:g{i}"}))
    res, ev = await r.send("画 1 张猫")
    d = card(ev)["details"]
    assert "积分 1" in d["zh"] and "credits 1" in d["en"], d
    assert not any("<" in x for x in d["zh"] + d["en"]), d


# #393 tester: data-URL images inside strings count as image tokens on every path -------------------------------

def test_data_url_in_string_counts_as_image():
    from ComfyArt.bot.run_budget import content_tokens
    img = "data:image/png;base64," + "A" * 400
    assert content_tokens(f"hi {img}", 1500) - content_tokens("hi", 1500) >= 1500
    assert content_tokens(f"a {img} b {img}", 1500) - content_tokens("a b", 1500) >= 3000


def test_data_url_in_list_text_part_counts_as_image():
    from ComfyArt.bot.run_budget import content_tokens, messages_tokens
    img = "data:image/png;base64," + "A" * 400
    plain = content_tokens([{"type": "text", "text": "hi"}], 1500)
    assert content_tokens([{"type": "text", "text": f"hi {img}"}], 1500) - plain >= 1500
    assert messages_tokens([{"role": "tool", "content": f"shot {img}"}], 1500) >= 1500


# #393 tester: unattended — every stop reason notifies exactly once and makes 0 paid calls -------------------------

def _unattended_cases():
    add = lambda m, n: calls(("add_text", {"text": f"x{n}"}))  # noqa: E731
    big = "x" * 8000
    return {
        "done": dict(script=[calls(("add_text", {"text": "a"})), reply("好了")]),
        "hard_cap": dict(script=add, policy={"hard_cap_steps": 3}),
        "stuck": dict(script=lambda m, n: calls(("add_text", {"text": "same"}))),
        "error": dict(script=lambda m, n: __import__("ComfyArt.bot.local_llm", fromlist=["x"]).LlmHttpError(500, "boom")),
        "budget:tokens": dict(script=add, window=2000, policy={"token_window_multiple": 2},
                              mcp=lambda name, a, i: json.dumps({"id": f"s{i}", "t": big})),
        "budget:paid_quote": dict(script=[calls(GEN), reply("好")], policy={"credits_usd": 1.0},
                                  prices={"generate_image": 1.5}),
    }


@pytest.mark.parametrize("case", list(_unattended_cases()))
async def test_unattended_every_reason_one_notify_zero_paid(monkeypatch, store, case):
    kw = dict(_unattended_cases()[case])
    script = kw.pop("script")
    r = Rig(monkeypatch, script, store=store, **kw)
    res, ev = await r.send("加字", mode="unattended")
    assert stop_of(res)["reason"] == case.split(":")[0], stop_of(res)
    assert len([e for e in ev if e.t == "notify"]) == 1
    assert r.paid_mcp() == [] and res.run["log"]["paid_calls"] == 0 and r.confirms == []
    assert [e for e in store.list_usage_events(run_id=res.run["run_id"]) if e["kind"] == "paid_call"] == []
