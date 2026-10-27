"""#393 end-to-end: over-quote confirm from a real click to the real API.

The local-llm provider runs a whole run through the real HTTP routes (/chats, /send, /asks/{aid}/answer); only the
LLM, MCP and price lookups are mocked (no keys, no paid calls). The pending over-quote ask block the backend wrote is
rendered in Chromium by the real chat router (renderAsk → OverQuote) + the real <Confirm/> modal; the test clicks
「先到这里」/「确认」 and the page's own fetch is routed to the aiohttp app. Card copy comes from the one shared
schema bot/over_quote.json. SHOT_DIR=<dir> also writes the four #78 shots of the card (zh/en × light/dark)."""
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import ComfyArt.api.bot  # noqa: F401  (registers the /comfyart/bot routes)
from ComfyArt.api import bot_asks, chat_store
from ComfyArt.bot import providers
from ComfyArt.bot.local_llm import OVER_QUOTE
from conftest import wait_bot_done
from test_agent_budget_391 import Rig, calls, reply, store  # noqa: F401  (store is a fixture)

ROOT = Path(__file__).resolve().parent.parent
apw = pytest.importorskip("playwright.async_api")
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")
GEN = ("generate_image", {"prompt": "cat", "model": "m"})


def gen(n):  # a fresh prompt each step, so the repeat guard never fires
    return ("generate_image", {"prompt": f"cat {n}", "model": "m"})


# one model step with two paid calls; the model then just replies
TWO = lambda m, n: calls(gen(0), gen(1)) if n == 0 else reply("好")  # noqa: E731
ORIGIN = "http://comfyart.test"
SHOT = os.environ.get("SHOT_DIR")


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("overquote")
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/overquote/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(d / "app.js")})
    css = "\n".join((ROOT / "src/styles" / f).read_text() for f in ("base.css", "canvas.css", "shell.css", "overlays.css", "home.css"))
    html = (f"<!doctype html><meta charset=utf-8><style>{css}</style><div id=root></div>"
            "<script>window.WebSocket = class { constructor() {} send() {} close() {} addEventListener() {} }</script>"
            "<script src=/app.js></script>")
    return html, (d / "app.js").read_text()


@pytest.fixture()
async def ui(bundle, bot_client):
    html, js = bundle
    hits: list = []
    done = asyncio.Event()  # set each time a routed /api request has its response recorded
    async with apw.async_playwright() as p:
        try:
            b = await p.chromium.launch()
        except Exception as e:  # browsers not installed
            pytest.skip(f"no chromium: {e}")
        pg = await b.new_page(viewport={"width": 412, "height": 420}, device_scale_factor=2)

        async def route(r):
            url = r.request.url[len(ORIGIN):]
            if url.startswith("/api/"):  # the page's real fetch → the real aiohttp route
                body = r.request.post_data
                hit = {"path": url[4:], "method": r.request.method, "body": json.loads(body) if body else None}
                hits.append(hit)
                res = await bot_client.request(r.request.method, url[4:], data=body,
                                               headers={"content-type": "application/json"})
                hit["status"] = res.status
                done.set()
                return await r.fulfill(status=res.status, body=await res.read(), content_type="application/json")
            if url == "/app.js":
                return await r.fulfill(body=js, content_type="text/javascript")
            return await r.fulfill(body=html, content_type="text/html")
        await pg.route(f"{ORIGIN}/**", route)
        await pg.goto(ORIGIN + "/")
        await pg.wait_for_function("window.__ready === true")
        pg.hits = hits

        async def hits_event(n, timeout=5.0):  # until request n has its response (event-driven, no polling)
            async def ready():
                while not (len(hits) > n and "status" in hits[n]):
                    done.clear()
                    if len(hits) > n and "status" in hits[n]:
                        break
                    await done.wait()
            await asyncio.wait_for(ready(), timeout)
        pg.hits_event = hits_event
        yield pg
        await b.close()


