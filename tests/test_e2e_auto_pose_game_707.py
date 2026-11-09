"""#707 pose-fission and game-art local auto entry. Not a provider, LLM, or visual pass.

Same chain as before-after: the local LLM fixture names the skill and a prompt only.
The real MCP tool selects the exact-size model. The page applies model prefs.
Disabled or unavailable compatible models make no mock submit and do not switch to flare.
A matching LOCAL FIXTURE is placed at the skill's pixels. The fixture is not game UI.
"""
from __future__ import annotations

import asyncio
import io
import json
import re

import pytest
from PIL import Image, ImageDraw

from conftest import SENT, write_settings
from test_e2e_skill_canvas_707 import QWEN, app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")

FLARE = "openai/gpt-image-2.5-flare/text-to-image"
CASES = (
    ("pose-fission", 1536, 2048, (36, 96, 168),
     "Same person and scene, one new camera angle. One 3:4 still."),
    ("game-art", 1024, 1824, (32, 128, 72),
     "One portrait mobile game UI screen, title bar, list, button, bottom nav. Not key art."),
)


def _png(skill: str, w: int, h: int, rgb: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (w, h), rgb)
    ImageDraw.Draw(img).text((16, 16), f"LOCAL FIXTURE {skill} {w}x{h}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _commands():
    return [d for event, d in SENT if event == "comfyart-mcp-command"]


@pytest.mark.parametrize("skill,w,h,rgb,prompt", CASES, ids=["pose-fission", "game-art"])
async def test_exact_skill_auto_entry_respects_prefs(app_url, mock_ws, monkeypatch, skill, w, h, rgb, prompt):  # noqa: F811
    import aiohttp
    from ComfyArt.api import mcp_commands
    from server import PromptServer

    mcp_commands._pages.clear()
    arguments = {"prompt": prompt, "skill": skill}
    assert set(arguments) == {"prompt", "skill"}
    write_settings(**{"enable-mcp": True})
    sockets: list = []
    original = PromptServer.instance.send_sync

    def forward(event, data, sid=None):
        original(event, data, sid)
        raw = json.dumps({"type": event, "data": data})
        for ws in list(sockets):
            ws.send(raw)

    monkeypatch.setattr(PromptServer.instance, "send_sync", forward)
    mock_ws["png"] = _png(skill, w, h, rgb)

    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
        page = await ctx.new_page()
        await page.add_init_script("localStorage.setItem('comfyart.lang','zh'); localStorage.setItem('comfyart.e2e','1')")
        await page.goto(app_url)
        await page.wait_for_timeout(1200)
        await page.mouse.click(28, 83)
        await page.locator(".tl-canvas").wait_for()
        await page.wait_for_timeout(600)
        if await page.locator(".ca-modal").count():
            await page.locator(".ca-modal button").nth(-2).click()
        await page.wait_for_function(
            "() => window.__comfyartE2E && window.__comfyartE2E.listed().includes('openai/gpt-image-2.5-flare/text-to-image')"
        )
        for _ in range(50):
            if sockets:
                break
            await asyncio.sleep(0.1)
        assert sockets, "page websocket was not connected"
        pages = dict(mcp_commands._pages)
        assert pages, "the canvas did not register a project"
        for client in pages:
            PromptServer.instance.sockets[client] = object()
        project = next(iter(pages.values()))
        origin = app_url.split("/comfyart/")[0]
        listed = await page.evaluate("() => window.__comfyartE2E.listed()")
        assert QWEN not in listed and FLARE in listed

        async def call():
            async with aiohttp.ClientSession() as http:
                res = await http.post(
                    f"{origin}/comfyart/mcp?project={project}",
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "generate_image", "arguments": arguments}},
                    timeout=aiohttp.ClientTimeout(total=30),
                )
                return await res.json()

        async def prefs(auto: bool, enabled: list[str]):
            await page.evaluate(
                "([auto, enabled]) => window.__comfyartE2E.setPrefs({ auto, enabled })",
                [auto, enabled],
            )

        await prefs(False, listed)
        disabled = await call()
        text = disabled["result"]["content"][0]["text"]
        assert disabled["result"]["isError"] is True, text
        assert "没有可用的尺寸兼容模型" in text and "没有提交" in text
        assert mock_ws["submits"] == []
        sent = _commands()[-1]["args"]
        assert sent["model"] == QWEN and sent["width"] == w and sent["height"] == h
        assert FLARE not in sent.get("size_candidates", [])

        await prefs(False, [FLARE])
        none = await call()
        assert none["result"]["isError"] is True
        assert "没有可用的尺寸兼容模型" in none["result"]["content"][0]["text"]
        assert mock_ws["submits"] == []

        await prefs(True, [])
        allowed = await call()
        assert mock_ws["submits"], allowed
        model, payload = mock_ws["submits"][-1]
        assert model == QWEN and payload.get("size") == f"{w}*{h}" and "size_lock" not in payload
        assert len(mock_ws["submits"]) == 1 and all(m != FLARE for m, _b in mock_ws["submits"])
        await page.locator(".tl-image img, img.tl-image").first.wait_for(timeout=25000)
        natural = await page.evaluate(
            """async () => {
              const img = document.querySelector('.tl-image img, img.tl-image')
              await img.decode()
              return [img.naturalWidth, img.naturalHeight]
            }"""
        )
        assert natural == [w, h], (skill, natural)
        await browser.close()
