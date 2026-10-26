"""#33 PR2: mock happy (+ one error each where feasible) for local canvas tools
that lack dedicated mocks.

Drives the real MCP relay (`/comfyart/mcp` → page command → `/comfyart/mcp_command_result`)
with a stub page, same pattern as `tests/test_mcp.py`. Result shapes mirror
`src/botLayout.ts` / `src/botCommands.ts` and the agent-regression FakePage.

$0 only: no Playwright, no WaveSpeed, no paid submit.
"""
from __future__ import annotations

import asyncio
import json

from conftest import SENT
from server import PromptServer


async def _open(client, project="p", tab="tab-1"):
    PromptServer.instance.sockets[tab] = object()
    await client.post("/comfyart/mcp_page", json={"client_id": tab, "project": project})


def _rpc(method, params=None, rid=1):
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}


async def _answer_commands(client, reply):
    for _ in range(200):
        commands = [d for e, d in SENT if e == "comfyart-mcp-command"]
        if commands:
            SENT.clear()
            for c in commands:
                await client.post("/comfyart/mcp_command_result", json={"command_id": c["id"], **reply(c)})
            return commands
        await asyncio.sleep(0.01)
    raise AssertionError("no command was sent")


async def _call(client, name: str, args: dict):
    return asyncio.create_task(
        client.post("/comfyart/mcp", json=_rpc("tools/call", {"name": name, "arguments": args}))
    )


def _text(data: dict) -> str:
    return data["result"]["content"][0]["text"]


def _payload(data: dict) -> dict:
    return json.loads(_text(data))


# --- vectorize_image ---------------------------------------------------------------------------------

async def test_vectorize_image_happy(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "vectorize_image", {"id": "shape:img1"})
    commands = await _answer_commands(
        bot_client, lambda c: {"ok": True, "result": {"id": "shape:svg1"}}
    )
    data = await (await call).json()
    assert commands[0]["action"] == "vectorize_image"
    assert commands[0]["args"] == {"id": "shape:img1"}
    assert data["result"]["isError"] is False
    assert _payload(data) == {"id": "shape:svg1"}


