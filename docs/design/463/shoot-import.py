"""#463 live shots: Import a Skill menu, drop dialog, same ZIP imported 3x (x, x-2, x-3).

(base: #462: real Edit Skill dialog (Name/Description/Instructions Preview·Code, Edit in Chat) + real Composer chip.

No Agent/发送 invented foot. Process/prefill seed via bot /log + WS bridge so the real ProcessTimeline renders.
$0 — mock WaveSpeed, fake provider probes.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))
os.chdir(ROOT)
os.environ.setdefault("COMFYART_SKIP_KEY_CHECK", "1")

# Install ComfyArt test stubs before importing api
import tests.conftest  # noqa: F401,E402

from aiohttp import web
from aiohttp.test_utils import TestServer
from playwright.async_api import async_playwright

from server import PromptServer
from ComfyArt.api import wavespeed
from ComfyArt.bot import get_provider
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import ProviderStatus
import folder_paths

OUT = Path(os.environ.get("SHOT_OUT", "/tmp/shots463"))

from tests.conftest import FakeProvider, write_settings  # noqa: E402
from ComfyArt.api.settings import SETTINGS_SPEC  # noqa: E402
from ComfyArt.bot import register_provider  # noqa: E402
from ComfyArt.bot.providers import BotEvent  # noqa: E402

PORT_HINT = 0  # TestServer picks


async def _status_ok(*_a, **_k):
    return ProviderStatus(available=True, version="1.0.0", logged_in=True, detail="")


async def _models(self):
    return ["deepseek/deepseek-v4.1-flash-1017"]


def _patch_providers():
    async def ok(*_a, **_k):
        return ProviderStatus(available=True, version="1.0.0", logged_in=True, detail="")
    for pid in ("local-llm", "claude-code", "codex"):
        p = get_provider(pid)
        if p is None:
            continue
        p.probe = ok  # type: ignore[method-assign]
    LocalLlmProvider.list_models = _models  # type: ignore[method-assign]


async def build_app(tmp: Path):
    folder_paths.STATE["base"] = tmp
    for d in ("input", "output", "temp", "user/default"):
        (tmp / d).mkdir(parents=True, exist_ok=True)

    # minimal wavespeed mock
    app = web.Application(client_max_size=200 * 2**20)
    app.router.add_routes(PromptServer.instance.routes)
    for rd in PromptServer.instance.routes:
        if isinstance(rd, web.RouteDef):
            app.router.add_route(rd.method, "/api" + rd.path, rd.handler)

    base = tmp

    def ud(r):
        return base / "user/default" / r.match_info["file"]

    async def ud_get(r):
        return web.FileResponse(ud(r)) if ud(r).is_file() else web.Response(status=404)

    async def ud_post(r):
        ud(r).parent.mkdir(parents=True, exist_ok=True)
        ud(r).write_bytes(await r.read())
        return web.json_response(r.match_info["file"])

    async def view(r):
        q = r.query
        p = base / q.get("type", "output") / q.get("subfolder", "") / q["filename"]
        return web.FileResponse(p) if p.is_file() else web.Response(status=404)

    async def ud_list(r):
        d = base / "user/default" / r.query.get("dir", "")
        if not d.is_dir():
            return web.Response(status=404)
        if r.query.get("recurse"):
            return web.json_response(sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()))
        return web.json_response(sorted(p.name for p in d.iterdir()))

    clients: list[web.WebSocketResponse] = []

    async def wsock(r):
        s = web.WebSocketResponse()
        await s.prepare(r)
        clients.append(s)
        try:
            async for _ in s:
                pass
        finally:
            if s in clients:
                clients.remove(s)
        return s

    def js(v):
        async def h(r):
            return web.json_response(v)
        return h

    for path, h in (
        ("/api/userdata", ud_list),
        ("/api/models/{k}", js([])),
        ("/api/settings/{id}", js(None)),
        ("/api/queue", js({"queue_running": [], "queue_pending": []})),
        ("/api/view", view),
        ("/api/userdata/{file:.+}", ud_get),
        ("/ws", wsock),
    ):
        app.router.add_get(path, h)
    for path, h in (
        ("/api/settings/{id}", js({})),
        ("/api/queue", js({})),
        ("/api/interrupt", js({})),
        ("/api/userdata/{file:.+}", ud_post),
        ("/api/upload/image", js({"name": "x.png", "subfolder": "", "type": "input"})),
    ):
        app.router.add_post(path, h)

    # Bridge PromptServer.send_sync → connected browser sockets (real comfyart-bot events)
    loop = asyncio.get_event_loop()
    orig = PromptServer.instance.send_sync

    def send_sync(event, data, sid=None):
        orig(event, data, sid)
        payload = json.dumps({"type": event, "data": data})

        async def _push(msg: str):
            for s in list(clients):
                if not s.closed:
                    try:
                        await s.send_str(msg)
                    except Exception:
                        pass

        try:
            asyncio.get_running_loop().create_task(_push(payload))
        except RuntimeError:
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_push(payload)))

    PromptServer.instance.send_sync = send_sync
    PromptServer.instance._shot_clients = clients

    server = TestServer(app)
    await server.start_server()
    return server, str(server.make_url("/comfyart/"))



import io, zipfile

def make_zip() -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("coffee-poster/SKILL.md", "---\nname: Coffee Poster\ndescription: \"Warm café morning poster: title on top\"\n---\n\nMake a 3:4 café poster.\n")
        z.writestr("coffee-poster/files/palette.md", "# Palette\n")
    return b.getvalue()


def seed(tmp: Path):
    ca = tmp / "user/default/comfyart"
    ca.mkdir(parents=True, exist_ok=True)
    (ca / "library.json").write_text("[]")
    (ca / "workflow-config.json").write_text("{}")


async def dismiss_modals(page):
    for _ in range(3):
        if await page.locator(".ca-modal").count() == 0:
            break
        for sel in ("button:has-text('稍后再说')", "button:has-text('Later')", "button:has-text('跳过')", "button:has-text('Skip')"):
            b = page.locator(sel).first
            if await b.count():
                await b.click()
                await page.wait_for_timeout(400)
                break
        else:
            break


async def main():
    import tempfile
    OUT.mkdir(parents=True, exist_ok=True)
    _patch_providers()
    zp = Path(tempfile.mkdtemp()) / "coffee-poster.zip"
    zp.write_bytes(make_zip())
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for lang in ("zh", "en"):
            for theme in ("light", "dark"):
                tmp = Path(tempfile.mkdtemp(prefix="ca463-"))
                seed(tmp)
                server, base = await build_app(tmp)
                tag = f"{lang}-{theme}"
                ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
                page = await ctx.new_page()
                await page.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
                await page.add_init_script(f"localStorage.setItem('comfyart.theme','{theme}')")
                await page.goto(f"{base}?view=skills", wait_until="networkidle")
                await page.locator('[data-testid="skills-page"]').wait_for(timeout=30000)
                await page.wait_for_timeout(800)
                await dismiss_modals(page)

                async def shot(name):
                    n = await page.locator(".tlui-toast, [data-sonner-toast]").count()
                    assert n == 0, f"{name}: {n} toast(s)"
                    await page.screenshot(path=str(OUT / f"{name}-{tag}.png"))

                await page.locator('[data-testid="skills-create-menu"]').click()
                item = page.locator('[data-testid="skills-import"]')
                await item.wait_for()
                assert (await item.inner_text()).strip() == ("导入技能" if lang == "zh" else "Import a Skill")
                await shot("import-menu")
                await item.click()
                dlg = page.locator('[data-testid="skill-import-dialog"]')
                await dlg.wait_for()
                drop = ("将技能文件夹或 ZIP 文件拖到此处" if lang == "zh" else "Drop a Skill folder or ZIP file here")
                assert drop in await dlg.inner_text()
                await page.wait_for_timeout(300)
                await shot("import-dialog")
                for i in range(3):
                    if i:
                        await page.locator('[data-testid="skills-create-menu"]').click()
                        await page.locator('[data-testid="skills-import"]').click()
                        await dlg.wait_for()
                    await page.locator('[data-testid="skill-import-zip-input"]').set_input_files(str(zp))
                    await dlg.wait_for(state="detached", timeout=15000)
                    await page.wait_for_timeout(500)
                dirs = sorted(d.name for d in (tmp / "user/default/comfyart/skills").iterdir())
                assert dirs == ["coffee-poster", "coffee-poster-2", "coffee-poster-3"], dirs
                await page.locator('[data-testid="skills-tab-personal"]').click()
                await page.wait_for_timeout(600)
                cards = page.locator('[data-testid="skills-wall-card"]')
                ids = sorted([await cards.nth(k).get_attribute("data-skill") for k in range(await cards.count())])
                assert ids == dirs, ids
                for k in range(3):
                    assert "Coffee Poster" in await cards.nth(k).inner_text()
                await page.locator('[data-testid="skills-import-note"]').count()
                await shot("import-3x")
                print("wrote", tag, ids)
                await ctx.close()
                await server.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
