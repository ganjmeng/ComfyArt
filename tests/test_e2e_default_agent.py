"""#219: a new user's left Agent panel defaults to ComfyArt Agent (built-in) even with claude/codex detected;
undetected tools are greyed with 未检测到 / Not detected; no WaveSpeed key shows a clear notice linking to key
settings. Provider probes are mocked; nothing paid is called ($0)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("AGENT_SHOTS")
DETECTED = ("claude-code", "codex")
MISSING = ("qwen-code", "deepseek-harness")


@pytest.fixture()
def fake_tools(monkeypatch):
    from ComfyArt.bot import providers as registry
    for pid in [k for k in registry._REGISTRY if k not in ("local-llm", *DETECTED, *MISSING)]:
        monkeypatch.delitem(registry._REGISTRY, pid)  # hide test-only agents (Fake, Fake Models) from the UI
    from ComfyArt.bot import get_provider
    from ComfyArt.bot.local_llm import LocalLlmProvider
    from ComfyArt.bot.providers import ProviderStatus

    def status(ok):
        async def probe(*_a):
            return ProviderStatus(available=ok, version="1.0.0" if ok else "", logged_in=ok or None,
                                  detail="" if ok else "executable not found")
        return probe
    for pid in DETECTED:
        monkeypatch.setattr(get_provider(pid), "probe", status(True))
    for pid in MISSING:
        monkeypatch.setattr(get_provider(pid), "probe", status(False))

    async def models(self):
        return ["deepseek/deepseek-v4.1-flash-1017"]
    monkeypatch.setattr(LocalLlmProvider, "probe", lambda self: status(True)())
    monkeypatch.setattr(LocalLlmProvider, "list_models", models)
    for pid in DETECTED:
        monkeypatch.setattr(get_provider(pid), "list_models", models.__get__(get_provider(pid)))


async def _page(p, url, lang):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
    pg = await ctx.new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}')")
    await pg.goto(url)
    await pg.wait_for_timeout(1500)
    await pg.mouse.click(28, 83)  # home: new project
    await pg.locator(".tl-canvas").wait_for()
    await pg.wait_for_timeout(2000)
    return browser, pg


CONFIRM = {
    "zh": "外部 Agent 需要开启 MCP，开启后本机的 MCP 客户端可以读写当前画布。开启？",
    "en": "External agents need MCP. Once on, MCP clients on this computer can read and edit your canvas. Turn on?",
}


BAR_FITS = """() => {
  const foot = document.querySelector('.ca-composer__foot'); const fr = foot.getBoundingClientRect()
  const kids = [...foot.children].map((e) => e.getBoundingClientRect()).filter((r) => r.width > 0)
  const modes = [...foot.querySelectorAll('.ca-composer__mode')]
  return {
    modes: modes.map((m) => m.innerText.trim()),
    clipped: modes.some((m) => m.scrollWidth > m.clientWidth + 1),
    overlap: kids.some((r, i) => i > 0 && r.left < kids[i - 1].right - 0.5),
    overflow: kids.some((r) => r.right > fr.right + 0.5 || r.left < fr.left - 0.5),
  }
}"""


async def _bar_fits(pg, agent="ComfyArt"):
    bar = await pg.evaluate(BAR_FITS)
    assert bar["modes"] == ["Agent", agent], bar
    assert not bar["clipped"] and not bar["overlap"] and not bar["overflow"], bar


async def _crop(pg, loc, name, pad=8):
    if not SHOTS:
        return
    b = await loc.bounding_box()
    await pg.screenshot(path=f"{SHOTS}/{name}.png", clip={"x": max(b["x"] - pad, 0), "y": max(b["y"] - pad, 0), "width": b["width"] + 2 * pad, "height": b["height"] + 2 * pad})


def _shot(name):
    return {"path": f"{SHOTS}/{name}.png"} if SHOTS else None


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_new_user_defaults_to_builtin_and_can_switch(app_url, fake_tools, monkeypatch, lang):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    builtin = "ComfyArt Agent（内置）" if lang == "zh" else "ComfyArt Agent (built-in)"
    nd = "未检测到" if lang == "zh" else "Not detected"
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        assert await pg.get_by_text("还没有开启" if lang == "zh" else "not enabled yet").count() == 0
        trigger = pg.get_by_title("选择 Agent" if lang == "zh" else "Select agent").first
        await trigger.wait_for()
        assert (await trigger.inner_text()).strip() == "ComfyArt"
        assert await trigger.locator("[title]").first.get_attribute("title") == builtin
        await _bar_fits(pg)  # default panel width: 'Agent ⌄ ComfyArt ⌄' both in full
        if SHOTS:
            await pg.screenshot(**_shot(f"first-open-{lang}"))
            await _crop(pg, pg.locator(".ca-composer__foot"), f"close-bar-{lang}")
        await trigger.click()
        menu = pg.locator(".ca-agentpick")
        await menu.wait_for()
        items = menu.locator(".ca-menu__item")
        assert builtin in await items.nth(0).inner_text()
        for label in ("Qwen Code", "DeepSeek Harness"):
            row = items.filter(has_text=label)
            assert await row.is_disabled() and nd in await row.inner_text()
        if SHOTS:
            await pg.screenshot(**_shot(f"picker-{lang}"))
            await _crop(pg, menu, f"close-picker-{lang}")
        await items.filter(has_text="Claude Code").click()
        dialog = pg.locator(".ca-modal")
        await dialog.wait_for()
        assert CONFIRM[lang] in await dialog.inner_text()
        if SHOTS:
            await pg.screenshot(**_shot(f"confirm-{lang}"))
            await _crop(pg, dialog.locator(".ca-modal__card"), f"close-confirm-{lang}")
        await dialog.locator(".ca-panel__primary").click()  # accept: MCP on, then switch
        await pg.wait_for_timeout(800)
        from ComfyArt.api import settings as _s
        assert _s.get_setting("enable-mcp") is True
        assert (await trigger.inner_text()).strip() == "Claude Code"
        from ComfyArt.api import settings
        assert settings.get_setting("bot-provider") == "claude-code"
        await _bar_fits(pg, "Claude Code")  # an external tool's name also shows in full at the default width
        if SHOTS:
            await pg.screenshot(**_shot(f"switched-{lang}"))
            await _crop(pg, pg.locator(".ca-composer__foot"), f"close-bar-cc-{lang}")
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_no_key_shows_notice_with_link(app_url, fake_tools, monkeypatch, lang):  # noqa: F811
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    monkeypatch.delenv("COMFYART_LOCAL_LLM_API_KEY", raising=False)
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await pg.keyboard.press("Escape")  # the WaveSpeed key dialog opens by itself for a keyless user
        await pg.wait_for_timeout(500)
        notice = pg.locator('.ca-chat__notice[data-level="error"]')
        await notice.wait_for()
        assert ("WaveSpeed Key" if lang == "zh" else "WaveSpeed key") in await notice.inner_text()
        if SHOTS:
            await pg.screenshot(**_shot(f"no-key-{lang}"))
            await _crop(pg, notice, f"close-no-key-{lang}")
        await notice.locator("a").click()
        await pg.wait_for_timeout(300)
        assert await pg.locator(".ca-modal, [role=dialog]").count() > 0
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_external_tool_confirm_cancel_keeps_builtin(app_url, fake_tools, monkeypatch, lang):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    from ComfyArt.api import settings as _s
    assert _s.get_setting("enable-mcp") is False
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        trigger = pg.get_by_title("选择 Agent" if lang == "zh" else "Select agent").first
        await trigger.click()
        await pg.locator(".ca-agentpick .ca-menu__item").filter(has_text="Claude Code").click()
        dialog = pg.locator(".ca-modal")
        await dialog.wait_for()
        assert CONFIRM[lang] in await dialog.inner_text()
        await dialog.locator(".ca-panel__secondary").click()  # cancel
        await pg.wait_for_timeout(800)
        assert await pg.locator(".ca-modal").count() == 0
        assert (await trigger.inner_text()).strip() == "ComfyArt"
        assert _s.get_setting("enable-mcp") is False
        assert _s.get_setting("bot-provider") == "local-llm"
        await browser.close()


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_url_host_change_shows_reenter_key_helper(app_url, fake_tools, monkeypatch, lang):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    from conftest import write_settings
    write_settings(**{"bot-local-llm-url": "https://llm.example.com/v1", "bot-local-llm-key": "sk-mock-custom"})
    helper = "地址已更改，请重新填写 Key" if lang == "zh" else "URL changed. Please re-enter the key."
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _page(p, app_url, lang)
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        await pg.get_by_title("选择 Agent" if lang == "zh" else "Select agent").first.click()
        await pg.locator(".ca-agentpick .ca-menu__item").filter(has_text="Agent 设置" if lang == "zh" else "Agent Settings").click()
        modal = pg.locator(".ca-modal__card")
        await modal.wait_for()
        url_in = modal.locator("label.ca-rename__field", has_text="模型地址" if lang == "zh" else "model URL").locator("input")
        key_field = modal.locator("label.ca-rename__field", has_text="API Key" if lang == "zh" else "API key")
        assert await key_field.get_by_text(helper).count() == 0
        hint = "留空则使用 WaveSpeed Key" if lang == "zh" else "Leave empty to use your WaveSpeed key"
        assert await key_field.locator("input").get_attribute("placeholder") == hint
        fit = await key_field.locator("input").evaluate("""(el) => { const cs = getComputedStyle(el); const c = document.createElement('canvas').getContext('2d');
          c.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`; const room = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
          return [c.measureText(el.placeholder).width, room] }""")
        assert fit[0] <= fit[1], fit  # the placeholder is not cut off
        await url_in.fill("https://llm.example.com/v2")  # same host: key kept, no helper
        assert await key_field.get_by_text(helper).count() == 0
        await url_in.fill("https://other-llm.example.org/v1")
        line = key_field.get_by_text(helper)
        await line.wait_for()
        assert await line.get_attribute("class") == "ca-adv__help"  # the existing grey helper style
        key_in = key_field.locator("input")
        lb, ib = await line.bounding_box(), await key_in.bounding_box()
        assert abs(lb["x"] - ib["x"]) < 0.5, (lb, ib)  # left-aligned with the input's left edge
        assert await key_field.locator("input").input_value() == ""
        if SHOTS:
            await _crop(pg, key_field, f"close-key-helper-{lang}")
        await url_in.fill("https://llm.wavespeed.ai/v1")  # back on WaveSpeed: cleared, WaveSpeed key used, no helper
        assert await key_field.get_by_text(helper).count() == 0
        await browser.close()
