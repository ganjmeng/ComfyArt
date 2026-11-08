"""#707 local canvas chain. Not a provider pass.

The real built app runs in headless Chromium against the real ComfyArt routes.
Those routes talk only to a local mock WaveSpeed. Each skill card is given the
declared pixels and a size lock, then the user presses generate.

The CDN returns a PNG this file drew in memory and labeled LOCAL FIXTURE.
A matching file is placed on the canvas; the browser reads that image's
natural pixels. A different file is refused and no image is placed.
Nothing here calls a paid API or claims the picture is a real supplier result.
"""
from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from PIL import Image, ImageDraw

from ComfyArt.api import wavespeed
from ComfyArt.api.skill_size import linkedin_decision
from test_wavespeed import MODELS

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
QWEN = "wavespeed-ai/qwen-image-2.0/text-to-image"
SHOTS = ROOT / "docs/qa/707-local-canvas"
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("index.html")), reason="needs built dist/")

# Declared skill pixels. The pictures are solid local fixtures, not layouts and not supplier files.
SKILLS = (
    ("before-after", 1024, 1280, "4:5", (176, 48, 48)),
    ("pose-fission", 1536, 2048, "3:4", (36, 96, 168)),
    ("game-art", 1024, 1824, "9:16", (32, 128, 72)),
    ("linkedin-banner", 1584, 396, "4:1", (168, 120, 36)),
)


