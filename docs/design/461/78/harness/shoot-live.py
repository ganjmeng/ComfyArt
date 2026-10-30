"""#460/#461 live shots: real Skills page + real Composer (ComposerSlot ↑/voice, shortLabel+logo).

No Agent/发送 invented foot. Process/prefill seed via bot /log + WS bridge so the real ProcessTimeline renders.
$0 — mock WaveSpeed, fake provider probes.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
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

OUT460 = ROOT / "docs/design/460/78/after"
OUT461 = ROOT / "docs/design/461/78/after"
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
        ("/api/userdata", js([])),
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


PROCESS_BLOCKS = [
    {"type": "thinking", "text": "先把交付物、比例和风格规则写清楚，再落成可复用 Skill。"},
    {"type": "tool_use", "name": "skill", "id": "tool_1", "input": {"action": "save", "name": "Coffee menu poster"}},
    {"type": "tool_result", "name": "skill", "id": "tool_1", "status": "ok", "text": "saved"},
]


async def seed_process(page, project: str, scene: str):
    """Create chat + log process/prefill blocks via real API; WS bridge updates the UI."""
    # wait for bot status
    await page.wait_for_function(
        """async () => {
          try {
            const r = await fetch('/comfyart/bot/status');
            const j = await r.json();
            return j.enabled && (j.providers||[]).some(p => p.id==='local-llm' && p.available);
          } catch { return false; }
        }""",
        timeout=20000,
    )
    result = await page.evaluate(
        """async ({ project, scene, blocks }) => {
          const create = await fetch('/comfyart/bot/chats', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ project, provider: 'local-llm' }),
          });
          const cj = await create.json();
          if (!create.ok) throw new Error('create chat: ' + JSON.stringify(cj));
          const text = 'Create minimalist coffee shop menu poster skill';
          const useBlocks = scene === 'prefill'
            ? [{ type: 'text', text: '好的，我会按这个想法写成可复用 Skill：交付物、3:4、暖色咖啡店风格。' }]
            : blocks;
          const log = await fetch('/comfyart/bot/chats/' + cj.chat.id + '/log', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ text, blocks: useBlocks }),
          });
          const lj = await log.json();
          if (!log.ok) throw new Error('log: ' + JSON.stringify(lj));
          return cj.chat.id;
        }""",
        {"project": project, "scene": scene, "blocks": PROCESS_BLOCKS},
    )
    # WS bridge should deliver chat_created + messages_logged. Also open via history as fallback.
    await page.wait_for_timeout(1000)
    for attempt in range(3):
        if await page.locator(".ca-process, .ca-chat__bot, .ca-chat__user").count():
            break
        hist = page.locator(".ca-split__chev").first
        if await hist.count():
            await hist.click()
            await page.wait_for_timeout(400)
            item = page.locator(".ca-history__item").first
            if await item.count():
                await item.click()
                await page.wait_for_timeout(800)
                continue
            await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
    return result


async def dismiss_modals(page):
    for _ in range(3):
        modal = page.locator(".ca-modal")
        if await modal.count() == 0:
            break
        # prefer skip / later / close
        for sel in (
            "button:has-text('稍后再说')",
            "button:has-text('Later')",
            "button:has-text('跳过')",
            "button:has-text('Skip')",
            ".ca-modal button.ca-panel__secondary",
            ".ca-modal .ca-panel__icon",
        ):
            btn = page.locator(sel).first
            if await btn.count():
                await btn.click()
                await page.wait_for_timeout(400)
                break
        else:
            break


async def main():
    import tempfile

    OUT460.mkdir(parents=True, exist_ok=True)
    OUT461.mkdir(parents=True, exist_ok=True)
    _patch_providers()

    tmp = Path(tempfile.mkdtemp(prefix="ca460-"))
    server, base = await build_app(tmp)
    print("app", base)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            # --- Explore (real Skills page) ---
            for theme, name in (("light", "explore-zh-light.png"), ("dark", "explore-zh-dark.png")):
                ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
                page = await ctx.new_page()
                await page.add_init_script("localStorage.setItem('comfyart.lang','zh')")
                await page.add_init_script(f"localStorage.setItem('comfyart.theme','{theme}')")
                await page.goto(f"{base}?view=skills", wait_until="networkidle")
                await page.wait_for_selector('[data-testid="skills-page"]', timeout=20000)
                await page.wait_for_timeout(1200)
                await dismiss_modals(page)
                shell = page.locator('[data-testid="home-shell"]')
                if await shell.count() == 0:
                    shell = page.locator(".ca-home").first
                await shell.screenshot(path=str(OUT460 / name))
                print("wrote", OUT460 / name, (OUT460 / name).stat().st_size)
                # assert real page
                assert await page.locator('[data-testid="skills-tabs"]').count()
                await ctx.close()

            # --- Creator process / prefill (real Composer) ---
            shots = [
                ("process", "light", "creator-process-zh-light.png"),
                ("process", "dark", "creator-process-zh-dark.png"),
                ("prefill", "light", "creator-prefill-zh-light.png"),
                ("prefill", "dark", "creator-prefill-zh-dark.png"),
            ]
            for scene, theme, name in shots:
                ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
                page = await ctx.new_page()
                await page.add_init_script("localStorage.setItem('comfyart.lang','zh')")
                await page.add_init_script(f"localStorage.setItem('comfyart.theme','{theme}')")
                pid = f"s{scene}{theme[:1]}"
                await page.goto(f"{base}?project={pid}&new=1&createSkill=1", wait_until="networkidle")
                await page.locator(".tl-canvas").wait_for(timeout=30000)
                await page.wait_for_timeout(1500)
                await dismiss_modals(page)
                await page.wait_for_selector('[data-testid="skill-creator-chip"]', timeout=20000)
                # Real ComposerSlot — never text 发送 / bare Agent mode
                await page.wait_for_selector(".ca-composer__slotwrap, .ca-composer__foot .ca-gen__send, .ca-composer__foot .ca-voice", timeout=10000)
                foot = page.locator(".ca-composer__foot")
                foot_text = await foot.inner_text()
                assert "发送" not in foot_text, f"invented 发送 in foot: {foot_text!r}"
                # mode should show shortLabel (Loomi) when agent ready, not bare 'Agent' as only mid text
                mode = page.locator(".ca-composer__mode")
                if await mode.count():
                    mt = (await mode.inner_text()).strip()
                    assert mt != "Agent", f"invented bare Agent mode: {mt!r}"

                await seed_process(page, pid, scene)
                await page.wait_for_timeout(1000)

                # Crop agent panel (composer + thread)
                panel = page.locator(".ca-agent").first
                await panel.wait_for(timeout=10000)
                # Ensure chip still visible
                assert await page.locator('[data-testid="skill-creator-chip"]').count()
                await panel.screenshot(path=str(OUT461 / name))
                print("wrote", OUT461 / name, (OUT461 / name).stat().st_size)
                await ctx.close()

            await browser.close()
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())