class Run:
    """A real chat on the real routes, driven by a mocked local-llm (Rig without its _confirm_over_quote stub)."""

    def __init__(self, monkeypatch, client, store, prices, script=None, usd=1.0, mcp=None):
        self.prices = list(prices)
        self._mcp = mcp
        self.r = Rig(monkeypatch, script or (lambda m, n: calls(gen(n))), store=store, policy={"credits_usd": usd},
                     mcp=self.mcp)
        monkeypatch.delattr(self.r.p, "_confirm_over_quote")  # the real ask path

        async def price(name, args):
            return self.prices[min(len(self.r.paid_mcp()), len(self.prices) - 1)] if name == "generate_image" else None
        monkeypatch.setattr(self.r.p, "_price_call", price)
        monkeypatch.setitem(providers._REGISTRY, self.r.p.id, self.r.p)
        self.client = client
        self.asks: list = []
        real = bot_asks.create_ask

        def spy(chat_id, message_id, spec):
            a = real(chat_id, message_id, spec)
            self.asks.append(a)
            return a
        monkeypatch.setattr(bot_asks, "create_ask", spy)

    def mcp(self, name, args, i):  # the real async generate_image shape: a queued job id, nothing on the canvas yet
        if self._mcp is not None:
            return self._mcp(name, args, i)
        if name == "generate_image":
            return json.dumps({"ids": [f"job-{i}"], "status": "queued"})
        if name == "get_canvas":
            return json.dumps({"shapes": []})
        return json.dumps({"ok": True})

    async def start(self, text="画 3 张猫", lang="zh"):
        c = await self.client.post("/comfyart/bot/chats", json={"provider": "local-llm", "project": "p393"})
        self.chat = (await c.json())["chat"]["id"]
        res = await self.client.post(f"/comfyart/bot/chats/{self.chat}/send", json={"text": text, "lang": lang})
        assert res.status < 300, await res.text()

    async def pending(self, k, timeout=10.0):
        """The k-th over-quote ask, as the block the backend stored on the message (what the UI renders)."""
        for _ in range(int(timeout / 0.02)):
            if len(self.asks) >= k and self.asks[k - 1].id in bot_asks.PENDING:
                aid = self.asks[k - 1].id
                for m in chat_store.list_messages(self.chat):
                    for b in m.get("blocks") or []:
                        if b.get("type") == "ask" and b.get("ask_id") == aid:
                            return b
            await asyncio.sleep(0.02)
        tail = [b for m in chat_store.list_messages(self.chat) for b in (m.get("blocks") or [])][-4:]
        raise AssertionError(f"no over-quote ask #{k}; asks={len(self.asks)} paid={self.r.paid_mcp()} tail={tail}")

    async def done(self):
        data = await wait_bot_done(self.client, self.chat, timeout=10.0)
        blocks = [b for m in data["messages"] for b in (m.get("blocks") or [])]
        return blocks, [b for b in blocks if b.get("type") == "run_stop"]


async def show(ui, block, chat, lang="zh", theme="light"):
    await ui.evaluate("([b, c, l, t]) => window.__render(b, c, l, t)", [block, chat, lang, theme])
    modal = ui.locator(".ca-modal")
    await modal.wait_for()
    return modal


async def wait_hit(ui, n):
    """The first request after index n, once its response is in. The route handler records the request before it
    awaits the backend, so the hit exists without a status for a moment: reading it then was the #393 flake."""
    await ui.hits_event(n)
    return ui.hits[n]


async def click(ui, block, chat, label, lang="zh", theme="light", shot=None):
    await ui.evaluate("([b, c, l, t]) => window.__render(b, c, l, t)", [block, chat, lang, theme])
    modal = ui.locator(".ca-modal")
    await modal.wait_for()
    copy = OVER_QUOTE["copy"][lang]
    assert await modal.locator(".ca-rename__body > div").first.inner_text() == copy["body"].format(credits=block["credits"])
    assert await ui.locator(".ca-panel__secondary").inner_text() == copy["decline"]
    assert await ui.locator(".ca-panel__primary").inner_text() == copy["confirm"]
    if shot:
        Path(SHOT).mkdir(parents=True, exist_ok=True)
        await modal.screenshot(path=str(Path(SHOT) / shot))
    n = len(ui.hits)
    await ui.get_by_role("button", name=label, exact=True).click()
    hit = await wait_hit(ui, n)
    assert hit["path"] == f"/comfyart/bot/chats/{chat}/asks/{block['ask_id']}/answer" and hit["status"] == 202, hit
    return hit