async def test_vectorize_image_error_not_an_image(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "vectorize_image", {"id": "shape:txt1"})
    await _answer_commands(
        bot_client, lambda c: {"ok": False, "error": "shape:txt1 is not an image"}
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "not an image" in _text(data)


# --- place_design ------------------------------------------------------------------------------------

async def test_place_design_happy(bot_client):
    await _open(bot_client)
    args = {"id": "shape:mock1", "design": "shape:logo", "x": 0.5, "y": 0.4, "scale": 0.6}
    call = await _call(bot_client, "place_design", args)
    commands = await _answer_commands(
        bot_client, lambda c: {"ok": True, "result": {"updated": "shape:mock1"}}
    )
    data = await (await call).json()
    assert commands[0]["action"] == "place_design"
    assert commands[0]["args"]["id"] == "shape:mock1"
    assert commands[0]["args"]["design"] == "shape:logo"
    assert data["result"]["isError"] is False
    assert _payload(data) == {"updated": "shape:mock1"}


async def test_place_design_error_not_a_mockup(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "place_design", {"id": "shape:img1"})
    await _answer_commands(
        bot_client,
        lambda c: {"ok": False, "error": "shape:img1 is not a mockup — make one with create_mockup"},
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "not a mockup" in _text(data)


# --- place_html --------------------------------------------------------------------------------------

async def test_place_html_happy(bot_client):
    await _open(bot_client)
    html = "<!doctype html><html><body><h1>Hi</h1></body></html>"
    call = await _call(bot_client, "place_html", {"html": html, "name": "Landing", "width": 800, "height": 600})
    commands = await _answer_commands(
        bot_client, lambda c: {"ok": True, "result": {"id": "shape:html1"}}
    )
    data = await (await call).json()
    assert commands[0]["action"] == "place_html"
    assert commands[0]["args"]["html"] == html
    assert data["result"]["isError"] is False
    assert _payload(data) == {"id": "shape:html1"}


async def test_place_html_error_bad_html(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "place_html", {"html": ""})
    await _answer_commands(
        bot_client, lambda c: {"ok": False, "error": "html must be a complete document"}
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "html" in _text(data).lower()


# --- create_slides -----------------------------------------------------------------------------------

async def test_create_slides_happy_local_frames(bot_client):
    """Slides without image prompts stay local (frames + text only); page mock returns frames."""
    await _open(bot_client)
    slides = {
        "title": "Product",
        "slides": [
            {"title": "Intro", "bullets": ["a", "b"]},
            {"title": "Next", "bullets": ["c"]},
        ],
    }
    call = await _call(bot_client, "create_slides", slides)
    commands = await _answer_commands(
        bot_client,
        lambda c: {
            "ok": True,
            "result": {"frames": ["shape:f1", "shape:f2"], "ids": []},
        },
    )
    data = await (await call).json()
    assert commands[0]["action"] == "create_slides"
    assert commands[0]["args"]["title"] == "Product"
    assert len(commands[0]["args"]["slides"]) == 2
    assert data["result"]["isError"] is False
    assert _payload(data)["frames"] == ["shape:f1", "shape:f2"]
    assert _payload(data)["ids"] == []


async def test_create_slides_error_empty_slides(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "create_slides", {"title": "Empty", "slides": []})
    await _answer_commands(
        bot_client, lambda c: {"ok": False, "error": "slides must be a non-empty array"}
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "non-empty" in _text(data)


# --- add_text / add_shape / create_frame -------------------------------------------------------------

async def test_add_text_happy(bot_client):
    await _open(bot_client)
    args = {"text": "BIG SALE", "font": "Inter", "color": "#FF5A1F", "font_size": 96}
    call = await _call(bot_client, "add_text", args)
    commands = await _answer_commands(
        bot_client, lambda c: {"ok": True, "result": {"id": "shape:t1"}}
    )
    data = await (await call).json()
    assert commands[0]["action"] == "add_text"
    assert commands[0]["args"]["text"] == "BIG SALE"
    assert data["result"]["isError"] is False
    assert _payload(data) == {"id": "shape:t1"}


async def test_add_text_error_missing_frame(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "add_text", {"text": "x", "frame": "shape:missing"})
    await _answer_commands(
        bot_client, lambda c: {"ok": False, "error": "no shape shape:missing"}
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "no shape" in _text(data)


async def test_add_shape_happy(bot_client):
    await _open(bot_client)
    args = {"kind": "rect", "width": 200, "height": 100, "fill": "#112233"}
    call = await _call(bot_client, "add_shape", args)
    commands = await _answer_commands(
        bot_client, lambda c: {"ok": True, "result": {"id": "shape:v1"}}
    )
    data = await (await call).json()
    assert commands[0]["action"] == "add_shape"
    assert commands[0]["args"]["kind"] == "rect"
    assert data["result"]["isError"] is False
    assert _payload(data) == {"id": "shape:v1"}


async def test_add_shape_error_bad_kind(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "add_shape", {"kind": "triangle"})
    await _answer_commands(
        bot_client,
        lambda c: {"ok": False, "error": "kind must be one of rect, ellipse, polygon, star"},
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "kind must be" in _text(data)


async def test_create_frame_happy(bot_client):
    await _open(bot_client)
    args = {"name": "Board", "width": 1280, "height": 720, "children": ["shape:t1"]}
    call = await _call(bot_client, "create_frame", args)
    commands = await _answer_commands(
        bot_client, lambda c: {"ok": True, "result": {"id": "shape:fr1"}}
    )
    data = await (await call).json()
    assert commands[0]["action"] == "create_frame"
    assert commands[0]["args"]["width"] == 1280
    assert commands[0]["args"]["children"] == ["shape:t1"]
    assert data["result"]["isError"] is False
    assert _payload(data) == {"id": "shape:fr1"}


async def test_create_frame_error_missing_child(bot_client):
    await _open(bot_client)
    call = await _call(
        bot_client, "create_frame", {"width": 100, "height": 100, "children": ["shape:gone"]}
    )
    await _answer_commands(
        bot_client, lambda c: {"ok": False, "error": "no shape shape:gone"}
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "no shape" in _text(data)


# --- update_shapes / delete_shapes -------------------------------------------------------------------

async def test_update_shapes_happy(bot_client):
    await _open(bot_client)
    args = {"updates": [{"id": "shape:t1", "text": "SALE", "color": "#FF0000"}]}
    call = await _call(bot_client, "update_shapes", args)
    commands = await _answer_commands(
        bot_client, lambda c: {"ok": True, "result": {"updated": ["shape:t1"]}}
    )
    data = await (await call).json()
    assert commands[0]["action"] == "update_shapes"
    assert commands[0]["args"]["updates"][0]["text"] == "SALE"
    assert data["result"]["isError"] is False
    assert _payload(data) == {"updated": ["shape:t1"]}


async def test_update_shapes_error_not_array(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "update_shapes", {"updates": "bad"})
    await _answer_commands(
        bot_client, lambda c: {"ok": False, "error": "updates must be an array"}
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "updates must be an array" in _text(data)


async def test_delete_shapes_happy(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "delete_shapes", {"ids": ["shape:a", "shape:b"]})
    commands = await _answer_commands(
        bot_client, lambda c: {"ok": True, "result": {"deleted": ["shape:a", "shape:b"]}}
    )
    data = await (await call).json()
    assert commands[0]["action"] == "delete_shapes"
    assert commands[0]["args"]["ids"] == ["shape:a", "shape:b"]
    assert data["result"]["isError"] is False
    assert _payload(data) == {"deleted": ["shape:a", "shape:b"]}


async def test_delete_shapes_error_missing(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "delete_shapes", {"ids": ["shape:missing"]})
    await _answer_commands(
        bot_client, lambda c: {"ok": False, "error": "no shape shape:missing"}
    )
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "no shape" in _text(data)


# --- focus (happy; error already in test_mcp.py) -----------------------------------------------------

async def test_focus_happy(bot_client):
    await _open(bot_client)
    call = await _call(bot_client, "focus", {"ids": ["shape:t1", "shape:v1"]})
    commands = await _answer_commands(
        bot_client,
        lambda c: {"ok": True, "result": {"selected": ["shape:t1", "shape:v1"]}},
    )
    data = await (await call).json()
    assert commands[0]["action"] == "focus"
    assert commands[0]["args"]["ids"] == ["shape:t1", "shape:v1"]
    assert data["result"]["isError"] is False
    assert _payload(data) == {"selected": ["shape:t1", "shape:v1"]}


async def test_focus_error_missing_shape(bot_client):
    """Error path also covered in test_mcp.py; kept here so the tool has a dedicated pair."""
    await _open(bot_client)
    call = await _call(bot_client, "focus", {"ids": ["shape:x"]})
    await _answer_commands(bot_client, lambda c: {"ok": False, "error": "no shape shape:x"})
    data = await (await call).json()
    assert data["result"]["isError"] is True
    assert "no shape" in _text(data)
