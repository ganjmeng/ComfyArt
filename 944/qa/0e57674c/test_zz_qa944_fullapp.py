"""QA #944 @0e57674c ($0): Full App, Firefox, real mouse. Real HTTP composer route + real LocalLlmProvider
agent loop (LLM scripted). The agent's MCP generate_image/wait_generation go through the real backend pin
pipeline and then the page's own command handlers (HANDLERS, the same ones the agent bus calls), which submit
and poll through the real ComfyArt WaveSpeed routes against a LOCAL mock WaveSpeed. Nothing paid, keys unset."""
from __future__ import annotations
import asyncio, json, os
from pathlib import Path
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from ComfyArt.api import wavespeed
from test_agent_budget_391 import Rig, calls, reply, store  # noqa: F401
from test_e2e_skill_canvas_707 import _png, app_url  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_wavespeed import MODELS

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
SB_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SHOTS = Path(os.environ.get("QA944_SHOTS", "/tmp/qa944c/shots"))
ZH = "图片还在生成，生成好后会自动出现在画布上，不会重复扣费。"
EN = "The image is still generating. It will appear on the canvas when it's ready, with no extra charge."
LOG = []


@pytest.fixture
async def mock_ws(monkeypatch, fresh_user_dir):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    state = {"submits": [], "polls": 0, "status": "processing", "png": _png(1536, 864, (36, 96, 168), "QA944 mock")}
    for b in (wavespeed._quotes, wavespeed._map_cache, wavespeed._jobs, wavespeed._submits, wavespeed._uploaded):
        b.clear()
    have = {m.get("model_id") for m in MODELS}
    models = list(MODELS) + [FIXTURE[m] for m in (SB_T2I,) if m not in have and m in FIXTURE]
    app = web.Application()

    async def models_route(_r):
        return web.json_response({"code": 200, "data": models})

    async def price(r):
        b = await r.json()
        return web.json_response({"code": 200, "data": {"model_id": b.get("model_id"), "price": 0.09, "unit_price": 0.09, "currency": "USD"}})

    async def submit(r):
        state["submits"].append((r.match_info["model"], await r.json()))
        return web.json_response({"code": 200, "data": {"id": f"task{len(state['submits'])}", "status": "created"}})

    async def result(r):
        state["polls"] += 1
        st = state["status"]
        data = {"id": r.match_info["id"], "status": st, "outputs": [], "error": ""}
        if st == "completed":
            data["outputs"] = [str(r.url.with_path("/cdn/out.png").with_query(None))]
        return web.json_response({"code": 200, "data": data})

    async def balance(_r):
        return web.json_response({"code": 200, "data": {"balance": 10}})

    async def cdn(_r):
        return web.Response(body=state["png"], content_type="image/png")
    app.router.add_get("/api/v3/models", models_route)
    app.router.add_get("/api/v3/balance", balance)
    app.router.add_post("/api/v3/model/price", price)
    app.router.add_get("/api/v3/predictions/{id}/result", result)
    app.router.add_post("/api/v3/{model:.+}", submit)
    app.router.add_get("/cdn/out.png", cdn)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    # shorten the local poll cap (prod 30 min) so the "past local cap, keep polling, no resubmit" path runs
    monkeypatch.setattr(wavespeed, "IMAGE_JOB_TIMEOUT", 2.0)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    yield state
    await server.close()


def _pin(args):
    from ComfyArt.api.mcp_tools import canvas
    choice = canvas._auto_choice("generate_image", dict(args))
    return canvas._pin_args(dict(args), choice) if choice else dict(args)


SHAPES = """() => { const ed = window.__caEditor; return ed.getCurrentPageShapes().map(s => ({id: s.id, type: s.type,
  x: Math.round(s.x), y: Math.round(s.y), w: Math.round(s.props.w || 0), h: Math.round(s.props.h || 0),
  status: s.props.status || s.meta?.status || '', gen: !!(s.meta && (s.meta.generating || s.meta.pending)), meta: s.meta})) }"""