async def test_decline_first_stops_with_one_quote_and_no_paid_call(monkeypatch, bot_client, store, ui):
    # every model step asks for two paid calls: a decline must stop the second one AND the next step
    run = Run(monkeypatch, bot_client, store, prices=[9.0], script=lambda m, n: calls(gen(2 * n), gen(2 * n + 1)))
    await run.start()
    b = await run.pending(1)
    assert b["kind"] == OVER_QUOTE["kind"] and "questions" not in b and b["credits"] == 900
    llm_before = run.r.n
    hit = await click(ui, b, run.chat, "先到这里")
    assert hit["body"]["selected"] == [OVER_QUOTE["decline"]] and "answers" not in hit["body"]
    blocks, stops = await run.done()
    assert len(run.asks) == 1, "a decline must not raise a second quote"
    assert run.r.paid_mcp() == []
    assert run.r.n == llm_before, "the decline is not handed back to the model"
    assert stops and stops[-1]["copy"]["key"] == "user_stop:quote_declined"
    assert [x for x in blocks if x.get("ask_id") == b["ask_id"]][0]["selected"] == [OVER_QUOTE["decline"]]


async def test_decline_after_one_image_keeps_count_from_delivery_records(monkeypatch, bot_client, store, ui):
    run = Run(monkeypatch, bot_client, store, prices=[0.3, 0.9], script=TWO)
    await run.start()
    b = await run.pending(1)
    assert len(run.r.paid_mcp()) == 1  # the cheap one ran (queued job, nothing on the canvas)
    await click(ui, b, run.chat, "先到这里")
    blocks, stops = await run.done()
    card = stops[-1]["copy"]
    assert card["key"] == "user_stop:quote_declined" and len(run.asks) == 1 and len(run.r.paid_mcp()) == 1
    assert "已保留之前生成的 1 张" in card["zh"]["body"], card["zh"]["body"]
    assert "1 image" in card["en"]["body"], card["en"]["body"]


async def test_confirm_pays_this_call_only_then_requotes(monkeypatch, bot_client, store, ui):
    run = Run(monkeypatch, bot_client, store, prices=[9.0, 9.0], script=TWO)
    await run.start()
    b1 = await run.pending(1)
    hit = await click(ui, b1, run.chat, "确认")
    assert hit["body"]["selected"] == [OVER_QUOTE["confirm"]]
    b2 = await run.pending(2)  # the next over-quote call (same step) asks again: 确认 covered one call only
    assert len(run.r.paid_mcp()) == 1, "确认 pays exactly the confirmed call"
    await click(ui, b2, run.chat, "先到这里")
    blocks, stops = await run.done()
    assert len(run.asks) == 2 and len(run.r.paid_mcp()) == 1
    assert stops[-1]["copy"]["key"] == "user_stop:quote_declined"
    assert "已保留之前生成的 1 张" in stops[-1]["copy"]["zh"]["body"]


@pytest.mark.parametrize("label", ["Stop here", "Confirm"])
async def test_en_buttons_answer_through_the_api(monkeypatch, bot_client, store, ui, label):
    run = Run(monkeypatch, bot_client, store, prices=[9.0], script=lambda m, n: calls(GEN) if n == 0 else reply("done"))
    await run.start("draw a cat", lang="en")
    b = await run.pending(1)
    hit = await click(ui, b, run.chat, label, lang="en")
    ok = label == "Confirm"
    assert hit["body"]["selected"] == [OVER_QUOTE["confirm" if ok else "decline"]]
    blocks, stops = await run.done()
    assert len(run.asks) == 1 and len(run.r.paid_mcp()) == (1 if ok else 0)
    if not ok:
        assert stops[-1]["copy"]["key"] == "user_stop:quote_declined"


