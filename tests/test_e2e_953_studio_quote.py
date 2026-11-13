"""#953 Full App regressions (mock WaveSpeed / scripted LLM only, $0).

Studio: the model the user checked must be the one submitted (stale Auto
model_choice must not override it). Agent: quote-card copy and task-history
attribution must agree with the model that actually ran.

Set CA_953_SHOTS to write review screenshots (native Full App UI, including
quote cards and real hover tips). Tracked docs/qa PNGs are not written.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from PIL import Image, ImageDraw

from ComfyArt.api import wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.providers import BotEvent, register_provider
from conftest import FakeProvider, write_settings
from test_wavespeed import MODELS

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
SHOT = Path(os.environ.get("CA_953_SHOTS", "/tmp/953-fullapp/new-tip"))
QEDIT = "wavespeed-ai/qwen-image-2.0/edit"
FLARE = "openai/gpt-image-2.6-flare/text-to-image"
GPT2 = "openai/gpt-image-2/text-to-image"
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("index.html")), reason="needs built dist/")


async def _launch(p):
    """Firefox for the QA / design harness when installed; Chromium ($0) elsewhere."""
    try:
        return await p.firefox.launch()
    except Exception as firefox_error:
        try:
            return await p.chromium.launch()
        except Exception as chromium_error:
            pytest.skip(f"no Playwright browser: firefox={firefox_error}; chromium={chromium_error}")


def _label_png(path: Path, w: int, h: int, rgb: tuple[int, int, int], label: str) -> bytes:
    img = Image.new("RGB", (w, h), rgb)
    ImageDraw.Draw(img).text((16, 16), label, fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = path
    img.save(buf, format="PNG")
    return path.read_bytes()


@pytest.fixture
async def mock_ws(monkeypatch, fresh_user_dir):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    out = _label_png(SHOT / "mock-result.png", 1024, 1024, (32, 96, 64), "MOCK #953 (no paid call)")
    state = {"submits": [], "uploads": 0, "png": out}
    for bucket in (wavespeed._quotes, wavespeed._map_cache, wavespeed._jobs, wavespeed._submits):
        bucket.clear()
    models = list({m["model_id"]: m for m in MODELS + list(FIXTURE.values())}.values())
    app = web.Application(client_max_size=80 * 2**20)

    async def models_route(_request):
        return web.json_response({"code": 200, "data": models})

    async def price(request):
        body = await request.json()
        return web.json_response({"code": 200, "data": {"model_id": body.get("model_id"), "price": 0.02, "unit_price": 0.02, "currency": "USD"}})

    async def upload(request):
        state["uploads"] += 1
        reader = await request.multipart()
        async for part in reader:
            await part.read()
        return web.json_response({"code": 200, "data": {"download_url": str(request.url.with_path(f"/cdn/up{state['uploads']}.png").with_query(None))}})

    async def submit(request):
        state["submits"].append((request.match_info["model"], await request.json()))
        return web.json_response({"code": 200, "data": {"id": f"task{len(state['submits'])}", "status": "created"}})

    async def result(request):
        data = {"id": request.match_info["id"], "status": "completed",
                "outputs": [str(request.url.with_path("/cdn/out.png").with_query(None))], "error": ""}
        return web.json_response({"code": 200, "data": data})

    async def balance(_request):
        return web.json_response({"code": 200, "data": {"balance": 10}})

    async def cdn(_request):
        return web.Response(body=state["png"], content_type="image/png")

    app.router.add_get("/api/v3/models", models_route)
    app.router.add_get("/api/v3/balance", balance)
    app.router.add_post("/api/v3/model/price", price)
    app.router.add_post("/api/v3/media/upload/binary", upload)
    app.router.add_get("/api/v3/predictions/{id}/result", result)
    app.router.add_post("/api/v3/{model:.+}", submit)
    app.router.add_get("/cdn/out.png", cdn)
    app.router.add_get("/cdn/{name}", cdn)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    original = wavespeed.load_config

    def fixture_config():
        cfg = copy.deepcopy(original())
        for feature, mid in (
            ("text_to_image", "wavespeed-ai/qwen-image-2.0/text-to-image"),
            ("image_edit", QEDIT),
        ):
            rows = cfg["features"][feature]["models"]
            if not any(m["id"] == mid for m in rows):
                rows.append({"id": mid})
        return cfg

    monkeypatch.setattr(wavespeed, "load_config", fixture_config)
    monkeypatch.setattr(canvas, "load_config", fixture_config)
    yield state
    await server.close()


@pytest.fixture
async def app_url(mock_ws, monkeypatch):
    import folder_paths
    from server import PromptServer

    monkeypatch.setattr(folder_paths, "folder_names_and_paths", {}, raising=False)
    base = folder_paths.STATE["base"]
    for folder in ("input", "output", "temp", "user/default"):
        os.makedirs(base / folder, exist_ok=True)
    app = web.Application(client_max_size=200 * 2**20)
    app.router.add_routes(PromptServer.instance.routes)
    for route in PromptServer.instance.routes:
        if isinstance(route, web.RouteDef):
            app.router.add_route(route.method, "/api" + route.path, route.handler)

    async def view(request):
        query = request.query
        path = base / query.get("type", "output") / query.get("subfolder", "") / query["filename"]
        return web.FileResponse(path) if path.is_file() else web.Response(status=404)

    async def wsock(request):
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        async for _ in socket:
            pass
        return socket

    def js(value):
        async def handle(_request):
            return web.json_response(value)
        return handle

    async def upload_image(request):
        form = await request.post()
        f, sub, kind = form["image"], form.get("subfolder", ""), form.get("type", "input")
        target = base / kind / sub / f.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.file.read())
        return web.json_response({"name": f.filename, "subfolder": sub, "type": kind})

    async def ud_get(request):
        path = base / "user/default" / request.match_info["file"]
        return web.FileResponse(path) if path.is_file() else web.Response(status=404)

    async def ud_post(request):
        path = base / "user/default" / request.match_info["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(await request.read())
        return web.json_response(request.match_info["file"])

    app.router.add_get("/api/userdata/{file:.+}", ud_get)
    app.router.add_post("/api/userdata/{file:.+}", ud_post)
    app.router.add_post("/api/upload/image", upload_image)
    app.router.add_get("/api/view", view)
    app.router.add_get("/ws", wsock)
    app.router.add_get("/api/queue", js({"queue_running": [], "queue_pending": []}))
    app.router.add_get("/api/settings/{id}", js(None))
    app.router.add_get("/api/userdata", js([]))
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(PromptServer.instance, "port", server.port)
    yield str(server.make_url("/comfyart/"))
    await server.close()


class ChoiceProvider(FakeProvider):
    id = "fake-953"
    label = "Fake953"

    def __init__(self, args: dict, user: str):
        super().__init__()
        self.args, self.user = dict(args), user
        self.results: list = []
        self.quote = None

    async def send(self, turn, emit, handle):
        import aiohttp
        from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
        from ComfyArt.bot.local_llm import LocalLlmProvider
        from ComfyArt.bot.plan_quote import build_quote

        async def price(model, inputs):
            return 0.02

        async def models(feature):
            return []

        token = BOT_CHAT_ID.set(turn.chat_id)
        try:
            self.quote = await build_quote(
                [{"text": "MOCK #953", "tool": "generate_image", "model": self.args.get("model") or "",
                  "arguments": self.args}],
                turn.lang, threshold=0.0, pricer=price, models_for=models, router=canvas.quote_route,
            )
        finally:
            BOT_CHAT_ID.reset(token)
        assert self.quote
        go = await LocalLlmProvider._confirm_plan(self, self.quote.ask_spec(), turn, handle)
        if go != "start":
            return self.result

        async def call(name, arguments, idx):
            await emit(BotEvent(t="tool_use", id=str(idx), name=name, input=arguments))
            async with aiohttp.ClientSession() as http:
                async with http.post(turn.mcp_endpoint, json={"jsonrpc": "2.0", "id": idx, "method": "tools/call",
                                                              "params": {"name": name, "arguments": arguments}}) as r:
                    res = await r.json()
            txt = res.get("result", {}).get("content", [{}])[0].get("text", "")
            await emit(BotEvent(t="tool_result", id=str(idx), name=name, text=txt,
                                is_error=res.get("result", {}).get("isError", False)))
            return json.loads(txt)

        gen = await call("generate_image", self.args, 1)
        self.results.append(gen)
        if gen.get("ids"):
            self.results.append(await call("wait_generation", {"ids": gen["ids"], "timeout_s": 30}, 2))
        await emit(BotEvent(t="delta", text="MOCK #953: image placed."))
        return self.result


async def test_studio_manual_gpt_image_2_is_the_submitted_model(app_url, mock_ws):
    """Full App Studio: Auto off, GPT Image 2 checked → that id is the sole submit."""
    SHOT.mkdir(parents=True, exist_ok=True)
    mock_ws["png"] = _label_png(SHOT / "studio-mock.png", 1024, 1024, (32, 96, 64), "MOCK #953 studio")
    intended = GPT2
    async with pw.async_playwright() as p:
        browser = await _launch(p)
        page = await browser.new_page(viewport={"width": 1600, "height": 1000})
        await page.add_init_script("localStorage.setItem('comfyart.lang','en'); localStorage.setItem('comfyart.e2e','1')")
        await page.goto(app_url)
        await page.wait_for_timeout(1000)
        await page.mouse.click(28, 83)
        await page.locator(".tl-canvas").wait_for()
        await page.wait_for_timeout(600)
        if await page.locator(".ca-modal").count():
            await page.keyboard.press("Escape")
        await page.locator(".ca-dock .ca-split .ca-bar__btn").first.click()
        await page.locator(".ca-gen__prompt").wait_for()
        await page.locator(".ca-gen__prompt").fill("a cup of coffee on a table")
        await page.wait_for_timeout(1600)
        await page.locator(".ca-gen [data-pill=model], .ca-genpanel [data-pill=model], .ca-gen__foot [data-pill=model]").first.click()
        menu = page.get_by_test_id("model-menu")
        await menu.wait_for()
        switch = menu.locator("[role=switch]")
        if await switch.get_attribute("aria-checked") == "true":
            await switch.click()
        row = menu.locator('button[title="' + intended + '"]')
        await row.scroll_into_view_if_needed()
        await row.click()
        modelbutton = page.locator(".ca-gen__foot [data-pill=model]")
        assert await modelbutton.get_attribute("data-model") == intended
        await page.wait_for_timeout(1000)
        await modelbutton.click()
        await page.screenshot(path=str(SHOT / "studio-en-manual-selected.png"))
        await page.keyboard.press("Escape")
        await page.locator(".ca-gen__send").click()
        for _ in range(100):
            if mock_ws["submits"]:
                break
            b = page.locator(".ca-modal .ca-panel__primary")
            if await b.count() and await b.first.is_visible():
                await b.first.click()
            await page.wait_for_timeout(150)
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(SHOT / "studio-en-submitted.png"))
        await browser.close()
        assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
        assert mock_ws["submits"][0][0] == intended


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_studio_manual_pick_of_the_same_model_after_auto_is_manual(app_url, mock_ws, lang):
    """#953 QA HOLD: Auto estimate (Flare) → Auto off → user checks the same Flare id → Generate.

    The submitted model must not change, and the estimate / result source must be the
    user's manual pick (no Auto), in zh and en. Full App mock, $0.
    """
    SHOT.mkdir(parents=True, exist_ok=True)
    mock_ws["png"] = _label_png(SHOT / f"studio-same-mock-{lang}.png", 1024, 1024, (32, 96, 64), "MOCK #953 same-id")
    estimates: list[dict] = []
    async with pw.async_playwright() as p:
        browser = await _launch(p)
        page = await browser.new_page(viewport={"width": 1600, "height": 1000})
        await page.add_init_script(
            f"localStorage.setItem('comfyart.lang','{lang}'); localStorage.setItem('comfyart.e2e','1')")

        async def watch_estimate(route):
            response = await route.fetch()
            try:
                body = await response.json()
            except Exception:
                body = {}
            estimates.append({"request": route.request.post_data_json, "response": body})
            await route.fulfill(response=response)

        await page.route("**/comfyart/wavespeed/estimate", watch_estimate)
        await page.goto(app_url)
        await page.wait_for_timeout(1000)
        await page.mouse.click(28, 83)
        await page.locator(".tl-canvas").wait_for()
        await page.wait_for_timeout(600)
        if await page.locator(".ca-modal").count():
            await page.keyboard.press("Escape")
        await page.locator(".ca-dock .ca-split .ca-bar__btn").first.click()
        await page.locator(".ca-gen__prompt").wait_for()
        await page.locator(".ca-gen__prompt").fill("a cup of coffee on a table")
        # 1) wait for the Auto estimate: the card is on Auto · Flare before the user acts
        await page.wait_for_function(
            "() => { const e = document.querySelector('[data-testid=auto-model-label]');"
            " return !!e && (e.textContent || '').includes('Auto') }", timeout=30000)
        modelbutton = page.locator(".ca-gen__foot [data-pill=model]")
        assert await modelbutton.get_attribute("data-auto") == "true"
        # 2) Auto off, then explicitly check the same Flare row
        await modelbutton.click()
        menu = page.get_by_test_id("model-menu")
        await menu.wait_for()
        switch = menu.locator("[role=switch]")
        assert await switch.get_attribute("aria-checked") == "true"
        await switch.click()
        assert await switch.get_attribute("aria-checked") != "true"
        row = menu.locator('button[title="' + FLARE + '"]')
        await row.scroll_into_view_if_needed()
        await row.click()
        assert await modelbutton.get_attribute("data-model") == FLARE
        assert await modelbutton.get_attribute("data-auto") is None
        # 3) after Auto off + the explicit same-id pick, the estimate for this card is a user
        #    pick, not the old Auto record. (The first Auto estimate above is auto=true.)
        assert any(
            ((e.get("response") or {}).get("model_choice") or {}).get("auto") is True for e in estimates
        ), [e.get("request") for e in estimates]
        manual: list[dict] = []
        for _ in range(100):
            manual = [e for e in estimates
                      if ((e.get("response") or {}).get("model_choice") or {}).get("model") == FLARE
                      and ((e.get("response") or {}).get("model_choice") or {}).get("auto") is False]
            if manual:
                break
            await page.wait_for_timeout(100)
        assert manual, [e.get("request") for e in estimates]
        assert manual[-1]["response"]["model"] == FLARE
        label = page.get_by_test_id("auto-model-label")
        await page.wait_for_function(
            "() => { const e = document.querySelector('[data-testid=auto-model-label]');"
            " return !!e && !(e.textContent || '').includes('Auto') }", timeout=10000)
        assert (await label.first.inner_text()).strip() == "GPT Image 2.6 Flare"
        # evidence: menu still shows Auto off + the same Flare checked
        await modelbutton.click()
        await menu.wait_for()
        assert await menu.locator('[role=switch]').get_attribute("aria-checked") != "true"
        assert await menu.locator('button[title="' + FLARE + '"]').get_attribute("data-on") is not None
        await page.screenshot(path=str(SHOT / f"studio-same-manual-selected-{lang}.png"))
        await page.keyboard.press("Escape")
        # 4) generate: the submitted model must stay Flare …
        await page.locator(".ca-gen__send").click()
        for _ in range(120):
            if mock_ws["submits"]:
                break
            b = page.locator(".ca-modal .ca-panel__primary")
            if await b.count() and await b.first.is_visible():
                await b.first.click()
            await page.wait_for_timeout(150)
        await page.wait_for_timeout(1000)
        # … and the result source must be the manual pick too (no Auto · label / no reason tip)
        target = page.get_by_test_id("auto-model-label")
        await page.wait_for_function(
            "() => { const e = document.querySelector('[data-testid=auto-model-label]');"
            " return !!e && !(e.textContent || '').includes('Auto') }", timeout=20000)
        assert (await target.first.inner_text()).strip() == "GPT Image 2.6 Flare"
        # manual source: no Auto hover reason is attached to the label (Auto cards set aria-label)
        assert await target.first.get_attribute("aria-label") is None
        assert await page.locator(".ca-tip").count() == 0
        await page.screenshot(path=str(SHOT / f"studio-same-submitted-{lang}.png"))
        await browser.close()
        assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
        assert mock_ws["submits"][0][0] == FLARE
        choice = manual[-1]["response"].get("model_choice") or {}
        assert choice.get("auto") is False
        assert choice.get("model") == FLARE


CASES = {
    "auto": (
        {"prompt": "beauty before after card", "skill": "before-after", "width": 1920, "height": 1080,
         "ratio": "16:9", "model": QEDIT, "refs": ["loose:0"]},
        "帮我做个前后对比，暗疮和肉色不均",
    ),
    "manual": (
        {"prompt": "a cup of coffee on a table", "model": FLARE},
        "Please use GPT Image 2.6 Flare for a cup of coffee",
    ),
}


@pytest.mark.parametrize("case,lang", [("auto", "zh"), ("auto", "en"), ("manual", "zh"), ("manual", "en")])
async def test_agent_quote_and_history_agree(app_url, mock_ws, monkeypatch, case, lang):
    """Quote copy, task-history pill, and the submitted model must agree."""
    from server import PromptServer
    from ComfyArt.api import mcp_commands

    SHOT.mkdir(parents=True, exist_ok=True)
    upload = SHOT / "upload-subject.png"
    _label_png(upload, 480, 640, (100, 50, 80), "MOCK #953 uploaded subject")
    dims = (1920, 1080) if case == "auto" else (1024, 1024)
    mock_ws["png"] = _label_png(SHOT / "mock-result.png", *dims, (32, 96, 64), "MOCK #953 (no paid call)")
    args, user = CASES[case]
    fake = ChoiceProvider(args, user)
    register_provider(fake)
    write_settings(**{"enable-mcp": True, "enable-bot": True, "bot-provider": fake.id, "bot-enable-review": False})
    sockets: list = []
    original = PromptServer.instance.send_sync

    def forward(event, data, sid=None):
        original(event, data, sid)
        for ws in list(sockets):
            try:
                ws.send(json.dumps({"type": event, "data": data}))
            except Exception:
                pass

    monkeypatch.setattr(PromptServer.instance, "send_sync", forward)
    relayed: list = []
    submit = canvas.submit_command

    async def capture(action, arguments, *a, **kw):
        if action == "generate_image":
            relayed.append(dict(arguments))
        return await submit(action, arguments, *a, **kw)

    monkeypatch.setattr(canvas, "submit_command", capture)
    async with pw.async_playwright() as p:
        browser = await _launch(p)
        ctx = await browser.new_context(viewport={"width": 1600, "height": 1000})
        await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
        page = await ctx.new_page()
        await page.add_init_script(
            f"localStorage.setItem('comfyart.lang','{lang}'); localStorage.setItem('comfyart.e2e','1')"
        )
        await page.goto(app_url)
        await page.wait_for_timeout(800)
        if args.get("skill"):
            await page.get_by_test_id("rail-skills").click()
            card = page.locator('[data-testid="skills-wall-card"][data-skill="' + args["skill"] + '"]')
            await card.scroll_into_view_if_needed()
            await card.hover()
            await card.get_by_test_id("skills-card-try").click()
            dlg = page.get_by_test_id("skill-run-dialog")
            await dlg.locator("input[type=file]").first.set_input_files(str(upload))
            await page.wait_for_timeout(600)
            await dlg.get_by_test_id("skill-run-go").click()
        else:
            await page.mouse.click(28, 83)
            await page.locator(".tl-canvas").wait_for()
        await page.locator(".ca-composer__input").wait_for(timeout=30000)
        await page.wait_for_timeout(600)
        if await page.locator(".ca-modal").count():
            await page.keyboard.press("Escape")
        await page.locator(".ca-composer__input").fill(user)
        await page.locator(".ca-composer").get_by_text(fake.label, exact=True).wait_for(timeout=15000)
        for client in mcp_commands._pages:
            PromptServer.instance.sockets[client] = object()
        await page.locator("button[data-slot=send]").click()
        await page.locator("[data-testid=chat-inline-confirm-desc]").wait_for(timeout=20000)
        quote_max = page.locator(".ca-agent .ca-wide-only")
        if await quote_max.count() and await quote_max.first.is_visible():
            await quote_max.first.click()
            await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT / f"{case}-{lang}-quote.png"))
        quote_text = (await page.locator("[data-testid=chat-inline-planquote]").inner_text()).strip()
        lines = [x.text for x in fake.quote.lines]
        blob = quote_text + "\n" + "\n".join(lines)
        if case == "auto":
            assert "你指定了这个模型" not in blob and "you named this model" not in blob.lower()
            assert any("Auto ·" in t for t in lines)
            assert any("before-after" in t or "Qwen" in t for t in lines)
        else:
            assert "你指定了这个模型" not in blob and "you named this model" not in blob.lower()
            assert all("Auto ·" not in t for t in lines)
        await page.locator(".ca-chat-confirm button").last.click()
        for _ in range(150):
            if fake.results and len(fake.results) > 1:
                break
            b = page.locator(".ca-modal .ca-panel__primary")
            if await b.count() and await b.first.is_visible():
                await b.first.click()
            await page.wait_for_timeout(150)
        await page.wait_for_function(
            "() => [...document.querySelectorAll('img.tl-image, .tl-image img')].some(e => e.naturalWidth > 0)"
        )
        await page.wait_for_timeout(400)
        target = page.get_by_test_id("auto-model-label")
        if await target.count():
            maximize = page.locator(".ca-agent .ca-wide-only")
            if await maximize.count() and await maximize.first.is_visible():
                await maximize.first.click()
                await page.wait_for_timeout(300)
            await target.first.hover()
            await page.wait_for_timeout(900)
            await page.screenshot(path=str(SHOT / f"{case}-{lang}-hover.png"))
            label = (await target.first.inner_text()).strip()
            tip = page.locator(".ca-tip")
            tip_text = (await tip.first.inner_text()).strip() if await tip.count() else ""
            if case == "auto":
                assert "Auto ·" in label
                assert "你指定了这个模型" not in tip_text and "you named this model" not in tip_text.lower()
                assert "before-after" in tip_text or "1920" in tip_text or "Qwen" in tip_text
            else:
                assert "Auto ·" not in label
                assert await tip.count() == 0
        assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
        submitted = mock_ws["submits"][0][0]
        if case == "auto":
            assert submitted == QEDIT
            choice = (fake.results[0] or {}).get("model_choice") or {}
            assert choice.get("auto") is True
            assert "你指定了这个模型" not in str(choice.get("reason"))
        else:
            assert submitted == FLARE
        await browser.close()