async def _send(pg, text):
    box = await pg.locator(".ca-composer__input").bounding_box()
    await pg.mouse.click(box["x"] + 30, box["y"] + 15)
    await pg.keyboard.type(text)
    btn = await pg.locator(".ca-composer__slotwrap > :not([hidden])").bounding_box()
    await pg.mouse.move(btn["x"] + btn["width"] / 2, btn["y"] + btn["height"] / 2)
    await pg.mouse.down(); await pg.mouse.up()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_qa944_fullapp(app_url, mock_ws, fake_tools, monkeypatch, store, lang, theme):  # noqa: F811
    from ComfyArt.bot import providers as registry
    from ComfyArt.api.bot_turns import ACTIVE_TURNS
    holder = {}
    r = None

    def script(messages, n):
        if n == 0:
            return calls(("generate_image", {"prompt": "QA944 banner local fixture", "ratio": "16:9"}))
        if holder.get("ids"):
            return calls(("wait_generation", {"ids": holder["ids"]}))
        return reply("no ids")

    r = Rig(monkeypatch, script, store=store, prices={"generate_image": 0.09})
    async def bridge(session, endpoint, name, arguments):
        r.mcp.append((name, dict(arguments)))
        pg = holder["pg"]
        if name == "generate_image":
            out = await pg.evaluate("async (a) => window.__comfyartE2E.command('generate_image', a)", _pin(arguments))
            assert out["ok"], out
            holder["ids"] = out["result"]["ids"]
            await asyncio.sleep(1.0)
            await pg.evaluate("() => window.__caEditor.zoomToFit({ animation: { duration: 0 } })")
            await asyncio.sleep(0.5)
            holder["canvas_text_gen"] = await pg.locator(".tl-canvas").inner_text()
            await pg.screenshot(path=str(SHOTS / f"944-qa-{lang}-1-generating.png"))
            holder["shapes_gen"] = await pg.evaluate(SHAPES)
            return json.dumps(out["result"]), []
        if name == "wait_generation":
            out = await pg.evaluate("async (a) => window.__comfyartE2E.command('wait_generation', a)",
                                    {"ids": arguments.get("ids"), "timeout_s": 3})
            r.clock.t += 601  # each wait stands in for ~10 min on the run clock (30-min agent cap after 3)
            LOG.append((lang, "wait", out.get("result", {}).get("status") if out.get("ok") else out))
            return json.dumps(out["result"] if out["ok"] else out), []
        return json.dumps({}), []
    monkeypatch.setattr(r.p, "_mcp_call_tool", bridge)
    monkeypatch.setitem(registry._REGISTRY, "local-llm", r.p)
    SHOTS.mkdir(parents=True, exist_ok=True)
    async with pw.async_playwright() as p:
        browser = await p.firefox.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1,
                                        locale="zh-CN" if lang == "zh" else "en-US")
        pg = await ctx.new_page()
        holder["pg"] = pg
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}');localStorage.setItem('comfyart.e2e','1')")
        await pg.goto(app_url)
        await pg.wait_for_timeout(1500)
        await pg.mouse.click(28, 83)
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(150)
        await pg.wait_for_function("() => window.__comfyartE2E && window.__comfyartE2E.listed().length > 0")
        await pg.evaluate("() => window.__comfyartE2E.setPrefs({ auto: true, enabled: [] })")
        await _send(pg, "画一张横幅" if lang == "zh" else "Draw a banner")
        for _ in range(600):
            if r.n >= 2 and not ACTIVE_TURNS:
                break
            await asyncio.sleep(0.1)
        assert not ACTIVE_TURNS, ("turn still active", r.n, r.mcp)
        run = store.list_runs(owner_id=None) if hasattr(store, "list_runs") else None
        LOG.append((lang, "mcp", [n for n, _ in r.mcp], "llm_n", r.n, "submits", len(mock_ws["submits"]),
                    "jobs", {k: dict(v) if isinstance(v, dict) else str(v) for k, v in list(wavespeed._jobs.items())[:2]}))
        gen_shapes = holder.get("shapes_gen")
        LOG.append((lang, "shapes_gen", gen_shapes))
        await pg.reload()
        await pg.wait_for_timeout(1500)
        await pg.locator(".ca-split__chev").first.click(timeout=8000)
        await pg.locator(".ca-history__item").first.click(timeout=8000)
        card = pg.locator("[data-testid=run-stop-still-generating]").first
        await card.wait_for(timeout=10000)
        text = (await card.inner_text()).strip()
        want = ZH if lang == "zh" else EN
        assert want in text, text
        for bad in ("任务卡住了", "已停止", "继续生成", "Continue generating"):
            assert bad not in text
        assert await card.locator("button").count() == 0
        await pg.wait_for_timeout(800)
        shapes_after_cap = await pg.evaluate(SHAPES)
        LOG.append((lang, "canvas_text_gen", holder.get("canvas_text_gen"), "after_cap", await pg.locator(".tl-canvas").inner_text()))
        LOG.append((lang, "shapes_after_cap_reload", shapes_after_cap))
        await pg.screenshot(path=str(SHOTS / f"944-qa-{lang}-2-still-generating.png"))
        assert len(mock_ws["submits"]) == 1
        mock_ws["status"] = "completed"
        for _ in range(300):
            sh = await pg.evaluate(SHAPES)
            if any(s["type"] == "image" for s in sh) and not any(s.get("gen") for s in sh):
                break
            await asyncio.sleep(0.2)
        await pg.wait_for_timeout(1500)
        final = await pg.evaluate(SHAPES)
        LOG.append((lang, "shapes_final", final, "submits", len(mock_ws["submits"]), "polls", mock_ws["polls"]))
        await pg.screenshot(path=str(SHOTS / f"944-qa-{lang}-3-landed.png"))
        Path(f"/tmp/qa944c/fullapp-{lang}.json").write_text(json.dumps(LOG, ensure_ascii=False, default=str, indent=1))
        assert len(mock_ws["submits"]) == 1
        await browser.close()