@pytest.mark.skipif(not SHOT, reason="SHOT_DIR not set")
@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_shots(monkeypatch, bot_client, store, ui, lang, theme):
    run = Run(monkeypatch, bot_client, store, prices=[0.33], usd=0.1)
    await run.start("画一张猫" if lang == "zh" else "draw a cat", lang=lang)
    b = await run.pending(1)
    await click(ui, b, run.chat, OVER_QUOTE["copy"][lang]["decline"], lang=lang, theme=theme,
                shot=f"over-quote-{lang}-{theme}.png")
    await run.done()


# --- #393 card chrome: no ✕, Esc = 先到这里, backdrop inert, body aligned with the title ---

async def test_card_has_no_close_x(monkeypatch, bot_client, store, ui):
    run = Run(monkeypatch, bot_client, store, prices=[9.0], script=lambda m, n: calls(GEN) if n == 0 else reply("done"))
    await run.start()
    modal = await show(ui, await run.pending(1), run.chat)
    head = modal.locator(".ca-side__head")
    assert await head.locator("button").count() == 0
    assert await modal.locator(".ca-panel__icon").count() == 0
    assert await modal.locator("button").count() == 2  # only 先到这里 / 确认


async def test_esc_declines_one_quote_no_paid(monkeypatch, bot_client, store, ui):
    run = Run(monkeypatch, bot_client, store, prices=[9.0], script=lambda m, n: calls(gen(2 * n), gen(2 * n + 1)))
    await run.start()
    b = await run.pending(1)
    await show(ui, b, run.chat)
    n = len(ui.hits)
    await ui.keyboard.press("Escape")
    hit = await wait_hit(ui, n)
    assert hit["path"] == f"/comfyart/bot/chats/{run.chat}/asks/{b['ask_id']}/answer" and hit["status"] == 202, hit
    assert hit["body"]["selected"] == [OVER_QUOTE["decline"]]
    blocks, stops = await run.done()
    assert len(run.asks) == 1 and run.r.paid_mcp() == []
    assert stops[-1]["copy"]["key"] == "user_stop:quote_declined"


async def test_backdrop_click_does_nothing(monkeypatch, bot_client, store, ui):
    run = Run(monkeypatch, bot_client, store, prices=[9.0], script=lambda m, n: calls(GEN) if n == 0 else reply("done"))
    await run.start()
    b = await run.pending(1)
    modal = await show(ui, b, run.chat)
    n = len(ui.hits)
    await ui.mouse.click(6, 6)  # the .ca-modal backdrop, outside the card
    await ui.mouse.click(406, 414)
    assert await modal.locator(".ca-modal__card").is_visible()
    assert b["ask_id"] in bot_asks.PENDING and run.r.paid_mcp() == [] and len(run.asks) == 1
    # no fixed wait: the very next request after the backdrop clicks must be this 先到这里, so the clicks posted nothing
    hit = await click(ui, b, run.chat, "先到这里")
    assert ui.hits.index(hit) == n and len(ui.hits) == n + 1, ui.hits[n:]
    assert hit["body"]["selected"] == [OVER_QUOTE["decline"]]
    await run.done()


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_body_left_edge_equals_title(monkeypatch, bot_client, store, ui, lang, theme):
    run = Run(monkeypatch, bot_client, store, prices=[9.0], script=lambda m, n: calls(GEN) if n == 0 else reply("done"))
    await run.start("画一张猫" if lang == "zh" else "draw a cat", lang=lang)
    modal = await show(ui, await run.pending(1), run.chat, lang=lang, theme=theme)
    title = await modal.locator(".ca-side__head > span").first.bounding_box()
    body = await modal.locator(".ca-rename__body > div").first.bounding_box()
    assert abs(body["x"] - title["x"]) < 0.5, (title, body)


