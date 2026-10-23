"""#166 (#33): project new -> edit -> save -> reopen full flow, mocks only (local sqlite in tmp, no network, $0).
Creates a project through the real /comfyart/projects routes with a tldraw-shaped snapshot that carries canvas
content (frame, generator card with its settings, text, image + asset) and document/page settings, saves edits, then
reopens it after dropping the DB engine (a server restart) and checks nothing was lost."""
from __future__ import annotations

import copy

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ComfyArt.api import db

PID = "flow0166"


def _doc(name: str) -> dict:
    return {
        "document:document": {"id": "document:document", "typeName": "document", "name": name, "gridSize": 10,
                              "meta": {"lang": "zh", "background": "#F5F5F0"}},
        "page:page": {"id": "page:page", "typeName": "page", "name": "画布 1", "index": "a1", "meta": {}},
    }


def _snapshot(name: str) -> dict:
    return {"document": {"store": _doc(name), "schema": {"schemaVersion": 2, "sequences": {"com.tldraw.store": 4}}},
            "session": {"version": 0, "currentPageId": "page:page", "isGridMode": True, "isFocusMode": False,
                        "pageStates": [{"pageId": "page:page", "camera": {"x": -120, "y": 40, "z": 0.75}, "selectedShapeIds": []}]}}


def _shape(sid: str, typ: str, props: dict, parent: str = "page:page", y: float = 0) -> dict:
    return {"id": sid, "typeName": "shape", "type": typ, "parentId": parent, "index": "a1", "x": 0, "y": y,
            "rotation": 0, "isLocked": False, "opacity": 1, "meta": {}, "props": props}


GEN_SETTINGS = {"w": 400, "h": 260, "prompt": "一只橘猫坐在窗台，晨光", "ratio": "16:9", "resolution": "1080p", "count": 2,
                "workflow": "text_to_image", "duration": 5, "transparent": False, "quality": "high", "style": "film",
                "cw": 1920, "ch": 1080}


async def _client():
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


def _restart_db():
    for engine in db._engines.values():
        engine.dispose()
    db._engines.clear()


async def test_new_edit_save_reopen_keeps_content_and_settings(bot_client):
    # new: empty project, as the page creates it
    created = await bot_client.put(f"/comfyart/projects/{PID}", json={"snapshot": _snapshot("未命名"), "name": "未命名", "covers": []})
    assert created.status == 200
    assert PID in [p["id"] for p in (await (await bot_client.get("/comfyart/projects")).json())["projects"]]

    # edit: add content and change settings, then save
    snap = await (await bot_client.get(f"/comfyart/projects/{PID}")).json()
    store = snap["document"]["store"]
    store["document:document"].update(name="海报 Poster", gridSize=20)
    store["document:document"]["meta"]["background"] = "#101010"
    store["shape:frame1"] = _shape("shape:frame1", "frame", {"w": 1080, "h": 1350, "name": "封面 Cover"})
    store["shape:gen1"] = _shape("shape:gen1", "generator", GEN_SETTINGS, parent="shape:frame1", y=40)
    store["shape:gen1"]["meta"] = {"model": "wavespeed-ai/flux-dev", "seed": 42}
    store["shape:text1"] = _shape("shape:text1", "ca-text", {"text": "限时 5 折 🎉", "size": "l", "color": "red"}, y=600)
    store["asset:img1"] = {"id": "asset:img1", "typeName": "asset", "type": "image", "meta": {},
                           "props": {"src": "/api/view?filename=cat.png&type=output", "w": 1024, "h": 1024, "name": "cat.png",
                                     "mimeType": "image/png", "isAnimated": False}}
    store["shape:img1"] = _shape("shape:img1", "image", {"assetId": "asset:img1", "w": 512, "h": 512}, parent="shape:frame1", y=400)
    snap["session"]["pageStates"][0]["camera"] = {"x": 10, "y": -20, "z": 1.5}
    covers = ["/api/view?filename=cat.png&type=output"]
    saved = await (await bot_client.put(f"/comfyart/projects/{PID}", json={"snapshot": snap, "name": "海报 Poster", "covers": covers})).json()
    assert saved["name"] == "海报 Poster" and saved["covers"] == covers
    expected = copy.deepcopy(snap)

    # reopen after a restart: fresh DB engine, fresh HTTP client
    _restart_db()
    client = await _client()
    try:
        listed = (await (await client.get("/comfyart/projects")).json())["projects"]
        entry = next(p for p in listed if p["id"] == PID)
        assert entry["name"] == "海报 Poster" and entry["covers"] == covers
        reopened = await (await client.get(f"/comfyart/projects/{PID}")).json()
    finally:
        await client.close()
    assert reopened == expected  # whole snapshot, byte-for-byte equal as JSON
    rs = reopened["document"]["store"]
    assert rs["shape:gen1"]["props"] == GEN_SETTINGS and rs["shape:gen1"]["meta"] == {"model": "wavespeed-ai/flux-dev", "seed": 42}
    assert rs["document:document"]["gridSize"] == 20 and rs["document:document"]["meta"] == {"lang": "zh", "background": "#101010"}
    assert rs["shape:text1"]["props"]["text"] == "限时 5 折 🎉" and rs["shape:img1"]["parentId"] == "shape:frame1"
    assert reopened["session"]["pageStates"][0]["camera"] == {"x": 10, "y": -20, "z": 1.5}
    assert sorted(k for k in rs if k.startswith("shape:")) == ["shape:frame1", "shape:gen1", "shape:img1", "shape:text1"]


async def test_second_save_replaces_and_does_not_mix_projects(bot_client):
    await bot_client.put("/comfyart/projects/a0166", json={"snapshot": _snapshot("A"), "name": "A", "covers": []})
    b = _snapshot("B")
    b["document"]["store"]["shape:t"] = _shape("shape:t", "ca-text", {"text": "B only"})
    await bot_client.put("/comfyart/projects/b0166", json={"snapshot": b, "name": "B", "covers": []})
    a2 = _snapshot("A2")
    a2["document"]["store"]["shape:x"] = _shape("shape:x", "frame", {"w": 1, "h": 1, "name": "x"})
    await bot_client.put("/comfyart/projects/a0166", json={"snapshot": a2, "name": "A2", "covers": []})
    _restart_db()
    assert await (await bot_client.get("/comfyart/projects/a0166")).json() == a2
    assert await (await bot_client.get("/comfyart/projects/b0166")).json() == b


@pytest.mark.parametrize("bad", [{"name": "x"}, {"snapshot": "not an object", "name": "x"}, {"snapshot": {}, "covers": "nope"}])
async def test_bad_save_keeps_previous_copy(bot_client, bad):
    good = _snapshot("Keep")
    await bot_client.put("/comfyart/projects/k0166", json={"snapshot": good, "name": "Keep", "covers": []})
    assert (await bot_client.put("/comfyart/projects/k0166", json=bad)).status == 400
    assert await (await bot_client.get("/comfyart/projects/k0166")).json() == good
