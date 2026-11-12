"""P1 hotfix (#911) e2e: clothing-swap and studio-model results actually land on the canvas.

The real built app runs in headless Chromium against the real ComfyArt routes, which talk only
to a local mock WaveSpeed (nothing paid). The generate_image args come from the real backend
pin pipeline (apply_generate -> _auto_choice -> _pin_args), then go through the same page
command handler the agent uses. The mock returns Sunburst's native 2k 3:4 file (1664×2224,
the size of pred a266bb741a514ee8b664402a4a825854 on main 88cbd358) or a 1k file (768×1024).

Both must be placed on the canvas as returned (natural pixels checked in the browser). The
1k file fails the ratio-mode check, so a size notice toast is shown, but it is still placed.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from PIL import Image

from ComfyArt.api import wavespeed
from test_e2e_skill_canvas_707 import _boot, _close_toasts, _png, _until, app_url  # noqa: F401 - app_url fixture
from test_wavespeed import MODELS

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
SB_EDIT = "openai/gpt-image-2.6-sunburst/edit"
SB_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("index.html")), reason="needs built dist/")


@pytest.fixture
async def mock_ws(monkeypatch, fresh_user_dir):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    state = {"submits": [], "uploads": 0, "png": _png(8, 8, (0, 0, 0), "unset")}
    for bucket in (wavespeed._quotes, wavespeed._map_cache, wavespeed._jobs, wavespeed._submits, wavespeed._uploaded):
        bucket.clear()
    have = {m.get("model_id") for m in MODELS}
    models = list(MODELS) + [FIXTURE[m] for m in (SB_EDIT, SB_T2I) if m not in have]
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
        data = {"id": request.match_info["id"], "status": "completed", "outputs": [str(request.url.with_path("/cdn/out.png").with_query(None))], "error": ""}
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
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    yield state
    await server.close()


def _write_inputs() -> list[str]:
    import folder_paths
    base = folder_paths.STATE["base"] / "input"
    base.mkdir(parents=True, exist_ok=True)
    urls = []
    for name, wh, rgb in (("person-911.png", (768, 1024), (200, 180, 160)), ("garment-911.png", (512, 512), (30, 60, 200))):
        Image.new("RGB", wh, rgb).save(base / name, format="PNG")
        urls.append(f"/api/view?filename={name}&type=input")
    return urls


def _page_args(skill: str, refs: list[str] | None, size: dict) -> dict:
    """Backend pin pipeline -> the args canvas.py hands the page (skill popped, as in _generate)."""
    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.bot.skill_output import apply_generate

    args = {"prompt": f"local fixture {skill}", "skill": skill, **size}
    if refs:
        args["refs"] = ["shape:person", "shape:garment"]
    args = apply_generate(args)
    choice = canvas._auto_choice("generate_image", dict(args))
    assert choice and choice["category"] == "skill"
    out = canvas._pin_args(dict(args), choice)
    out.pop("skill", None)
    if refs:
        out["refs"] = refs  # the page resolves shape ids to these view URLs; pass them directly
    assert out["size_lock"] is True and out["size_lock_mode"] == "ratio"
    return out


CASES = [
    ("clothing-swap", True, {}),
    ("studio-model", True, {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True}),
    ("studio-model", False, {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True}),
]


async def test_clothing_swap_and_studio_model_results_land_on_canvas(app_url, mock_ws):
    refs = _write_inputs()
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        page = await browser.new_page(viewport={"width": 1280, "height": 800}, locale="zh-CN")
        await _boot(page, app_url)
        await page.evaluate("() => window.__comfyartE2E.setPrefs({ auto: true, enabled: [] })")
        for skill, with_refs, size in CASES:
            for (fw, fh), passes in (((1664, 2224), True), ((768, 1024), False)):
                await _case(page, mock_ws, skill, refs if with_refs else None, size, fw, fh, passes)
        await browser.close()


async def _case(page, mock_ws, skill, refs, size, fw, fh, passes):
    label = f"{skill}-{'edit' if refs else 't2i'}-{fw}x{fh}"
    mock_ws["png"] = _png(fw, fh, (36, 96, 168), label)
    await page.evaluate("() => { const ed = window.__caEditor; ed.selectAll(); ed.deleteShapes(ed.getSelectedShapeIds()) }")
    await _close_toasts(page)
    before = len(mock_ws["submits"])
    args = _page_args(skill, refs, size)
    started = await page.evaluate("async (args) => window.__comfyartE2E.command('generate_image', args)", args)
    assert started["ok"] is True, (label, started)
    ids = started["result"]["ids"]
    waited = await page.evaluate("async (ids) => window.__comfyartE2E.command('wait_generation', { ids, timeout_s: 25 })", ids)
    assert waited["ok"] is True, (label, waited)
    res = waited["result"]["results"][0]
    assert res["status"] == "done", (label, res)
    assert res["urls"], (label, res)

    assert len(mock_ws["submits"]) == before + 1
    model, payload = mock_ws["submits"][-1]
    assert model == (SB_EDIT if refs else SB_T2I), label
    assert payload.get("aspect_ratio") == "3:4" and payload.get("resolution") == "2k", (label, payload)
    assert "size" not in payload and "size_lock" not in payload and "size_lock_mode" not in payload

    await _until(lambda: _image_count(page), 25)
    placed = await page.evaluate(
        """async () => {
          const ed = window.__caEditor
          const shapes = ed.getCurrentPageShapes().filter((s) => s.type === 'image')
          const shape = shapes.at(-1)
          const asset = shape && ed.getAsset(shape.props.assetId)
          const img = new Image()
          img.src = asset.props.src
          await img.decode()
          return { n: shapes.length, asset: [asset.props.w, asset.props.h], natural: [img.naturalWidth, img.naturalHeight] }
        }"""
    )
    # Native file on the canvas: not scaled or cropped to 1536×2048.
    assert placed["n"] == 1, (label, placed)
    assert placed["natural"] == [fw, fh], (label, placed)
    assert placed["asset"] == [fw, fh], (label, placed)
    assert await page.locator(".ca-gen-card__error").count() == 0, label
    toasts = await page.locator(".tlui-toast__title").all_inner_texts()
    if passes:
        assert "size_notice" not in res, (label, res)
        assert not any("尺寸提示" in t for t in toasts), (label, toasts)
    else:
        assert "768×1024" in res["size_notice"] and "1536×2048" in res["size_notice"], (label, res)
        await _until(lambda: _toast(page, "尺寸提示"), 10)


async def _image_count(page):
    return await page.evaluate("() => window.__caEditor.getCurrentPageShapes().filter((s) => s.type === 'image').length") >= 1


async def _toast(page, text):
    return any(text in t for t in await page.locator(".tlui-toast__title").all_inner_texts())
