"""#462 slash-picked message shots: pick a skill with "/", type a line, send to a mocked agent ($0).

Runs unchanged on main (before) and on the #462 tip (after); both copies must sit in a dir named ComfyArt.
  python3 docs/design/462/shoot-slash.py <out-dir> <label>      e.g. ... /tmp/before main
Writes slash-<label>-<lang>.png and, when <label> is not main, slash-long-<label>-zh.png (long skill name).
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("shoot_live", HERE / "shoot-live.py")
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)

from playwright.async_api import async_playwright  # noqa: E402
from ComfyArt.bot.providers import BotEvent  # noqa: E402

LONG = "早安咖啡店海报生成器·门店社媒竖版暖色调超长名称版本二"
TEXT = {"zh": "我想修改这个 Skill", "en": "I want to edit this Skill"}
REPLY = {"zh": "好的，你想修改哪些方面？", "en": "Sure, what would you like to change?"}


def seed_long(tmp: Path):
    d = tmp / "user/default/comfyart/skills/coffee-long"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {LONG}\ndescription: long-name sample\n---\n\nSame as the café poster skill.\n")
    (d / "images.json").write_text("{}")


async def send_slash(page, name, text):
    box = page.locator(".ca-composer textarea").first
    await box.click()
    await box.fill("/")
    # exact name: the short name is a prefix of the long one
    await page.locator(".ca-composer__suggest .ca-menu__item").filter(has=page.get_by_text(name, exact=True)).first.click()
    await page.wait_for_timeout(300)
    await box.fill(text)
    await box.press("Enter")


async def main(out: Path, label: str):
    out.mkdir(parents=True, exist_ok=True)
    live._patch_providers()
    tmp = Path(tempfile.mkdtemp(prefix="ca462s-"))
    live.seed(tmp)
    seed_long(tmp)
    server, base = await live.build_app(tmp)
    live.register_provider(live.FAKE)
    live.SETTINGS_SPEC["bot-model-fake-test"] = ""
    live.write_settings(**{"bot-provider": live.FAKE.id, "enable-bot": True, "enable-mcp": True})
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            jobs = [(lang, "早安咖啡店海报生成器", f"slash-{label}-{lang}") for lang in ("zh", "en")]
            if label != "main":
                jobs.append(("zh", LONG, f"slash-long-{label}-zh"))
            for i, (lang, name, fname) in enumerate(jobs):
                ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
                page = await ctx.new_page()
                await page.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
                await page.add_init_script("localStorage.setItem('comfyart.theme','light')")
                await page.goto(f"{base}?project=sl462{label}{i}&new=1", wait_until="networkidle")
                await page.locator(".tl-canvas").wait_for(timeout=30000)
                await page.wait_for_timeout(1500)
                await live.dismiss_modals(page)
                live.FAKE.script = [BotEvent(t="delta", text=REPLY[lang])]
                await send_slash(page, name, TEXT[lang])
                await page.get_by_text(REPLY[lang]).first.wait_for(timeout=15000)
                await page.wait_for_timeout(600)
                assert await page.locator(".tlui-toast, [data-sonner-toast]").count() == 0
                await page.screenshot(path=str(out / f"{fname}.png"), clip={"x": 0, "y": 0, "width": 720, "height": 450})
                print("wrote", fname)
                await ctx.close()
            await browser.close()
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2]))
