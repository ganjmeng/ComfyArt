"""WaveSpeed API key settings (#11) against a mock /balance server; fake keys only, no real API calls."""
from __future__ import annotations

import os
import stat

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from ComfyArt.api import wavespeed

GOOD = "ws-fake-good-key-1234"
EMPTY = "ws-fake-empty-key-0000"
ENVKEY = "ws-fake-env-key-9876"


@pytest.fixture
async def mock(monkeypatch, fresh_user_dir):
    state = {"down": False, "calls": 0}

    async def balance(request):
        state["calls"] += 1
        auth = request.headers.get("Authorization", "")
        if auth == f"Bearer {GOOD}":
            return web.json_response({"code": 200, "message": "success", "data": {"balance": 12.5}})
        if auth in (f"Bearer {EMPTY}", f"Bearer {ENVKEY}"):
            return web.json_response({"code": 200, "message": "success", "data": {"balance": 0}})
        return web.json_response({"code": 401, "message": "Unauthorized"}, status=401)

    app = web.Application()
    app.router.add_get("/api/v3/balance", balance)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.delenv("WAVESPEED_API_KEY", raising=False)
    yield state
    await server.close()


@pytest.fixture
async def client(mock):
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    c = TestClient(TestServer(app))
    await c.start_server()
    yield c
    await c.close()


async def test_unconfigured(client):
    body = await (await client.get("/comfyart/wavespeed/key")).json()
    assert body == {"configured": False, "source": "none", "last4": "", "balance": None}


async def test_save_valid_key_masks_and_stores_0600(client):
    res = await client.put("/comfyart/wavespeed/key", json={"key": GOOD})
    text = await res.text()
    assert res.status == 200 and GOOD not in text
    body = await (await client.get("/comfyart/wavespeed/key")).json()
    assert body == {"configured": True, "source": "settings", "last4": "1234", "balance": 12.5}
    path = wavespeed._key_path()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert wavespeed._key() == GOOD


async def test_invalid_key_not_saved(client):
    res = await client.put("/comfyart/wavespeed/key", json={"key": "ws-wrong-key-abcd"})
    assert res.status == 401 and (await res.json())["error"]["reason"] == "invalid"
    assert not os.path.exists(wavespeed._key_path())


async def test_network_failure_not_saved(client, monkeypatch):
    monkeypatch.setenv("WAVESPEED_BASE_URL", "http://127.0.0.1:9")
    res = await client.put("/comfyart/wavespeed/key", json={"key": GOOD})
    assert res.status == 503 and (await res.json())["error"]["reason"] == "network"
    assert not os.path.exists(wavespeed._key_path())


async def test_zero_balance_is_saved(client):
    res = await client.put("/comfyart/wavespeed/key", json={"key": EMPTY})
    assert res.status == 200 and (await res.json())["balance"] == 0


async def test_env_wins_and_is_read_only(client, monkeypatch):
    await client.put("/comfyart/wavespeed/key", json={"key": GOOD})
    monkeypatch.setenv("WAVESPEED_API_KEY", ENVKEY)
    body = await (await client.get("/comfyart/wavespeed/key")).json()
    assert body["source"] == "env" and body["last4"] == "9876" and body["balance"] == 0
    assert wavespeed._key() == ENVKEY
    assert (await client.put("/comfyart/wavespeed/key", json={"key": GOOD})).status == 409


async def test_delete_key(client):
    await client.put("/comfyart/wavespeed/key", json={"key": GOOD})
    body = await (await client.delete("/comfyart/wavespeed/key")).json()
    assert body["configured"] is False and not os.path.exists(wavespeed._key_path())


async def test_saved_key_invalid_later_reports_reason(client, monkeypatch):
    wavespeed._save_key("ws-revoked-key-zzzz")
    body = await (await client.get("/comfyart/wavespeed/key")).json()
    assert body["configured"] is True and body["error"] == "invalid" and body["balance"] is None
