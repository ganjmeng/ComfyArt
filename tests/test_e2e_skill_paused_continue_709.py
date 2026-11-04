"""#709 precondition (tech lead, option a): a run that pauses on budget (paused / budget:exhausted) or on a
stuck:* stop shows WHY in the UI and offers 继续; 继续 resumes the SAME run (no restart) and can reach done.
Scripted LLM + MCP (no paid call); the card is the backend's real run_stop block, rendered by the real
RunStop in Chromium (tests/js/runstop harness). SHOT_DIR=<dir> writes the docs/qa/709 screenshot."""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.bot import run_budget

from test_agent_budget_391 import Clock, Rig, calls, card, reply, stop_of, store  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")
SHOT = os.environ.get("SHOT_DIR")


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    d = tmp_path_factory.mktemp("paused709")
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/runstop/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css"))
    (d / "index.html").write_text(f"<!doctype html><meta charset=utf-8><style>{css}</style><div id=root></div>"
        "<script>window.WebSocket = class { constructor() {} send() {} close() {} addEventListener() {} }</script>"
        "<script src=app.js></script>")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # browsers not installed
            pytest.skip(f"no chromium: {e}")
        pg = b.new_page(viewport={"width": 412, "height": 360}, device_scale_factor=2)
        pg.goto((d / "index.html").as_uri())
        pg.wait_for_function("window.__ready === true")
        yield pg
        b.close()


def ui_continue(page, block, reason_text, shot=None):
    """Render the real card: reason text + a 继续 button; clicking it POSTs /runs/<same id>/continue."""
    page.evaluate("([b]) => { window.__calls = []; window.__render(b, 'zh', 'light') }", [[block]])
    page.wait_for_selector(".ca-run")
    r = page.locator(".ca-run").first
    assert reason_text in r.inner_text()
    assert page.locator("[data-run-reason]").first.inner_text() == reason_text
    if shot:
        Path(shot).parent.mkdir(parents=True, exist_ok=True)
        r.screenshot(path=shot)
    btn = r.locator("button", has_text="继续")
    assert btn.count() == 1 and btn.is_visible()
    btn.click()
    page.wait_for_function("window.__calls.length > 0")
    c = page.evaluate("window.__calls")
    assert [(x["method"], x["url"]) for x in c] == [("POST", f"/api/comfyart/bot/runs/{block['run_id']}/continue")]
    return c[0]["url"].split("/runs/")[1].split("/")[0]


def resume_to_done(monkeypatch, store, rid):
    r2 = Rig(monkeypatch, [calls(("add_text", {"text": "end"})), reply("好了")], store=store)
    res2, ev2 = arun(r2.send("继续", resume=rid))
    assert res2.run["run_id"] == rid                       # same run, not a restart
    assert stop_of(res2)["reason"] == "done", stop_of(res2)
    assert store.get_run(rid)["status"] == "done"
    assert len(store.list_runs(chat_id="c")) == 1
    return res2


def test_budget_exhausted_shows_reason_and_continue_resumes_same_run(monkeypatch, store, page):
    clk = Clock()

    def mcp(name, a, i):
        clk.t += 400
        return json.dumps({"id": f"s{i}"})
    r = Rig(monkeypatch, lambda m, n: calls(("add_text", {"text": f"x{n}"})), store=store, clock=clk, mcp=mcp,
            policy={"wall_time_s": 600})
    res, ev = arun(r.send("加字"))
    s, rid = stop_of(res), res.run["run_id"]
    assert (s["reason"], s["sub"], s["dimension"]) == ("budget", "exhausted", "time")
    assert store.get_run(rid)["status"] == "paused"
    b = card(ev)
    assert b["can_continue"] and b["run_id"] == rid
    shot = str(Path(SHOT) / "paused_budget_exhausted_zh.png") if SHOT else None
    assert ui_continue(page, b, "用时达到本次上限", shot) == rid
    resume_to_done(monkeypatch, store, rid)


def test_stuck_shows_reason_and_continue_resumes_same_run(monkeypatch, store, page):
    r = Rig(monkeypatch, lambda m, n: calls(("get_canvas", {})), store=store)
    res, ev = arun(r.send("加字", goal=""))
    s, rid = stop_of(res), res.run["run_id"]
    assert s["reason"] == "stuck" and store.get_run(rid)["status"] == "paused"
    b = card(ev)
    want = run_budget_label(s["sub"])
    assert want and b["copy"]["zh"]["reason"] == want
    assert ui_continue(page, b, want) == rid
    resume_to_done(monkeypatch, store, rid)


def test_stuck_timeout_shows_reason_and_continue_resumes_same_run(monkeypatch, store, page):
    orig = run_budget.ProgressTracker.wait_timeout

    def small(self, obs, now=None):
        self.wait_max_polls = 2
        return orig(self, obs, now)
    monkeypatch.setattr(run_budget.ProgressTracker, "wait_timeout", small)
    r = Rig(monkeypatch, lambda m, n: calls(("wait_generation", {"ids": ["job1"]})), store=store,
            mcp=lambda name, a, i: json.dumps({"status": "pending"}))
    res, ev = arun(r.send("加字", goal=""))
    s, rid = stop_of(res), res.run["run_id"]
    assert (s["reason"], s["sub"]) == ("stuck", "timeout") and store.get_run(rid)["status"] == "paused"
    b = card(ev)
    assert ui_continue(page, b, run_budget_label("timeout")) == rid
    monkeypatch.setattr(run_budget.ProgressTracker, "wait_timeout", orig)
    resume_to_done(monkeypatch, store, rid)


def arun(coro):
    """The scripted backend runs on its own loop in a worker thread (sync Playwright owns this thread's loop)."""
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(asyncio.run, coro).result()


def run_budget_label(sub):
    from ComfyArt.bot.agent_loop import _STALL_LABEL
    return _STALL_LABEL["zh"].get(sub, "")
