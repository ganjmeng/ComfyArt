"""#231 Agent regression set: 15 tester tasks (+ fault-retry targets and the 80-step limit) x zh/en UI.
Fully mocked, $0: scripted mock LLM, mock WaveSpeed, FakePage for the canvas; real built-in agent loop
(bot/local_llm.py via api/providers.AgentLlmProvider), real bot send route, MCP dispatch and paid guard.
Run everything + the summary report with: python tests/agent_regression/run.py"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cases import CASES, IMG, Case  # noqa: E402
from harness import CJK, LLM_KEY, ROOT, WS_KEY, FakePage, MockLLM, MockWS, NetGuard, curated_ids  # noqa: E402
from conftest import wait_bot_done, write_settings  # noqa: E402

RESULTS: dict[str, dict] = {}
LANGS = ("zh", "en")


def _params():
    for c in CASES:
        for lang in LANGS:
            marks = [pytest.mark.xfail(reason=c.xfail, strict=True)] if c.xfail else []
            yield pytest.param(c, lang, id=f"{c.id}-{lang}", marks=marks)


async def _run(case: Case, lang: str, monkeypatch, caplog, capfd) -> dict:
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from server import PromptServer

    from ComfyArt.api import chat_store, paid_guard
    from ComfyArt.api.bot_turns import ACTIVE_TURNS, QUEUED
    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.bot import local_llm

    llm, ws = MockLLM(case.script), MockWS()
    app = web.Application()
    app.router.add_routes(PromptServer.instance.routes)
    app.router.add_get("/mockllm/v1/models", llm.models)
    app.router.add_post("/mockllm/v1/chat/completions", llm.chat)
    app.router.add_post("/mockws/api/v3/{model:.+}", ws.submit)
    client = TestClient(TestServer(app, host="127.0.0.1"))
    await client.start_server()
    base = f"http://127.0.0.1:{client.server.port}"
    monkeypatch.setattr(PromptServer.instance, "port", client.server.port, raising=False)
    monkeypatch.setenv("WAVESPEED_BASE_URL", base + "/mockws")
    if case.no_key:
        monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
        monkeypatch.delenv("COMFYART_LOCAL_LLM_API_KEY", raising=False)
        llm_url = "https://llm.wavespeed.ai/v1"  # the WaveSpeed LLM default: needs the WaveSpeed key
    else:
        monkeypatch.setenv("WAVESPEED_API_KEY", WS_KEY)
        monkeypatch.setenv("COMFYART_LOCAL_LLM_API_KEY", LLM_KEY)
        llm_url = base + "/mockllm/v1"
    write_settings(**{"enable-bot": True, "bot-local-llm-url": llm_url, "bot-model-local-llm": "mock-agent-model"})
    page = FakePage(ws_url=base + "/mockws", decline=case.decline, shapes=[*map(_copy, case.shapes_initial)],
                    selection=list(case.selection), brand_kit=case.brand_kit)
    monkeypatch.setattr(canvas, "submit_command", page)
    monkeypatch.setattr(local_llm, "_LLM_TIMEOUT_S", 0.3)  # the timeout fault sleeps 1 s
    monkeypatch.setattr(local_llm, "_RETRY_BACKOFF_S", (0.01, 0.01))  # #232 retry waits, shortened
    monkeypatch.setattr(local_llm, "_RATE_LIMIT_WAIT_S", (0.01, 0.01))
    caplog.set_level(logging.DEBUG)
    ACTIVE_TURNS.clear(); QUEUED.clear(); paid_guard.TURNS.clear()
    chat = chat_store.create_chat(user="default", project="p231", provider="local-llm")
    messages = []
    try:
        with NetGuard() as net:
            for turn in case.turns:
                r = await client.post(f"/comfyart/bot/chats/{chat['id']}/send", json={"text": turn[lang], "lang": lang})
                assert r.status == 200, await r.text()
                messages = (await wait_bot_done(client, chat["id"], timeout=30))["messages"]
    finally:
        await client.close()
    out, err = capfd.readouterr()
    assistants = [m for m in messages if m["role"] == "assistant"]
    last = assistants[-1]
    blocks = [b for m in assistants for b in m["blocks"]]
    uses = [b for b in blocks if b["type"] == "tool_use"]
    results = [b for b in blocks if b["type"] == "tool_result"]
    usage = {}
    for m in assistants:
        for k, v in (m.get("usage") or {}).items():
            if isinstance(v, (int, float)):
                usage[k] = usage.get(k, 0) + v
    return {
        "case": case, "lang": lang, "page": page, "llm": llm, "ws": ws, "net": net.blocked,
        "tools": [str(b.get("name", "")).split("__")[-1] for b in uses], "uses": uses, "results": results,
        "status": last["status"], "reply": "".join(b.get("text", "") for b in last["blocks"] if b["type"] == "text").strip(),
        "notices": [b["text"] for b in last["blocks"] if b["type"] == "notice"],
        "retries": [b for b in blocks if b["type"] == "retry"],
        "last_blocks": last["blocks"],
        "logs": caplog.text + out + err + json.dumps(messages, ensure_ascii=False), "usage": usage,
        "messages": len(llm.requests[-1]["messages"]) if llm.requests else 0,
    }


def _copy(s):
    from dataclasses import replace
    return replace(s, props=dict(s.props))


def _check(r: dict) -> None:
    c: Case = r["case"]; lang = r["lang"]; page: FakePage = r["page"]
    # 1. tool order/args; every paid model id is in the curated list
    assert r["tools"] == c.tools
    cur = curated_ids()
    from ComfyArt.api.wavespeed import load_config
    cfg = load_config()["features"]
    for tool, feature, model in page.models:
        allowed = cur.get(feature) or {m if isinstance(m, str) else m["id"] for m in cfg[feature]["models"]}
        assert model in allowed, (tool, feature, model)
    # 2. results land on the canvas with the expected shape count
    assert page.counts() == c.shapes
    # 3. the reply / notice follows the UI language
    if c.status == "done":
        assert r["reply"] and bool(CJK.search(r["reply"])) == (lang == "zh"), r["reply"]
    if c.error:
        assert r["notices"] and r["notices"][-1].startswith(c.error[lang]), r["notices"]
        # #232: the zh UI accepts only Chinese errors, the en UI only English ones
        assert bool(CJK.search(r["notices"][-1])) == (lang == "zh"), r["notices"]
    if c.reply:
        assert c.reply[lang] in r["reply"]
    # 4. paid calls == expected (no double charge), all with the (sentinel) key, none to the real hosts
    assert len(r["ws"].submits) == c.paid
    assert all(a == f"Bearer {WS_KEY}" for a in r["ws"].auth)
    assert r["net"] == []
    # 5. no key in the logs / stored chat
    assert WS_KEY not in r["logs"] and LLM_KEY not in r["logs"]
    # 6. steps <= limit
    assert len(r["uses"]) <= c.limit
    assert r["status"] == c.status, (r["status"], r["notices"])
    if c.llm_requests is not None:
        assert len(r["llm"].requests) == c.llm_requests
    if r["llm"].requests:
        assert set(r["llm"].auth) == {f"Bearer {LLM_KEY}"}
    EXTRA.get(c.extra or "", lambda r: None)(r)


def _args(r, name, n=0):
    return [b["input"] for b in r["uses"] if b["name"].split("__")[-1] == name][n]


def _x_ratio(r):
    a = _args(r, "generate_image")
    assert a["ratio"] == "3:4" and "watercolor" in a["prompt"]


def _x_edit_target(r):
    assert _args(r, "edit_image")["id"] == IMG
    assert r["page"].models[0][1] == "image_edit"


def _x_t2v(r):
    assert _args(r, "generate_video")["duration"] == 5 and r["page"].models[0][1] == "text_to_video"


def _x_i2v(r):
    assert _args(r, "generate_video")["first_frame"] == IMG and r["page"].models[0][1] == "image_to_video"


def _x_music(r):
    assert _args(r, "generate_music")["duration"] == 15 and r["page"].models[0][1] == "music"


def _x_sale(r):
    texts = sorted(s.text for s in r["page"].shapes.values() if s.type == "text")
    assert texts == ["50% OFF", "SALE"]


def _x_brand(r):
    t = next(s for s in r["page"].shapes.values() if s.type == "text")
    assert t.props == {"font": "Inter", "color": "#FF5A1F"}
    assert "#FF5A1F" in _args(r, "generate_image")["prompt"]


def _x_edit_original(r):
    """'brighter' = exactly 1 new image made FROM the original; the original is untouched; 1 paid call per edit."""
    from dataclasses import asdict
    page = r["page"]
    assert _args(r, "edit_image")["id"] == "shape:gen1"
    (edit,) = page.edits
    orig = page.shapes["shape:gen1"]
    assert asdict(orig) == edit["input"]                       # same id / props / asset, unchanged
    assert set(page.shapes) - edit["before"] == set(edit["output"]) and len(edit["output"]) == 1
    new = page.shapes[edit["output"][0]]
    assert new.type == "image" and new.props["source"] == orig.id and new.props["asset"] != orig.props["asset"]
    edits = [p for p in page.payloads if p["tool"] == "edit_image"]
    assert len(edits) == 1 and edits[0]["image"] == orig.props["asset"]  # edit input references the original


def _x_slides(r):
    texts = [s for s in r["page"].shapes.values() if s.type == "text"]
    assert all(s.parent.startswith("shape:") for s in texts)  # editable text shapes inside the slide frames


def _x_cancel(r):
    first, second = r["results"][:2]
    assert json.loads(first["text"])["cancelled"] is True  # the step shows 已取消 / Cancelled
    assert first["status"] == second["status"] == "cancelled"  # #232: never "success"
    # the guard refusal reaches the model as text (local_llm marks only transport errors as is_error)
    assert second["text"].startswith("[tool error]") and ("已取消" in second["text"] or "Cancelled" in second["text"])  # retry refused
    assert r["page"].confirms == 1  # one confirm dialog, no second ask
    loc = {lg: json.loads((ROOT / "src" / "locales" / f"{lg}.json").read_text()) for lg in ("zh", "en")}
    assert loc["zh"]["chatMessage.cancelled"] == "已取消" and loc["en"]["chatMessage.cancelled"] == "Cancelled"


def _retry_kind(r):
    return "5xx" if r["case"].id.split("-")[1] == "500" else r["case"].id.split("-")[1]


def _x_retry_rows(r):
    """#232: two retry rows (attempt 1/2, 2/2) of the fault kind; the paid tool ran once."""
    rows = r["retries"]
    assert [(b["kind"], b["attempt"], b["max"]) for b in rows] == [(_retry_kind(r), 1, 2), (_retry_kind(r), 2, 2)]
    assert all(b["until"] > 0 and b["wait_s"] >= 0 for b in rows)


