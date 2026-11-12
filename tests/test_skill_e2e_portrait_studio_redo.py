"""portrait-studio e2e: the replies around the set and redoing ONE image (Lovart 7fc60c86 reply).

The real built app in headless Chromium, real ComfyArt routes, real MCP tool dispatch, real chat panel,
real page command handlers (generate_image / wait_generation place real images on the canvas). The agent
is a scripted in-process provider (no LLM). WaveSpeed is a local mock (GPT Image 2.6 Sunburst edit in its
catalog) that returns local PNG fixtures, so nothing is paid.

Turn 1: portrait_studio_plan -> its reply (locked / changed, lighting, optics, pose, 「现在开始生成」) ->
one generate_image per slot (3) -> wait_generation -> portrait_studio_done -> table + parameters + closing.
Each of the three reply parts shows exactly once in the chat; the en UI shows English only.
Turn 2: the user names one image (「半身那张脸不像」 / "The half-body one doesn't look like me") ->
portrait_studio_redo -> exactly ONE more model submit (Sunburst edit, the half-body shot), the new image
is placed next to the original half-body image; the original and the other two are untouched.

dist/ must be a local build of this tree (`npx vite build`, not committed); a missing or stale dist/ or a
missing Chromium is a hard failure, never a skip. PORTRAIT_E2E_SHOTS=/dir keeps the screenshots.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from PIL import Image, ImageDraw

from ComfyArt.api import wavespeed
from test_e2e_comment_edit import app_url  # noqa: F401  (real routes; uses this module's mock_ws)
from test_skill_e2e_portrait_studio import LOC, ScriptedAgent, _call, _send, agent, ws_forward  # noqa: F401
from test_wavespeed import MODELS

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("PORTRAIT_E2E_SHOTS")
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
SB_EDIT = "openai/gpt-image-2.6-sunburst/edit"
GAP = 40  # src/botCommands.ts place(): near -> right of the original, GAP apart
CJK = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")
USER_TEXT = {"zh": "帮我用这张照片做一组专业形象照。", "en": "Make a professional portrait set from my photo."}
REDO_TEXT = {"zh": "半身那张脸不像，重做一下", "en": "The half-body one doesn't look like me, redo it"}
REDO_SHOT = {"zh": "半身", "en": "half body"}
PLAN_ARGS = {
    "zh": {"shots": "A", "outfit": "A", "scene": "A",
           "locked": ["五官轮廓", "黑色中长微卷发", "暖调自然肤色", "纤细身材比例"],
           "outfit_desc": "白长袖打底 + 黑 V 领针织背心", "reference_background": "罗马柱建筑空间"},
    "en": {"shots": "A", "outfit": "A", "scene": "A",
           "locked": ["facial features", "black shoulder-length wavy hair", "warm natural skin tone", "slim build"],
           "outfit_desc": "white long-sleeve top, black V-neck knit vest", "reference_background": "a columned hall"},
}
MARKERS = {"zh": ("现在开始生成", "已完成：", "验收提示："), "en": ("Starting the", "are done:", "Check: ")}
SHOT_PROMPTS = ("tight face close-up", "half-body portrait", "three-quarter-body portrait")


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing: run `npx vite build` (local build, not committed) before this e2e")
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "dist").rglob("*.js"))
    if "portrait_studio_redo" not in bundle:
        pytest.fail("dist/ is stale (no portrait_studio_redo label): run `npx vite build` (local, not committed)")


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def _png(w, h, rgb, label):
    img = Image.new("RGB", (w, h), rgb)
    d = ImageDraw.Draw(img)
    d.rectangle([w // 2 - 120, h // 4, w // 2 + 120, h // 4 + 300], fill=(240, 220, 200))
    d.text((24, 24), f"LOCAL FIXTURE {label}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


COLORS = [(60, 90, 140), (90, 130, 90), (140, 90, 70), (120, 70, 140), (70, 120, 130)]


@pytest.fixture
async def mock_ws(monkeypatch, fresh_user_dir):
    """Local WaveSpeed: Sunburst edit in the catalog; each submit returns its own labeled PNG."""
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    state = {"submits": [], "quotes": [], "uploads": 0}
    for bucket in (wavespeed._quotes, wavespeed._map_cache, wavespeed._jobs, wavespeed._submits, wavespeed._uploaded):
        bucket.clear()
    have = {m.get("model_id") for m in MODELS}
    models = list(MODELS) + [FIXTURE[m] for m in (SB_EDIT,) if m not in have]
    app = web.Application(client_max_size=80 * 2**20)

    async def models_route(_r):
        return web.json_response({"code": 200, "data": models})

    async def price(r):
        body = await r.json()
        state["quotes"].append(body)
        return web.json_response({"code": 200, "data": {"model_id": body.get("model_id"), "price": 0.02, "unit_price": 0.02, "currency": "USD"}})

    async def upload(r):
        state["uploads"] += 1
        async for part in await r.multipart():
            await part.read()
        return web.json_response({"code": 200, "data": {"download_url": str(r.url.with_path(f"/cdn/up{state['uploads']}.png").with_query(None))}})

    async def submit(r):
        state["submits"].append((r.match_info["model"], await r.json()))
        return web.json_response({"code": 200, "data": {"id": f"task{len(state['submits'])}", "status": "created"}})

    async def result(r):
        n = int(r.match_info["id"][4:])
        data = {"id": r.match_info["id"], "status": "completed", "error": "",
                "outputs": [str(r.url.with_path(f"/cdn/out{n}.png").with_query(None))]}
        return web.json_response({"code": 200, "data": data})

    async def cdn(r):
        n = int(r.match_info["n"])
        return web.Response(body=_png(768, 1024, COLORS[(n - 1) % len(COLORS)], f"result #{n}"), content_type="image/png")

    async def balance(_r):
        return web.json_response({"code": 200, "data": {"balance": 10}})

    app.router.add_get("/api/v3/models", models_route)
    app.router.add_get("/api/v3/balance", balance)
    app.router.add_post("/api/v3/model/price", price)
    app.router.add_post("/api/v3/media/upload/binary", upload)
    app.router.add_get("/api/v3/predictions/{id}/result", result)
    app.router.add_post("/api/v3/{model:.+}", submit)
    app.router.add_get(r"/cdn/out{n:\d+}.png", cdn)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-not-a-real-key")
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    yield state
    await server.close()


def _reference() -> str:
    import folder_paths
    base = folder_paths.STATE["base"] / "input"
    base.mkdir(parents=True, exist_ok=True)
    (base / "ps-ref.png").write_bytes(_png(768, 1024, (200, 180, 160), "reference person"))
    return "/api/view?filename=ps-ref.png&type=input"


async def _page(p, app_url, lang):  # noqa: F811
    try:
        browser = await p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"chromium not available, this e2e must not skip: {e}")
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN" if lang == "zh" else "en-US")
    return browser, ctx


async def _images(pg):
    return await pg.evaluate(
        """() => {
          const ed = window.__caEditor
          return ed.getCurrentPageShapes().filter((s) => s.type === 'image').map((s) => {
            const b = ed.getShapePageBounds(s.id)
            return { id: s.id, src: ed.getAsset(s.props.assetId)?.props.src, x: b.x, y: b.y, w: b.w, h: b.h, maxX: b.maxX, maxY: b.maxY }
          })
        }""")


def _overlap(a, b):
    return a["x"] < b["maxX"] and b["x"] < a["maxX"] and a["y"] < b["maxY"] and b["y"] < a["maxY"]


async def _bot_text(pg):
    return "\n".join(await pg.locator(".ca-chat__bot").all_inner_texts())


async def _until(fn, secs=30):
    for _ in range(int(secs * 10)):
        if await fn():
            return
        await asyncio.sleep(0.1)
    raise AssertionError("timed out")


async def _shot(pg, name, fit=True):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        if fit:
            await pg.evaluate("() => window.__caEditor.zoomToFit({ animation: { duration: 0 } })")
        await pg.wait_for_timeout(700)
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_skill_e2e_portrait_studio_note_then_redo_one(app_url, mock_ws, agent, ws_forward, monkeypatch, lang):  # noqa: F811
    ref = _reference()
    placed: list[str] = []

    async def set_steps(a, turn, emit):
        from ComfyArt.bot.providers import BotEvent
        plan = await _call(a, emit, "portrait_studio_plan", {**PLAN_ARGS[lang], "refs": [ref],
                                                             "prompt": "young woman with black shoulder-length wavy hair"}, 1)
        await emit(BotEvent(t="delta", text=plan.get("user_message") or f"NO PLAN {plan}"))
        ids = []
        for s in plan.get("slots") or []:
            g = await _call(a, emit, "generate_image", {"prompt": "young woman with black shoulder-length wavy hair",
                                                        "skill": "portrait-studio", "refs": [ref], "count": 1,
                                                        "portrait_slot": s["slot"]}, 10 + s["slot"])
            ids += g.get("ids") or []
        w = await _call(a, emit, "wait_generation", {"ids": ids, "timeout_s": 60}, 20)
        for r in w.get("results") or []:
            placed.extend(r.get("shapes") or [])
        done = await _call(a, emit, "portrait_studio_done", {"images": list(placed)}, 21)
        await emit(BotEvent(t="delta", text=done.get("user_message") or f"NO DONE {done}"))

    async def redo_steps(a, turn, emit):
        from ComfyArt.bot.providers import BotEvent
        r = await _call(a, emit, "portrait_studio_redo", {"shot": REDO_SHOT[lang], "fix": "match the reference face shape"}, 30)
        await emit(BotEvent(t="delta", text=r.get("user_message") or f"NO REDO {r}"))
        await _call(a, emit, "wait_generation", {"ids": r.get("ids") or [], "timeout_s": 60}, 31)

    async with pw.async_playwright() as p:
        browser, ctx = await _page(p, app_url, lang)
        await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: ws_forward.append(ws))
        pg = await ctx.new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light');localStorage.setItem('comfyart.e2e','1')")
        await pg.goto(app_url + f"?project=ppr{lang}&new=1&skill=portrait-studio&mode=agent")
        await pg.locator(".ca-composer__input").wait_for(timeout=20000)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        await pg.locator(".ca-composer").get_by_text(ScriptedAgent.label, exact=True).wait_for(timeout=15000)
        await pg.evaluate(
            """(src) => {
              const ed = window.__caEditor
              ed.createAssets([{ id: 'asset:psref', typeName: 'asset', type: 'image', meta: {},
                props: { name: 'reference.png', src, w: 768, h: 1024, mimeType: 'image/png', isAnimated: false } }])
              ed.createShape({ id: 'shape:psref', type: 'image', x: -900, y: 0, props: { assetId: 'asset:psref', w: 384, h: 512 } })
              ed.selectNone()
            }""", ref)

        await pg.wait_for_function("() => window.__comfyartE2E && window.__comfyartE2E.listed().length > 0")
        await pg.evaluate("() => window.__comfyartE2E.setPrefs({ auto: true, enabled: [] })")
        from ComfyArt.api.mcp_tools import canvas
        page_calls: list[str] = []

        async def to_page(action, args, project, timeout, chat=""):
            """The command bus hop: the server's command runs in this page's real handler (HANDLERS)."""
            page_calls.append(action)
            out = await pg.evaluate("async ([a, args]) => window.__comfyartE2E.command(a, args)", [action, args])
            if not out["ok"]:
                raise RuntimeError(out["error"])
            return out["result"]
        monkeypatch.setattr(canvas, "submit_command", to_page)

        # --- turn 1: the set ------------------------------------------------------------------------
        agent.steps = set_steps
        await _send(pg, USER_TEXT[lang])
        try:
            await _until(lambda: _has(pg, MARKERS[lang][2]), 90)
        except AssertionError:
            raise AssertionError(json.dumps({"results": agent.results, "chat": await _bot_text(pg),
                                             "submits": len(mock_ws["submits"])}, ensure_ascii=False, default=str)[:6000]) from None
        await pg.wait_for_timeout(1500)  # turn end: self-check runs, nothing else may be appended
        text = await _bot_text(pg)
        if os.environ.get("PS_DEBUG"):
            from ComfyArt.api import chat_store
            for msg in chat_store.list_messages(agent.last_turn.chat_id):
                for blk in msg.get("blocks") or []:
                    print("BLOCK", json.dumps(blk, ensure_ascii=False, default=str)[:600])
        for m in MARKERS[lang]:
            assert text.count(m) == 1, (m, text)
        assert text.index(MARKERS[lang][0]) < text.index(MARKERS[lang][1]) < text.index(MARKERS[lang][2])
        if lang == "en":
            assert not CJK.search(text), text
        for bad in ("ISO", "1/250", "Portra", "Negative", "$"):
            assert bad not in text, bad
        assert "85mm" in text and "f/2.8" in text and "3:4" in text
        submits = list(mock_ws["submits"])
        assert len(submits) == 3, submits
        for (model, body), shot in zip(submits, SHOT_PROMPTS):
            assert model == SB_EDIT and shot in body["prompt"], (model, body.get("prompt"))
        assert len(placed) == 3, placed
        before = {i["id"]: i for i in await _images(pg)}
        assert set(placed) <= set(before) and "shape:psref" in before and len(before) == 4, before
        quotes_before = len(mock_ws["quotes"])
        tables = pg.locator(".ca-chat__bot table")
        assert await tables.count() == 1
        await tables.first.scroll_into_view_if_needed()
        await _shot(pg, f"note-{lang}")

        # --- turn 2: redo exactly the half-body image ------------------------------------------------
        agent.steps = redo_steps
        n_results = len(agent.results)
        await _send(pg, REDO_TEXT[lang])
        await _until(lambda: _count_images(pg, 5), 60)
        await pg.wait_for_timeout(1500)
        assert len(mock_ws["submits"]) == 4, mock_ws["submits"]  # exactly one more paid call
        model, body = mock_ws["submits"][-1]
        assert model == SB_EDIT and "half-body portrait" in body["prompt"]
        assert "tight face close-up" not in body["prompt"] and "three-quarter-body" not in body["prompt"]
        assert len(mock_ws["quotes"]) - quotes_before <= 1  # any price quote is for that one image only
        redo = next(payload for name, payload in agent.results[n_results:] if name == "portrait_studio_redo")
        assert redo["portrait_slot"] == 2 and redo["near"] == placed[1], redo
        after = {i["id"]: i for i in await _images(pg)}
        for sid, img in before.items():  # originals untouched: same ids, same files, same place
            assert sid in after and after[sid]["src"] == img["src"], sid
            assert (after[sid]["x"], after[sid]["y"]) == (img["x"], img["y"]), sid
        new = [after[s] for s in after if s not in before]
        assert len(new) == 1, new
        orig = before[placed[1]]
        assert new[0]["x"] == pytest.approx(orig["maxX"] + GAP) and new[0]["y"] == pytest.approx(orig["y"])
        for sid, img in before.items():
            assert not _overlap(new[0], img), (sid, new[0], img)
        text = await _bot_text(pg)
        msg = redo["user_message"]
        assert msg in text and "2" in msg
        assert bool(CJK.search(msg)) is (lang == "zh")
        if lang == "en":
            assert not CJK.search(text), text
        for m in MARKERS[lang]:  # the set's replies are not repeated by the redo
            assert text.count(m) == 1, (m, text)
        await _shot(pg, f"redo-{lang}")
        await browser.close()


async def _has(pg, needle):
    return needle in await _bot_text(pg)


async def _count_images(pg, n):
    return len(await _images(pg)) >= n