# --- EL guard: the #393 opt-in props must not change ordinary dialogs (values measured on origin/main eca71bc) ---
# main: Confirm renders <Modal closable={false}> → an ordinary confirm has NO ✕; backdrop click cancels and closes;
# body text sits 20px from the card edge (.ca-rename__body padding 0 20px), the title 16px (.ca-side__head).
# A plain <Modal> keeps its ✕ (closable defaults true) and its backdrop closes.

@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("theme", ["light", "dark"])
async def test_ordinary_confirm_unchanged(ui, lang, theme):
    await ui.evaluate("([l, t]) => window.__confirm(l, t)", [lang, theme])
    modal = ui.locator(".ca-modal")
    await modal.wait_for()
    card = ui.locator(".ca-modal__card")
    assert "ca-overquote" not in (await card.get_attribute("class"))
    assert await card.locator(".ca-side__head button").count() == 0, "main: ordinary confirms have no ✕"
    c = await card.bounding_box()
    title = await card.locator(".ca-side__head > span").first.bounding_box()
    body = await card.locator(".ca-rename__body > div").first.bounding_box()
    assert abs(body["x"] - c["x"] - 20) < 0.5, (c, body)  # main's body indent: 20px
    assert abs(title["x"] - c["x"] - 16) < 0.5, (c, title)
    await ui.mouse.click(6, 6)  # backdrop
    await modal.wait_for(state="detached")
    assert await ui.evaluate("window.__log") == ["cancel"]


async def test_plain_modal_keeps_close_x_and_backdrop(ui):
    await ui.evaluate("window.__modal()")
    modal = ui.locator(".ca-modal")
    await modal.wait_for()
    assert await modal.locator(".ca-side__head button").count() == 1, "Modal default closable=true shows ✕"
    await ui.mouse.click(6, 6)
    await ui.wait_for_function("window.__log.length === 1")
    assert await ui.evaluate("window.__log") == ["close"]


# Seedream → flare is the #133 table; a failed A then a declined B must not fall back (#393 P0).
_FAIL = ("generate_image", {"prompt": "cat fail", "model": "bytedance/seedream-v5.0-pro"})
_SEEDREAM_FAIL = json.dumps({"status": "failed", "error": "WaveSpeed task failed",
                             "model": "bytedance/seedream-v5.0-pro"})


def _fail_then_queue():
    state = {"n": 0}

    def mcp(name, args, i):
        if name == "ask_user":
            # would agree to a #236 switch if asked — the break→pass mutant would then spend
            return json.dumps({"status": "answered", "selected": ["yes"]})
        if name != "generate_image":
            return json.dumps({"ok": True})
        if args.get("fallback_for"):
            return json.dumps({"ids": ["fb"], "status": "queued"})
        state["n"] += 1
        if state["n"] == 1:
            return _SEEDREAM_FAIL
        return json.dumps({"ids": [f"job-{i}"], "status": "queued"})
    return mcp


@pytest.mark.parametrize("how", ["click", "esc"])
async def test_decline_after_failed_call_blocks_fallback(monkeypatch, bot_client, store, ui, how):
    """Call A model-fails (fallback-eligible); call B is over-quote; decline by 先到这里 click or Esc.
    Assert: no #236 fallback ask, no paid fallback MCP call, run ends quote_declined."""
    run = Run(monkeypatch, bot_client, store, prices=[0.3, 9.0],
              script=lambda m, n: calls(_FAIL, gen(1)) if n == 0 else reply("done"),
              mcp=_fail_then_queue())
    await run.start()
    b = await run.pending(1)
    assert b["kind"] == OVER_QUOTE["kind"]
    n_asks = len(run.asks)
    if how == "click":
        await click(ui, b, run.chat, "先到这里")
    else:
        await show(ui, b, run.chat)
        n = len(ui.hits)
        await ui.keyboard.press("Escape")
        hit = await wait_hit(ui, n)
        assert hit["body"]["selected"] == [OVER_QUOTE["decline"]]
    blocks, stops = await run.done()
    assert stops[-1]["copy"]["key"] == "user_stop:quote_declined"
    assert len(run.asks) == n_asks, "no second over-quote and no fallback ask_user card"
    assert not any(c[0] == "ask_user" for c in run.r.mcp), run.r.mcp
    assert not any(c[1].get("fallback_for") for c in run.r.mcp if c[0] == "generate_image"), run.r.mcp


