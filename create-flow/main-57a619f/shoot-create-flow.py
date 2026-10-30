"""create-skill flow shots (main 57a619f), A=home, B=Skills page Create. Typing only, never sends.
Original header: #462 live shots: real Edit Skill dialog (Name/Description/Instructions Preview·Code, Edit in Chat) + real Composer chip.

No Agent/发送 invented foot. Process/prefill seed via bot /log + WS bridge so the real ProcessTimeline renders.
$0 — mock WaveSpeed, fake provider probes.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "ComfyArt"
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

OUT = Path(os.environ.get("SHOT_OUT", "/workspace/wt-flow/shots"))

from tests.conftest import FakeProvider, write_settings  # noqa: E402
from ComfyArt.api.settings import SETTINGS_SPEC  # noqa: E402
from ComfyArt.bot import register_provider  # noqa: E402
from ComfyArt.bot.providers import BotEvent  # noqa: E402

FAKE = FakeProvider()

REPLY = {
    "zh": "已加载这个 Skill，它目前包含：\n\n- **名称**：早安咖啡店海报生成器\n- **描述**：一键生成竖版暖色调咖啡店早安海报，标题置于顶部\n- **工作流**：确认标题（默认「早安咖啡」）→ `generate_image` 3:4 竖版 → 暖色晨光、咖啡杯与蒸汽\n- **附件**：files/palette.md（配色）\n\n可以修改的方向，例如：\n\n1. 画幅比例或构图\n2. 默认标题与文案规则\n3. 配色与风格\n\n你想修改哪些方面？",
    "en": "Loaded this Skill. It currently contains:\n\n- **Name**: 早安咖啡店海报生成器\n- **Description**: one-click vertical warm-toned café morning poster, title at the top\n- **Workflow**: confirm the title (default 「早安咖啡」) → `generate_image` 3:4 portrait → warm morning light, cup and steam\n- **Files**: files/palette.md (palette)\n\nThings you could change, for example:\n\n1. Aspect ratio or layout\n2. Default title and copy rules\n3. Palette and style\n\nWhat would you like to change?",
}


def script(lang):
    return [
        BotEvent(t="thinking", text="Read the skill first, then list it."),
        BotEvent(t="tool_use", name="skill", input={"action": "read", "name": "早安咖啡店海报生成器"}, id="t1"),
        BotEvent(t="tool_result", name="skill", text=SKILL_MD, id="t1"),
        BotEvent(t="delta", text=REPLY[lang]),
    ]

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


SKILL_MD = """---
name: 早安咖啡店海报生成器
description: 一键生成竖版暖色调咖啡店早安海报，标题置于顶部，适合门店早安图与社媒传播。
---

## Core Methodology
本技能用于快速产出一张竖版咖啡店早安主题海报，核心约束为：**竖版构图**、顶部大标题、暖色调氛围。

## Workflow
1. 确认用户提供的标题，默认使用「早安咖啡」。标题必须原样保留，不擅自增删文案。
2. 使用 `generate_image`，比例 `3:4`，作为咖啡店竖版海报的标准画幅。
3. 在 prompt 中描述暖色晨光、咖啡杯与蒸汽，保持画面干净。
"""


def seed(tmp: Path):
    d = tmp / "user/default/comfyart/skills/coffee-morning"
    (d / "files").mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(SKILL_MD)
    (d / "files/palette.md").write_text("# Palette\n- #6B4226 espresso\n- #F3E5D0 latte foam\n")
    (d / "images.json").write_text("{}")
    # stub the app's own user files so the shell boots without 404 toasts
    ca = tmp / "user/default/comfyart"
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



PROMPT = {"zh": "做一个咖啡店早安海报技能", "en": "A skill for café morning posters"}


async def main():
    import tempfile
    OUT.mkdir(parents=True, exist_ok=True)
    _patch_providers()
    tmp = Path(tempfile.mkdtemp(prefix="caflow-"))
    seed(tmp)
    server, base = await build_app(tmp)
    register_provider(FAKE)
    SETTINGS_SPEC["bot-model-fake-test"] = ""
    write_settings(**{"bot-provider": FAKE.id, "enable-bot": True, "enable-mcp": True})
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for lang in ("zh", "en"):
                theme = "light"
                tag = f"{lang}-{theme}"
                ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
                await ctx.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
                await ctx.add_init_script(f"localStorage.setItem('comfyart.theme','{theme}')")
                page = await ctx.new_page()
                # safety: never let a send reach a bot/generate endpoint
                async def block(route):
                    print("BLOCKED", route.request.method, route.request.url)
                    await route.abort()
                for pat in ("**/comfyart/bot/send**", "**/comfyart/bot/chat**", "**/api/prompt**", "**/comfyart/generate**"):
                    await page.route(pat, block)

                async def shot(name):
                    await page.wait_for_timeout(500)
                    path = OUT / f"{name}-{tag}.png"
                    await page.screenshot(path=str(path))
                    print("shot", path.name, page.url)

                async def type_prompt(prefix):
                    ed = page.locator(".ca-composer textarea, .ca-composer [contenteditable]").first
                    await ed.wait_for(timeout=15000)
                    await ed.click()
                    await page.keyboard.type(PROMPT[lang])
                    await shot(f"{prefix}-typed")
                    # layout facts of the input
                    info = await page.evaluate("""() => { const c=document.querySelector('.ca-composer'); const a=document.querySelector('.ca-agent');
                      const r=c&&c.getBoundingClientRect(); return {composer: r&&[Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)],
                      agentMax: a&&a.hasAttribute('data-max'), vw: innerWidth, vh: innerHeight, chip: !!document.querySelector('[data-testid=skill-creator-chip]'),
                      tl: !!document.querySelector('.tl-canvas')} }""")
                    print("layout", prefix, tag, info)

                # ---- A: home page
                await page.goto(base, wait_until="networkidle")
                await page.wait_for_timeout(1500)
                await dismiss_modals(page)
                await shot("A1-home")
                await page.mouse.wheel(0, 2000)
                await shot("A2-home-scrolled")
                await page.mouse.wheel(0, -4000)
                mode = page.locator(".ca-landing__mode").first
                if await mode.count():
                    await mode.click()
                    await shot("A3-home-mode-menu")
                    await page.keyboard.press("Escape")
                # no 'Skill Creator' on home: closest path = new canvas → composer + → Skill → 技能创建器
                await page.goto(f"{base}?project=flowa{lang}&new=1", wait_until="networkidle")
                await page.locator(".tl-canvas").wait_for(timeout=30000)
                await page.wait_for_timeout(1500)
                await dismiss_modals(page)
                await shot("A4-canvas-new")
                await page.locator(".ca-composer__foot .ca-bar__btn--icon").first.click()
                await page.wait_for_timeout(300)
                await page.locator(".ca-menu__item", has_text="Skill").first.click()
                await shot("A5-composer-skill-menu")
                await page.locator('[data-testid="skill-creator-start"]').click()
                await shot("A6-creator-chip")
                await type_prompt("A7")

                # ---- B: Skills page → Create
                await page.goto(f"{base}?view=skills", wait_until="networkidle")
                await page.wait_for_timeout(1500)
                await dismiss_modals(page)
                await shot("B1-skills-page")
                await page.locator('[data-testid="skills-create"]').hover()
                await shot("B2-create-hover")
                await page.locator('[data-testid="skills-create"]').click()
                await page.locator(".tl-canvas").wait_for(timeout=30000)
                await page.wait_for_timeout(2500)
                await dismiss_modals(page)
                await shot("B3-after-create")
                await type_prompt("B4")
                await ctx.close()
            await browser.close()
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())
