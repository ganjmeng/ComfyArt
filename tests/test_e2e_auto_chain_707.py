"""#707 free local chain. Not a provider, LLM, or visual pass.

Entry: a recorded local LLM fixture emits one generate_image tool call that names
the skill and the prompt only. It does not name a model, size_lock, or size_candidates.
The real MCP tool handler then chooses the model, and the open page applies the
user's model prefs before anything is submitted.

Upstream is the local WaveSpeed mock. A matching LOCAL FIXTURE is audited from the
downloaded file and placed on the real canvas. A disabled or unavailable compatible
model returns before that mock is called.
"""
from __future__ import annotations

import io
import json
import re

import pytest
from PIL import Image, ImageDraw

from conftest import SENT, write_settings
from test_e2e_skill_canvas_707 import QWEN, app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")

FLARE = "openai/gpt-image-2.5-flare/text-to-image"
# External LLM boundary only. The fixture does not choose a model.
LOCAL_LLM_FIXTURE = {
    "label": "LOCAL LLM FIXTURE, not a live model",
    "tool": "generate_image",
    "arguments": {
        "prompt": "LinkedIn banner. Headline in quotes: Data systems.",
        "skill": "linkedin-banner",
    },
}


def _png(w: int, h: int) -> bytes:
    img = Image.new("RGB", (w, h), (168, 120, 36))
    ImageDraw.Draw(img).text((16, 16), f"LOCAL FIXTURE linkedin-banner {w}x{h}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _commands():
    return [d for event, d in SENT if event == "comfyart-mcp-command"]


async def _boot(page, app_url: str):
    await page.add_init_script("localStorage.setItem('comfyart.lang','zh'); localStorage.setItem('comfyart.e2e','1')")
    await page.goto(app_url)
    await page.wait_for_timeout(1500)
    await page.mouse.click(28, 83)
    await page.locator(".tl-canvas").wait_for()
    await page.wait_for_timeout(800)
    if await page.locator(".ca-modal").count():
        await page.locator(".ca-modal button").nth(-2).click()
    await page.wait_for_function(
        "() => window.__comfyartE2E && window.__comfyartE2E.listed().includes('openai/gpt-image-2.5-flare/text-to-image')"
    )


async def test_skill_tool_auto_picks_then_page_prefs_gate_the_mock(app_url, mock_ws, monkeypatch):  # noqa: F811
    import aiohttp
    from ComfyArt.api import mcp_commands
    from server import PromptServer

    assert set(LOCAL_LLM_FIXTURE["arguments"]) == {"prompt", "skill"}
    write_settings(**{"enable-mcp": True})
    sockets: list = []
    original = PromptServer.instance.send_sync

    def forward(event, data, sid=None):
        original(event, data, sid)
        raw = json.dumps({"type": event, "data": data})
        for ws in list(sockets):
            ws.send(raw)

    monkeypatch.setattr(PromptServer.instance, "send_sync", forward)
    mock_ws["png"] = _png(1584, 396)

    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
        page = await ctx.new_page()
        await _boot(page, app_url)
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
                          "params": {"name": LOCAL_LLM_FIXTURE["tool"], "arguments": LOCAL_LLM_FIXTURE["arguments"]}},
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
        disabled_text = disabled["result"]["content"][0]["text"]
        assert disabled["result"]["isError"] is True
        assert "没有可用的尺寸兼容模型" in disabled_text
        assert "没有提交" in disabled_text
        assert mock_ws["submits"] == []
        sent = _commands()[-1]["args"]
        assert sent["model"] == QWEN and sent["size_lock"] is True
        assert FLARE not in sent.get("size_candidates", [])
        assert "model" not in LOCAL_LLM_FIXTURE["arguments"]

        await prefs(False, [FLARE])
        none = await call()
        none_text = none["result"]["content"][0]["text"]
        assert none["result"]["isError"] is True and "没有可用的尺寸兼容模型" in none_text
        assert mock_ws["submits"] == []
        assert all(item[0] != FLARE for item in mock_ws["submits"])

        await prefs(True, [])
        allowed = await call()
        assert mock_ws["submits"], allowed
        model, payload = mock_ws["submits"][-1]
        assert model == QWEN
        assert payload.get("size") == "1584*396" and "size_lock" not in payload
        assert len(mock_ws["submits"]) == 1
        assert all(item[0] != FLARE for item in mock_ws["submits"])
        await page.locator(".tl-image img, img.tl-image").first.wait_for(timeout=25000)
        natural = await page.evaluate(
            """async () => {
              const img = document.querySelector('.tl-image img, img.tl-image')
              await img.decode()
              return [img.naturalWidth, img.naturalHeight]
            }"""
        )
        assert natural == [1584, 396]
        await browser.close()
