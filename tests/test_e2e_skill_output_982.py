"""#982 mock e2e: the size that is ACTUALLY submitted for logo-material-explorer and
character-sheet-design default paths (not what the UI shows).

The real backend relay (api/mcp_tools/canvas._relay_run: apply_generate -> select_model ->
page command) drives the real built page in headless Chromium; the page posts the job to the
real ComfyArt routes, which submit to a local mock WaveSpeed whose model schemas are the
recorded catalog fixture (tier-only: aspect_ratio + 1k/2k/4k). Asserted per call: the page
args (width/height/count/size_lock), the WaveSpeed payload (model, aspect_ratio, resolution),
and the server size audit (expect_pixels, ratio mode). $0: nothing leaves localhost.
Set CA_982_REPORT=<file> to dump the size table.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from PIL import Image

from ComfyArt.api import wavespeed
from test_e2e_skill_canvas_707 import _png, app_url  # noqa: F401 - app_url fixture
from test_e2e_skill_sunburst_size_911 import _boot
from test_wavespeed import MODELS

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
FLARE_EDIT = "openai/gpt-image-2.6-flare/edit"
FLARE_T2I = "openai/gpt-image-2.6-flare/text-to-image"
RECRAFT = "recraft-ai/recraft-v3"
REAL = (FLARE_EDIT, FLARE_T2I, RECRAFT)
LOGO = "logo-material-explorer"
CHAR = "character-sheet-design"
MATERIALS = ("brushed metal", "clear glass", "woven fabric", "glazed ceramic")


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing: run `npx vite build` before this e2e")


@pytest.fixture
async def mock_ws(monkeypatch, fresh_user_dir):
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    state = {"submits": [], "uploads": 0, "png": _png(8, 8, (0, 0, 0), "unset")}
    for bucket in (wavespeed._quotes, wavespeed._map_cache, wavespeed._jobs, wavespeed._submits, wavespeed._uploaded):
        bucket.clear()
    models = [m for m in MODELS if m.get("model_id") not in REAL] + [FIXTURE[m] for m in REAL]
    app = web.Application(client_max_size=80 * 2**20)

    async def models_route(_r):
        return web.json_response({"code": 200, "data": models})

    async def price(request):
        body = await request.json()
        return web.json_response({"code": 200, "data": {"model_id": body.get("model_id"), "price": 0.02, "unit_price": 0.02, "currency": "USD"}})

    async def upload(request):
        state["uploads"] += 1
        async for part in await request.multipart():
            await part.read()
        return web.json_response({"code": 200, "data": {"download_url": str(request.url.with_path(f"/cdn/up{state['uploads']}.png").with_query(None))}})

    async def submit(request):
        state["submits"].append((request.match_info["model"], await request.json()))
        return web.json_response({"code": 200, "data": {"id": f"task{len(state['submits'])}", "status": "created"}})

    async def result(request):
        data = {"id": request.match_info["id"], "status": "completed", "outputs": [str(request.url.with_path("/cdn/out.png").with_query(None))], "error": ""}
        return web.json_response({"code": 200, "data": data})

    async def balance(_r):
        return web.json_response({"code": 200, "data": {"balance": 10}})

    async def cdn(_r):
        return web.Response(body=state["png"], content_type="image/png")

    for method, path, fn in (("GET", "/api/v3/models", models_route), ("GET", "/api/v3/balance", balance),
                             ("POST", "/api/v3/model/price", price), ("POST", "/api/v3/media/upload/binary", upload),
                             ("GET", "/api/v3/predictions/{id}/result", result), ("POST", "/api/v3/{model:.+}", submit),
                             ("GET", "/cdn/out.png", cdn)):
        app.router.add_route(method, path, fn)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    yield state
    await server.close()


def _logo_ref() -> str:
    import folder_paths
    base = folder_paths.STATE["base"] / "input"
    base.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 800), (20, 20, 20)).save(base / "logo-982.png", format="PNG")
    return "/api/view?filename=logo-982.png&type=input"


async def _run(page, mock_ws, monkeypatch, args: dict, provider_png: tuple[int, int]) -> dict:
    """One generate_image through the real backend relay, then wait_generation on the page."""
    from ComfyArt.api.mcp_tools import canvas

    async def to_page(action, a, _project, _timeout, chat=None):
        got = await page.evaluate("async ([act, a]) => window.__comfyartE2E.command(act, a)", [action, a])
        assert got["ok"] is True, got
        return got["result"]

    monkeypatch.setattr(canvas, "submit_command", to_page)
    mock_ws["png"] = _png(*provider_png, (36, 96, 168), "982")
    before = len(mock_ws["submits"])
    started = await canvas._relay_run("generate_image", dict(args), "", 60)
    assert started.get("ids"), started
    waited = await page.evaluate("async (ids) => window.__comfyartE2E.command('wait_generation', { ids, timeout_s: 25 })", started["ids"])
    assert waited["ok"] is True, waited
    assert len(mock_ws["submits"]) == before + 1
    model, payload = mock_ws["submits"][-1]
    task = f"task{len(mock_ws['submits'])}"
    job = wavespeed._jobs.get(task, {})
    res = waited["result"]["results"][0]
    return {"page_width": started.get("width"), "page_height": started.get("height"), "model": model,
            "aspect_ratio": payload.get("aspect_ratio"), "resolution": payload.get("resolution"),
            "size_field": payload.get("size"), "expect_pixels": list(job.get("expect_pixels") or []),
            "size_mode": job.get("size_mode", "exact"), "delivered": list(provider_png),
            "size_info": res.get("size_info"), "placed": res.get("placed")}


async def test_default_paths_submit_declared_size(app_url, mock_ws, monkeypatch):
    ref = _logo_ref()
    rows = []
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"chromium not available, this e2e must not skip: {e}")
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await _boot(page, app_url, "zh")
        await page.evaluate("() => window.__comfyartE2E.setPrefs({ auto: true, enabled: [] })")

        # logo-material-explorer default path: upload is required -> refs on every call; 4 materials.
        # The edit model is tier-only: 1254 long side -> the lowest tier >= 1254 = 2k. A 2k 1:1 file
        # (2048²) passes the ratio-mode audit with no size notice.
        for mat in MATERIALS:
            r = await _run(page, mock_ws, monkeypatch,
                           {"prompt": f"{mat} material study of the uploaded mark", "skill": LOGO, "refs": [ref]}, (2048, 2048))
            assert (r["page_width"], r["page_height"]) == (1254, 1254), r
            assert r["model"] == FLARE_EDIT and r["aspect_ratio"] == "1:1" and r["resolution"] == "2k", r
            assert r["size_field"] is None and r["expect_pixels"] == [1254, 1254] and r["size_mode"] == "ratio", r
            assert r["placed"] is True and not r["size_info"], r
            rows.append({"skill": LOGO, "case": f"refs/{mat}", **r})
        # Hypothetical no-ref call (UI requires the upload): Auto picks Recraft for a logo prompt; Recraft has
        # only aspect_ratio (native 1024²), so 1254 is NOT reachable — delivered with an honest size notice.
        r = await _run(page, mock_ws, monkeypatch, {"prompt": "brushed metal logo material study", "skill": LOGO}, (1024, 1024))
        assert r["model"] == RECRAFT and r["aspect_ratio"] == "1:1" and r["resolution"] is None, r
        assert r["expect_pixels"] == [1254, 1254] and r["size_mode"] == "ratio", r
        assert r["placed"] is True and "1024×1024" in (r["size_info"] or ""), r
        rows.append({"skill": LOGO, "case": "no-ref (auto)", **r})

        # character-sheet-design: default template + every template, text-only default path.
        cases = [("", (1024, 1024), "1:1", "1k"), ("turnaround", (1024, 1024), "1:1", "1k"),
                 ("expression", (2048, 1152), "16:9", "2k"), ("modeling", (2048, 1152), "16:9", "2k"),
                 ("outfit", (1024, 1024), "1:1", "1k"), ("prop", (1024, 1024), "1:1", "1k"),
                 ("basic", (2048, 1152), "16:9", "2k"), ("technical", (2048, 1152), "16:9", "2k"),
                 ("editorial", (1024, 1024), "1:1", "1k")]
        for pid, (w, h), ratio, tier in cases:
            args = {"prompt": "adult character reference board, consistent costume", "skill": CHAR}
            if pid:
                args["preset"] = pid
            r = await _run(page, mock_ws, monkeypatch, args, (w, h))
            assert (r["page_width"], r["page_height"]) == (w, h), (pid, r)
            assert r["model"] == FLARE_T2I and r["aspect_ratio"] == ratio and r["resolution"] == tier, (pid, r)
            assert r["expect_pixels"] == [w, h] and r["size_mode"] == "ratio", (pid, r)
            assert r["placed"] is True and not r["size_info"], (pid, r)
            rows.append({"skill": CHAR, "case": pid or "(default template)", **r})
        # with the uploaded reference the same template goes to the edit model at the same size
        r = await _run(page, mock_ws, monkeypatch, {"prompt": "turnaround of this person", "skill": CHAR, "preset": "basic", "refs": [ref]}, (2048, 1152))
        assert r["model"] == FLARE_EDIT and r["aspect_ratio"] == "16:9" and r["resolution"] == "2k", r
        rows.append({"skill": CHAR, "case": "basic + refs", **r})
        await browser.close()
    out = os.environ.get("CA_982_REPORT")
    if out:
        Path(out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