async def test_overquote_body_indent_16_ordinary_stays_20(monkeypatch, bot_client, store, ui):
    """EL: on main eca71bc ordinary Confirm body indent is 20px; over-quote card is 16px."""
    await ui.evaluate("([l, t]) => window.__confirm(l, t)", ["zh", "light"])
    card = ui.locator(".ca-modal__card")
    await card.wait_for()
    c = await card.bounding_box()
    body = await card.locator(".ca-rename__body > div").first.bounding_box()
    assert abs(body["x"] - c["x"] - 20) < 0.5, (c, body)
    await ui.mouse.click(6, 6)
    await ui.locator(".ca-modal").wait_for(state="detached")
    run = Run(monkeypatch, bot_client, store, prices=[9.0],
              script=lambda m, n: calls(GEN) if n == 0 else reply("done"))
    await run.start()
    b = await run.pending(1)
    modal = await show(ui, b, run.chat)
    card = modal.locator(".ca-modal__card")
    c = await card.bounding_box()
    body = await card.locator(".ca-rename__body > div").first.bounding_box()
    assert abs(body["x"] - c["x"] - 16) < 0.5, (c, body)
    await click(ui, b, run.chat, "先到这里")
    await run.done()


async def test_fallback_over_quote_decline_blocks_paid_fallback(monkeypatch, bot_client, store, ui):
    """#393: a paid call fails; the #236 fallback would exceed the remaining quote → over-quote card
    from paid_gate inside `_maybe_model_fallback` (not the pending_stop/break path). Declining it must
    produce zero fallback MCP calls. Deleting that paid_gate block makes this red; the break-path tests stay green."""
    state = {"n": 0}

    def mcp(name, args, i):
        if name == "ask_user":
            # agree to the #236 switch so we reach paid_gate for the fallback submit
            return json.dumps({"status": "answered", "selected": ["yes"]})
        if name != "generate_image":
            return json.dumps({"ok": True})
        if args.get("fallback_for"):
            return json.dumps({"ids": ["fb"], "status": "queued"})
        state["n"] += 1
        # the only primary call fails (Seedream → Flare is the #133 backup)
        return json.dumps({"status": "failed", "error": "WaveSpeed task failed",
                           "model": "bytedance/seedream-v5.0-pro"})

    # credits 1.0; primary costs 0.3 (affordable, fails); fallback priced 9.0 → over-quote via paid_gate
    run = Run(monkeypatch, bot_client, store, prices=[0.3, 9.0], usd=1.0,
              script=lambda m, n: calls(_FAIL) if n == 0 else reply("done"),
              mcp=mcp)
    await run.start()
    b = await run.pending(1)
    assert b["kind"] == OVER_QUOTE["kind"] and b.get("credits") == 900, b
    # primary ran and failed; no fallback submit yet; the ask is the fallback's over-quote (paid_gate)
    assert state["n"] == 1 and not any(c[1].get("fallback_for") for c in run.r.mcp if c[0] == "generate_image")
    assert any(c[0] == "ask_user" for c in run.r.mcp), "must have agreed to the #236 switch before paid_gate"
    await click(ui, b, run.chat, "先到这里")
    blocks, stops = await run.done()
    assert stops[-1]["copy"]["key"] == "user_stop:quote_declined"
    assert not any(c[1].get("fallback_for") for c in run.r.mcp if c[0] == "generate_image"), run.r.mcp
    assert len([c for c in run.r.mcp if c[0] == "generate_image"]) == 1  # primary only