def _png(w: int, h: int, rgb: tuple[int, int, int], label: str) -> bytes:
    img = Image.new("RGB", (w, h), rgb)
    draw = ImageDraw.Draw(img)
    draw.text((16, 16), f"LOCAL FIXTURE {label} {w}x{h}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
async def mock_ws(monkeypatch, fresh_user_dir):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    state = {"submits": [], "png": _png(8, 8, (0, 0, 0), "unset")}
    for bucket in (wavespeed._quotes, wavespeed._map_cache, wavespeed._jobs, wavespeed._submits):
        bucket.clear()
    models = [m for m in MODELS if m.get("model_id") != QWEN] + [FIXTURE[QWEN]]
    app = web.Application(client_max_size=80 * 2**20)

    async def models_route(_request):
        return web.json_response({"code": 200, "data": models})

    async def price(request):
        body = await request.json()
        return web.json_response({"code": 200, "data": {"model_id": body.get("model_id"), "price": 0.02, "unit_price": 0.02, "currency": "USD"}})

    async def submit(request):
        state["submits"].append((request.match_info["model"], await request.json()))
        return web.json_response({"code": 200, "data": {"id": f"task{len(state['submits'])}", "status": "created"}})

    async def result(request):
        data = {"id": request.match_info["id"], "status": "completed", "outputs": [str(request.url.with_path("/cdn/out.png").with_query(None))], "error": ""}
        return web.json_response({"code": 200, "data": data})

    async def balance(_request):
        return web.json_response({"code": 200, "data": {"balance": 10}})

    async def cdn(_request):
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
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    yield state
    await server.close()


@pytest.fixture
async def app_url(mock_ws, monkeypatch):
    import os
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

    app.router.add_get("/api/view", view)
    app.router.add_get("/ws", wsock)
    app.router.add_get("/api/queue", js({"queue_running": [], "queue_pending": []}))
    app.router.add_get("/api/settings/{id}", js(None))
    app.router.add_get("/api/userdata", js([]))
    server = TestServer(app)
    await server.start_server()
    yield str(server.make_url("/comfyart/"))
    await server.close()


async def _until(fn, timeout=25.0):
    for _ in range(int(timeout * 10)):
        if await fn():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("timed out")


def _auto_banner_args() -> dict:
    """The args the linkedin auto path sends to the page. Not a hand-built card."""
    decision = linkedin_decision(
        {"prompt": "local auto banner", "skill": "linkedin-banner", "width": 1584, "height": 396},
        FIXTURE, wavespeed.load_config())
    assert "block" not in decision
    args = decision["args"]
    assert args["model"] == QWEN and args["size_lock"] is True
    assert args["size_candidates"] == [QWEN]
    assert "openai/gpt-image-2.5-flare/text-to-image" not in args["size_candidates"]
    return args


async def _boot(page, app_url: str):
    await page.add_init_script("localStorage.setItem('comfyart.lang','zh'); localStorage.setItem('comfyart.e2e','1')")
    await page.goto(app_url)
    await page.wait_for_timeout(1500)
    await page.mouse.click(28, 83)
    await page.locator(".tl-canvas").wait_for()
    await page.wait_for_timeout(800)
    if await page.locator(".ca-modal").count():
        await page.locator(".ca-modal button").nth(-2).click()
    await page.wait_for_function("() => window.__comfyartE2E && window.__comfyartE2E.listed().includes('openai/gpt-image-2.5-flare/text-to-image')")


async def test_auto_entry_respects_disabled_qwen_and_does_not_call_upstream(app_url, mock_ws):
    """Agent generate_image args go through the real command handler, not a pre-filled card."""
    args = _auto_banner_args()
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        page = await browser.new_page(viewport={"width": 1280, "height": 800}, locale="zh-CN")
        await _boot(page, app_url)
        listed = await page.evaluate("() => window.__comfyartE2E.listed()")
        assert QWEN not in listed
        assert "openai/gpt-image-2.5-flare/text-to-image" in listed

        async def command(payload):
            return await page.evaluate(
                """async (args) => window.__comfyartE2E.command('generate_image', args)""",
                payload,
            )

        await page.evaluate("(enabled) => window.__comfyartE2E.setPrefs({ auto: false, enabled })", listed)
        disabled = await command(args)
        assert disabled["ok"] is False
        assert "没有可用的尺寸兼容模型" in disabled["error"]
        assert "没有提交" in disabled["error"]
        assert "这次生成没有完成" not in disabled["error"]
        assert mock_ws["submits"] == []

        none = await command({**args, "model": QWEN, "size_candidates": [QWEN, "wavespeed-ai/qwen-image-2.0/edit"]})
        assert none["ok"] is False
        assert "没有可用的尺寸兼容模型" in none["error"]
        assert mock_ws["submits"] == []

        await page.evaluate("() => window.__comfyartE2E.setPrefs({ auto: true, enabled: [] })")
        allowed = await command(args)
        assert mock_ws["submits"], allowed
        model, payload = mock_ws["submits"][-1]
        assert model == QWEN
        assert payload.get("size") == "1584*396"
        assert "size_lock" not in payload
        assert all(m != "openai/gpt-image-2.5-flare/text-to-image" for m, _ in mock_ws["submits"])
        assert len(mock_ws["submits"]) == 1
        await browser.close()


async def test_skill_cards_place_matching_fixture_and_refuse_a_different_one(app_url, mock_ws):
    """Real generate button, local fixture file, canvas pixels or an explicit refusal."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        page = await browser.new_page(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        await page.add_init_script("localStorage.setItem('comfyart.lang','zh')")
        await page.goto(app_url)
        await page.wait_for_timeout(1500)
        await page.mouse.click(28, 83)  # home: new project
        await page.locator(".tl-canvas").wait_for()
        await page.wait_for_timeout(1200)
        if await page.locator(".ca-modal").count():
            await page.locator(".ca-modal button").nth(-2).click()
        await page.wait_for_function("() => window.__caEditor")

        for skill, width, height, ratio, rgb in SKILLS:
            await _case(page, mock_ws, skill, width, height, ratio, rgb, match=True)
            await _case(page, mock_ws, skill, width, height, ratio, rgb, match=False)
        await browser.close()


async def _case(page, mock_ws, skill, width, height, ratio, rgb, match: bool):
    wrong = (2048, 682)
    fw, fh = (width, height) if match else wrong
    mock_ws["png"] = _png(fw, fh, rgb if match else (20, 20, 20), skill if match else f"{skill}-wrong")
    before = len(mock_ws["submits"])
    await page.evaluate("() => { const ed = window.__caEditor; ed.selectAll(); ed.deleteShapes(ed.getSelectedShapeIds()) }")
    await page.get_by_role("button", name="图像生成").first.click()
    await page.locator(".ca-gen__prompt").wait_for()
    await page.evaluate(
        """([skill, width, height, ratio, model]) => {
          const ed = window.__caEditor
          const id = ed.getSelectedShapeIds()[0]
          const shape = ed.getShape(id)
          ed.updateShape({
            id, type: 'generator',
            props: { ...shape.props, prompt: 'local fixture ' + skill, resolution: 'custom', ratio, cw: width, ch: height, w: width, h: height },
            meta: { ...shape.meta, pixelSize: [width, height], sizeLockModel: model, quiet: false },
          })
        }""",
        [skill, width, height, ratio, QWEN],
    )
    await page.locator(".ca-gen__send").click()
    await _until(lambda: _async(len(mock_ws["submits"]) == before + 1))
    model, payload = mock_ws["submits"][-1]
    assert model == QWEN, skill
    assert payload.get("size") == f"{width}*{height}", (skill, payload)
    assert "size_lock" not in payload

    if match:
        await _until(lambda: _images(page), 25)
        await page.wait_for_timeout(600)
        natural = await page.evaluate(
            """async () => {
              const img = document.querySelector('.tl-image img, img.tl-image')
              if (!img) return null
              await img.decode()
              return [img.naturalWidth, img.naturalHeight]
            }"""
        )
        asset = await page.evaluate(
            """() => {
              const ed = window.__caEditor
              const shapes = ed.getCurrentPageShapes().filter((s) => s.type === 'image')
              const shape = shapes.at(-1)
              const bound = shape && ed.getAsset(shape.props.assetId)
              const all = ed.store.allRecords().filter((r) => r.typeName === 'asset' && r.type === 'image').map((r) => [r.props.w, r.props.h, r.props.src])
              return { bound: bound ? [bound.props.w, bound.props.h] : null, all, n: shapes.length }
            }"""
        )
        assert natural == [width, height], (skill, natural)
        assert asset["bound"] == [width, height], (skill, asset)
        await _close_toasts(page)
        await page.screenshot(path=str(SHOTS / f"{skill}-placed.png"))
    else:
        await _until(lambda: _error(page), 25)
        text = await page.locator(".ca-gen-card__error").inner_text()
        assert "没有通过" in text, (skill, text)
        assert f"{wrong[0]}×{wrong[1]}" in text and f"{width}×{height}" in text
        assert await page.locator(".tl-image").count() == 0
        await _close_toasts(page)
        await page.screenshot(path=str(SHOTS / f"{skill}-refused.png"))


async def _close_toasts(page):
    for _ in range(8):
        button = page.get_by_role("button", name="关闭")
        if await button.count() == 0:
            return
        await button.first.click()


async def _async(value):
    return value


async def _images(page):
    return await page.locator(".tl-image").count() >= 1


async def _error(page):
    return await page.locator(".ca-gen-card__error").count() >= 1