def _x_fail_done(r):
    _x_retry_rows(r)
    assert ("已完成：生成图像" if r["lang"] == "zh" else "Done so far: Generate image.") in r["notices"][-1]


_DONE_WORDS = ("完成", "已完成", "Done", "done")


def _run_stop(r):
    cards = [b for b in r["last_blocks"] if b["type"] == "run_stop"]
    assert cards, "#391: every budget-loop run ends with a run_stop card"
    return cards[-1]


def _sc(r):
    """The structured #383 result: on the run_stop card, and on the failure notice when it failed."""
    return _run_stop(r)["self_check"]


def _visible(r):
    return r["reply"] + " ".join(r["notices"])


def _x_run_done(r):
    assert _run_stop(r)["stop"]["reason"] == "done"


def _x_hard_cap(r):
    card = _run_stop(r)
    assert card["stop"]["reason"] == "hard_cap" and card["can_continue"] is True


def _x_stalled(r):
    card = _run_stop(r)
    assert card["stop"]["reason"] == "stalled" and card["stop"]["sub"] == "readonly_limit"


def _x_sc_pass(r):
    sc = _sc(r)
    assert sc["self_check"] == "pass" and sc["expected"] == sc["placed"] == 4
    assert _run_stop(r)["stop"]["reason"] == "done"


