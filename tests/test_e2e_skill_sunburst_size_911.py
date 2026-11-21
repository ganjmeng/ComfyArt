"""P1 hotfix (#911) e2e: clothing-swap and studio-model results actually land on the canvas.

The real built app runs in headless Chromium against the real ComfyArt routes, which talk only
to a local mock WaveSpeed (nothing paid). The generate_image args come from the real backend
pin pipeline (apply_generate -> _auto_choice -> _pin_args), then go through the same page
command handler the agent uses. The mock returns Sunburst's native 2k 3:4 file (1664×2224,
the size of pred a266bb741a514ee8b664402a4a825854 on main 88cbd358) or a 1k file (768×1024).

Both must be placed on the canvas as returned (natural pixels checked in the browser). The
1k file fails the ratio-mode check, so a light info toast is shown in the UI language only,
but it is still placed. The native 2k file shows no toast. What goes back to the agent
(wait_generation) is a success with the image placed: no 「0 张成功」, no rerun hint.

This e2e never skips silently. dist/ must be a local build of this tree (gate: `npx vite build`,
not committed); a missing or stale dist/ or a missing Chromium is a hard failure.
Set CA_911_SHOTS=<dir> to save the review screenshots.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from PIL import Image

from ComfyArt.api import wavespeed
from test_e2e_skill_canvas_707 import _close_toasts, _png, _until, app_url  # noqa: F401 - app_url fixture
from test_wavespeed import MODELS

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
SB_EDIT = "openai/gpt-image-2.6-sunburst/edit"
SB_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
COPY = {
    "zh": "出图尺寸低于预期（实际 {w}×{h}），已按原图交付。",
    "en": "Output is smaller than expected ({w}×{h}). Delivered as generated.",
}
# Must never reach the agent or the page for a delivered image.
BANNED = ("0 张成功", "0 succeeded", "重跑", "再发起", "重新生成", "rerun", "re-run", "run it again", "try again",
          "没有通过", "Not accepted", "失败", "failed")


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    """Fail loudly (never skip) when dist/ is missing or was not built from this tree's sources."""
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing: run `npx vite build` (local build, not committed) before this e2e")
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "dist").rglob("*.js"))
    for marker in ("已按原图交付", "Delivered as generated", "size_lock_mode"):
        if marker not in bundle:
            pytest.fail(f"dist/ is stale (no {marker!r}): run `npx vite build` (local, not committed) before this e2e")


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


async def _boot(page, app_url: str, lang: str):
    await page.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}'); localStorage.setItem('comfyart.e2e','1')")
    await page.goto(app_url)
    await page.wait_for_timeout(1500)
    await page.mouse.click(28, 83)
    await page.locator(".tl-canvas").wait_for()
    await page.wait_for_timeout(800)
    if await page.locator(".ca-modal").count():
        await page.locator(".ca-modal button").nth(-2).click()
    await page.wait_for_function("() => window.__comfyartE2E && window.__comfyartE2E.listed().length > 0")


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_skill_clothing_swap_and_studio_model_results_land_on_canvas(app_url, mock_ws, lang):
    refs = _write_inputs()
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"chromium not available, this e2e must not skip: {e}")
        page = await browser.new_page(viewport={"width": 1280, "height": 800}, locale="zh-CN" if lang == "zh" else "en-US")
        await _boot(page, app_url, lang)
        await page.evaluate("() => window.__comfyartE2E.setPrefs({ auto: true, enabled: [] })")
        for skill, with_refs, size in CASES:
            for (fw, fh), passes in (((1664, 2224), True), ((768, 1024), False)):
                await _case(page, mock_ws, lang, skill, refs if with_refs else None, size, fw, fh, passes)
        await browser.close()


async def _case(page, mock_ws, lang, skill, refs, size, fw, fh, passes):
    label = f"{lang}-{skill}-{'edit' if refs else 't2i'}-{fw}x{fh}"
    mock_ws["png"] = _png(fw, fh, (36, 96, 168), label)
    await page.evaluate("() => { const ed = window.__caEditor; ed.selectAll(); ed.deleteShapes(ed.getSelectedShapeIds()) }")
    await _close_toasts(page)
    await _dismiss_all(page)
    before = len(mock_ws["submits"])
    args = _page_args(skill, refs, size)
    started = await page.evaluate("async (args) => window.__comfyartE2E.command('generate_image', args)", args)
    assert started["ok"] is True, (label, started)
    ids = started["result"]["ids"]
    waited = await page.evaluate("async (ids) => window.__comfyartE2E.command('wait_generation', { ids, timeout_s: 25 })", ids)
    assert waited["ok"] is True, (label, waited)

    # Agent-facing result: a success with the image placed, size note as info only.
    agent = waited["result"]
    assert agent["status"] == "done", (label, agent)
    res = agent["results"][0]
    assert res["status"] == "done" and res["placed"] is True and res["generation_succeeded"] is True, (label, res)
    assert res["delivered"] == 1 and res["urls"], (label, res)
    assert "error" not in res, (label, res)
    agent_text = json.dumps(agent, ensure_ascii=False)
    for bad in BANNED:
        assert bad.lower() not in agent_text.lower(), (label, bad, agent_text)

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

    other = "en" if lang == "zh" else "zh"
    if passes:
        assert "size_info" not in res, (label, res)
        await page.wait_for_timeout(1200)  # give a (wrong) toast time to appear
        assert await page.locator(".tlui-toast__container").count() == 0, (label, await _toast_texts(page))
    else:
        want = COPY[lang].format(w=fw, h=fh)
        assert res["size_info"] == want, (label, res)
        await _until(lambda: _toast(page, want), 10)
        toast = page.locator(".tlui-toast__container").filter(has_text=want)
        assert await toast.count() == 1
        # light info toast: not the error style, and no action (retry) button
        assert (await toast.first.get_attribute("data-severity")) == "info", label
        assert await toast.locator(".tlui-toast__actions").count() == 0, label
        texts = " ".join(await _toast_texts(page))
        assert COPY[other].format(w=fw, h=fh) not in texts, (label, texts)  # UI language only
    body = await page.evaluate("() => document.body.innerText")
    for bad in BANNED:
        assert bad.lower() not in body.lower(), (label, bad)
    shots = os.environ.get("CA_911_SHOTS")
    if shots and skill == "clothing-swap":
        Path(shots).mkdir(parents=True, exist_ok=True)
        await page.evaluate("() => { window.__caEditor.zoomToFit({ animation: { duration: 0 } }) }")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(Path(shots) / f"{lang}-clothing-swap-{fw}x{fh}-{'no-toast' if passes else 'toast'}.png"))


async def _dismiss_all(page):
    for _ in range(30):
        if await page.locator(".tlui-toast__container").count() == 0:
            return
        close = page.locator(".tlui-toast__close")
        if await close.count():
            await close.first.click()
        await page.wait_for_timeout(100)
    raise AssertionError(f"toasts did not close: {await _toast_texts(page)}")


async def _toast_texts(page):
    return await page.locator(".tlui-toast__container").all_inner_texts()


async def _image_count(page):
    return await page.evaluate("() => window.__caEditor.getCurrentPageShapes().filter((s) => s.type === 'image').length") >= 1


async def _toast(page, text):
    return any(text in t for t in await page.locator(".tlui-toast__title").all_inner_texts())
