"""#462 live shots: real Edit Skill dialog (Name/Description/Instructions Preview·Code, Edit in Chat) + real Composer chip.

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

OUT = ROOT / "docs/design/462/after"

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


async def open_edit(page, lang):
    await page.locator(".ca-composer__foot .ca-bar__btn--icon").first.click()
    await page.wait_for_timeout(300)
    await page.locator(".ca-menu__item", has_text="Skill").first.click()
    await page.wait_for_timeout(400)
    await page.locator(".ca-menu__item", has_text="管理技能" if lang == "zh" else "Manage").first.click()
    await page.wait_for_selector(".ca-skills-dialog")
    await page.locator(".ca-skills-dialog .ca-memory__row", has_text="早安咖啡店").locator("button[title='%s']" % ("编辑" if lang == "zh" else "Edit")).click()
    await page.wait_for_selector('[data-testid="skill-form"]')
    await page.wait_for_timeout(400)


async def main():
    import tempfile
    OUT.mkdir(parents=True, exist_ok=True)
    _patch_providers()
    tmp = Path(tempfile.mkdtemp(prefix="ca462-"))
    seed(tmp)
    server, base = await build_app(tmp)
    register_provider(FAKE)
    SETTINGS_SPEC["bot-model-fake-test"] = ""
    write_settings(**{"bot-provider": FAKE.id, "enable-bot": True, "enable-mcp": True})
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            for lang in ("zh", "en"):
                for theme in ("light", "dark"):
                    ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
                    page = await ctx.new_page()
                    await page.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
                    await page.add_init_script(f"localStorage.setItem('comfyart.theme','{theme}')")
                    await page.goto(f"{base}?project=s462{lang}{theme[0]}&new=1", wait_until="networkidle")
                    await page.locator(".tl-canvas").wait_for(timeout=30000)
                    await page.wait_for_timeout(1500)
                    await dismiss_modals(page)
                    await open_edit(page, lang)
                    tag = f"{lang}-{theme}"

                    async def shot(name, target=None):
                        n = await page.locator(".tlui-toast, .tlui-toast__container li, [data-sonner-toast]").count()
                        assert n == 0, f"{name}: {n} toast(s) on screen"
                        assert await page.locator(".ca-import, [data-testid='skill-import']").count() == 0, f"{name}: import dialog open"
                        await (target or page).screenshot(path=str(OUT / f"{name}-{tag}.png"))

                    form = page.locator('[data-testid="skill-form"]')
                    await shot("edit-preview")
                    if tag == "zh-light":
                        await page.locator('[data-testid="skill-form-scroll"]').evaluate("e => e.scrollTop = e.scrollHeight")
                        await page.wait_for_timeout(300)
                        await shot("edit-bottom")
                        await page.locator('[data-testid="skill-form-scroll"]').evaluate("e => e.scrollTop = 0")
                    await page.locator('[data-testid="skill-tabs"] button').nth(1).click()
                    await page.wait_for_timeout(300)
                    await shot("edit-code")
                    name = await page.locator("#skill-name").input_value()
                    FAKE.script = script(lang)
                    FAKE.last_turn = None
                    await page.locator('[data-testid="skill-edit-in-chat"]').click()
                    # new project: the auto-sent user turn carries a name-only skill chip (no prefix, no ×)
                    chip = page.locator('[data-testid="user-bubble"] [data-testid="user-skill-chip"]').first  # #462: inside the bubble
                    await chip.wait_for(timeout=15000)
                    assert (await chip.inner_text()).strip() == name, await chip.inner_text()
                    title = ("修改" + name + " Skill") if lang == "zh" else ("Edit " + name + " Skill")
                    assert await page.locator(".ca-head__name").input_value() == title
                    # mocked agent reply: 思考完成 → 技能加载完成, lists the content, asks what to change
                    ask = "你想修改哪些方面" if lang == "zh" else "What would you like to change"
                    await page.get_by_text(ask).first.wait_for(timeout=15000)
                    for lbl in (("思考完成", "技能加载完成") if lang == "zh" else ("Thought", "Skill ready")):
                        assert await page.get_by_text(lbl).count() >= 1, lbl
                    assert FAKE.last_turn is not None
                    ed = page.locator(".ca-composer [contenteditable], .ca-composer textarea").first
                    assert (await ed.inner_text() if await ed.evaluate("e => e.isContentEditable") else await ed.input_value()).strip() == ""
                    await page.wait_for_timeout(800)
                    await shot("edit-in-chat")
                    print("wrote", tag)
                    await ctx.close()
            await browser.close()
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())