def _x_sc_missing2(r):
    sc = _sc(r)
    assert (sc["self_check"], sc["expected"], sc["generated"], sc["placed"], sc["missing"]) == ("fail", 4, 4, 2, 2)
    assert not any(w in _visible(r) for w in _DONE_WORDS), _visible(r)
    assert ("缺 2 张" if r["lang"] == "zh" else "2 missing") in _visible(r)
    note = next(b for b in r["last_blocks"] if b["type"] == "notice" and b.get("self_check"))
    assert note["self_check"]["missing"] == 2


def _x_sc_allfail(r):
    sc = _sc(r)
    assert sc["self_check"] == "fail" and sc["generated"] == 0 and sc["missing"] == 4
    assert not any(w in _visible(r) for w in _DONE_WORDS), _visible(r)
    assert "content filter" in _visible(r)  # the failure reason reaches the user


def _x_sc_claim(r):
    sc = _sc(r)
    assert sc["self_check"] == "fail" and sc["missing"] == 4
    assert not any(w in _visible(r) for w in _DONE_WORDS), _visible(r)  # "已完成 4 张" was rewritten


def _x_sc_skip(r):
    assert _sc(r)["self_check"] == "skip"
    assert not any(b.get("self_check") for b in r["last_blocks"] if b["type"] == "notice")


EXTRA = {k[3:]: v for k, v in globals().items() if k.startswith("_x_")}


@pytest.mark.parametrize("case,lang", list(_params()))
async def test_agent_regression(case, lang, monkeypatch, caplog, capfd):
    r = await _run(case, lang, monkeypatch, caplog, capfd)
    row = {"case": case.id, "lang": lang, "title": case.title, "steps": len(r["uses"]), "limit": case.limit,
           "paid_calls": len(r["ws"].submits), "paid_expected": case.paid, "llm_requests": len(r["llm"].requests),
           "messages": r["messages"], "tokens": sum(r["llm"].usage.values()),
           "status": r["status"], "tools": r["tools"], "note": case.xfail or case.note or (f"baseline, flips in {case.baseline_for}" if case.baseline_for else "")}
    try:
        _check(r)
        row["result"] = "pass"
    except Exception as e:
        row["result"] = "xfail" if case.xfail else "fail"
        row["error"] = str(e).splitlines()[0][:200] if str(e) else "assertion failed"
        raise
    finally:
        RESULTS[f"{case.id}-{lang}"] = row


@pytest.fixture(scope="module", autouse=True)
def _report():
    yield
    if not RESULTS:
        return
    from report import write
    write(RESULTS)
