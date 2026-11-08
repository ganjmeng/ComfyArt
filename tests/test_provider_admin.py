"""Per-tool routes and fallback. No live paid calls."""
from __future__ import annotations

import asyncio
import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ComfyArt.api import provider_admin, replicate_image
from ComfyArt.api.provider_catalog import audit_rows, render_audit_markdown
from ComfyArt.api.tool_routing import RouteFailure, tool_of

TOKEN = "r8_test_not_a_real_token"
FLARE = "openai/gpt-image-2.6-flare"
SUNBURST = "openai/gpt-image-2.6-sunburst"


@pytest.fixture
async def client():
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    c = TestClient(TestServer(app))
    await c.start_server()
    yield c
    await c.close()


def _route(model=FLARE, backup=None, fallback=False, activate=True):
    body = {"primary": {"provider": "replicate", "model": model}, "fallback": fallback, "activate": activate}
    if backup:
        body["backup"] = {"provider": "replicate", "model": backup}
    return body


async def test_tools_default_and_admin_gate(client, monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    denied = await client.get("/comfyart/provider-admin", headers={"comfy-user": "alice"})
    assert denied.status == 403
    body = await (await client.get("/comfyart/provider-admin")).json()
    assert TOKEN not in json.dumps(body)
    ids = {row["id"] for row in body["tools"]}
    assert {"generate_image", "edit_image", "to_gif", "generate_video", "text_to_speech"} <= ids
    assert all(row["effective"]["source"] == "default" for row in body["tools"])
    assert body["policy"]["fallback_default"] is False


async def test_missing_key_does_not_activate(client, monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    res = await client.put("/comfyart/provider-admin/tool/edit_image", json=_route())
    assert res.status == 409 and (await res.json())["activated"] is False
    assert provider_admin._tool_record("edit_image")["active"] is None
    draft = await client.put("/comfyart/provider-admin/tool/edit_image", json=_route(activate=False))
    assert draft.status == 200 and (await draft.json())["activated"] is False
    assert provider_admin._tool_record("edit_image")["active"] is None


async def test_tool_coexistence_and_restore(monkeypatch):
    calls = {"orig": []}

    async def orig(inputs):
        calls["orig"].append(inputs.get("tool") or inputs.get("feature"))
        return "wave"

    async def post(url, body, token):
        return "pred_edit"

    async def priced(model, cap, inputs):
        return 1, "quote"

    monkeypatch.setattr(provider_admin, "_image_orig", orig)
    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setattr(provider_admin, "_quote_override", priced)
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._write_tool("edit_image", {"revision": 1, "active": {"primary": {"provider": "replicate", "model": FLARE}, "backup": None, "fallback": False}, "previous": None})
    import ComfyArt.api.wavespeed as wavespeed
    assert await wavespeed.submit({"tool": "generate_image", "feature": "text_to_image", "prompt": "a"}) == "wave"
    assert await wavespeed.submit({"tool": "upscale_image", "feature": "upscale_image", "image": "https://cdn.example/a.png"}) == "wave"
    assert await wavespeed.submit({"tool": "edit_image", "feature": "image_edit", "prompt": "blue", "image": "https://cdn.example/a.png"}) == "pred_edit"
    assert calls["orig"] == ["generate_image", "upscale_image"]
    provider_admin._write_tool("edit_image", {"revision": 2, "active": None, "previous": {"primary": {"provider": "replicate", "model": FLARE}, "backup": None, "fallback": False}})
    assert await wavespeed.submit({"tool": "edit_image", "feature": "image_edit", "prompt": "blue", "image": "https://cdn.example/a.png"}) == "wave"


def test_tool_identity_matches_the_product_actions():
    assert tool_of({"feature": "text_to_image", "prompt": "x"}) == "generate_image"
    assert tool_of({"feature": "text_to_image", "prompt": "x", "image": "https://cdn.example/a.png", "params": {"output_format": "gif"}}) == "to_gif"
    assert tool_of({"feature": "image_edit", "custom": "edit", "prompt": "make it blue", "image": "x"}) == "edit_image"
    assert tool_of({"feature": "image_edit", "custom": "edit", "prompt": 'Change the text "a" to "b"', "image": "x"}) == "replace_text"
    assert tool_of({"feature": "image_edit", "custom": "style", "prompt": "x", "image": "x"}) == "style_transfer"
    assert tool_of({"feature": "image_to_video", "custom": "animate", "image": "x"}) == "animate_image"
    assert tool_of({"tool": "generate_video", "feature": "image_edit"}) == "generate_video"


def test_replicate_payload_keeps_references_and_has_no_price():
    ref = replicate_image.build_input("reference_gif", {"prompt": "animate", "image": "https://cdn.example/still.png", "params": {"frame_count": 2, "frame_duration_ms": 200}})
    assert ref["input_images"] == ["https://cdn.example/still.png"] and ref["output_format"] == "gif" and ref["frame_count"] == 2
    assert "input_images" not in replicate_image.build_input("text_to_image", {"prompt": "x"})
    with pytest.raises(replicate_image.PayloadError):
        replicate_image.build_input("reference_gif", {"prompt": "animate"})


async def _arm(monkeypatch, primary, quotes):
    posts = []

    async def post(url, body, token):
        posts.append(url)
        if FLARE.split("/")[-1] in url:
            result = primary()
            if isinstance(result, Exception):
                raise result
            return result
        return "pred_backup"

    async def priced(model, cap, inputs):
        price, source = quotes(model)
        return price, source

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setattr(provider_admin, "_quote_override", priced)
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._runs.clear()
    provider_admin._write_tool("edit_image", {
        "revision": 1,
        "active": {
            "primary": {"provider": "replicate", "model": FLARE},
            "backup": {"provider": "replicate", "model": SUNBURST},
            "fallback": True,
        },
        "previous": None,
    })
    return posts


async def test_not_accepted_falls_back_once(monkeypatch):
    posts = await _arm(monkeypatch, lambda: RouteFailure("not_accepted", "no task"), lambda model: (1, "quote"))
    import ComfyArt.api.wavespeed as wavespeed
    task = await wavespeed.submit({"tool": "edit_image", "feature": "image_edit", "prompt": "blue", "image": "https://cdn.example/a.png"})
    assert task == "pred_backup" and len(posts) == 2
    assert provider_admin._audit[-1]["fallback_used"] is True


async def test_accepted_timeout_safety_and_price_do_not_switch(monkeypatch):
    import ComfyArt.api.wavespeed as wavespeed
    from ComfyArt.api.wavespeed import WaveSpeedError
    job = {"tool": "edit_image", "feature": "image_edit", "image": "https://cdn.example/a.png"}

    posts = await _arm(monkeypatch, lambda: RouteFailure("accepted", "has id", task_id="pred_live"), lambda model: (1, "quote"))
    assert await wavespeed.submit({**job, "prompt": "a"}) == "pred_live"
    assert len(posts) == 1

    posts = await _arm(monkeypatch, lambda: TimeoutError(), lambda model: (1, "quote"))
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({**job, "prompt": "b"})
    assert caught.value.kind == "unknown" and len(posts) == 1

    posts = await _arm(monkeypatch, lambda: RouteFailure("safety", "blocked"), lambda model: (1, "quote"))
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({**job, "prompt": "c"})
    assert caught.value.kind == "safety" and len(posts) == 1

    posts = await _arm(monkeypatch, lambda: RouteFailure("not_accepted", "no task"), lambda model: (5, "quote") if model == SUNBURST else (1, "quote"))
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({**job, "prompt": "d"})
    assert caught.value.kind == "price" and len(posts) == 1


async def test_unknown_price_and_incompatible_backup_do_not_switch(monkeypatch):
    import ComfyArt.api.wavespeed as wavespeed
    from ComfyArt.api.wavespeed import WaveSpeedError
    posts = await _arm(monkeypatch, lambda: RouteFailure("not_accepted", "no task"), lambda model: (None, "unknown"))
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({"tool": "edit_image", "feature": "image_edit", "prompt": "e", "image": "https://cdn.example/a.png"})
    assert caught.value.kind == "price" and posts == []

    provider_admin._runs.clear()
    provider_admin._write_tool("to_gif", {
        "revision": 1,
        "active": {"primary": {"provider": "replicate", "model": FLARE}, "backup": {"provider": "wavespeed", "model": "existing"}, "fallback": True},
        "previous": None,
    })
    seen = []

    async def post(url, body, token):
        seen.append(url)
        raise RouteFailure("not_accepted", "no task")

    async def priced(model, cap, inputs):
        return 1, "quote"

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setattr(provider_admin, "_quote_override", priced)
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({"tool": "to_gif", "feature": "text_to_image", "prompt": "loop", "image": "https://cdn.example/a.png", "params": {"output_format": "gif"}})
    assert caught.value.kind == "incompatible" and len(seen) == 1


async def test_concurrent_submit_is_idempotent(monkeypatch):
    gate = asyncio.Event()
    entered = asyncio.Event()
    posts = []

    async def post(url, body, token):
        posts.append(url)
        entered.set()
        await gate.wait()
        return "pred_once"

    async def priced(model, cap, inputs):
        return 1, "quote"

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setattr(provider_admin, "_quote_override", priced)
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._write_tool("generate_image", {"revision": 1, "active": {"primary": {"provider": "replicate", "model": FLARE}, "backup": None, "fallback": False}, "previous": None})
    import ComfyArt.api.wavespeed as wavespeed
    job = {"tool": "generate_image", "feature": "text_to_image", "prompt": "same"}
    first = asyncio.create_task(wavespeed.submit(dict(job)))
    await entered.wait()
    second = asyncio.create_task(wavespeed.submit(dict(job)))
    await asyncio.sleep(0.05)
    gate.set()
    assert await first == await second == "pred_once"
    assert len(posts) == 1


async def test_llm_check_does_not_save_or_call(client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    before = provider_admin.active_llm()
    res = await client.post("/comfyart/provider-admin/llm/check", json={"provider": "deepseek", "model": "deepseek-flash"})
    body = await res.json()
    assert res.status == 200 and body["calls"] == 0 and body["saved"] is False
    assert body["quote"] == "unknown" and body["base_url"] == "https://api.deepseek.com"
    assert "不是无差异" in body["message"]
    assert provider_admin.active_llm() == before


def test_audit_keeps_unverified_distinct_from_unsupported():
    rows = audit_rows()
    enabled = [row for row in rows if row["enabled"]]
    assert {row["verdict"] for row in enabled} == {"connected"}
    assert {row["replicate_model"] for row in enabled} <= {FLARE, SUNBURST}
    assert any(row["verdict"] == "same_model_pending" and not row["enabled"] for row in rows)
    assert any(row["verdict"] == "alternative_explicit" and "video" in row["feature"] and not row["enabled"] for row in rows)
    assert any(row["verdict"] == "unverified" for row in rows)
    text = render_audit_markdown()
    assert "未核实" in text and "完全兼容" not in text


async def test_batch_skips_unconnected_tools(client, monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    res = await client.put("/comfyart/provider-admin/tools/batch", json={
        "ids": ["edit_image", "generate_video"],
        "primary": {"provider": "replicate", "model": FLARE},
        "backup": None,
        "fallback": False,
    })
    body = await res.json()
    assert res.status == 200 and body["applied"] == ["edit_image"] and "generate_video" in body["skipped"]
    assert body["usable"] is False and body["blocked"] == "quote_unknown"
    video = next(row for row in body["tools"] if row["id"] == "generate_video")
    edit = next(row for row in body["tools"] if row["id"] == "edit_image")
    assert video["effective"]["source"] == "default"
    assert edit["effective"]["provider"] == "replicate" and edit["usable"] is False


async def test_svg_stays_on_the_original_route_and_gif_backup_is_rejected(client, monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    saved = await client.put("/comfyart/provider-admin/tool/generate_image", json={
        "primary": {"provider": "replicate", "model": FLARE}, "backup": None, "fallback": False, "activate": True,
    })
    assert saved.status == 200
    seen = []

    async def original(inputs):
        seen.append("svg")
        return "orig"

    assert await provider_admin.dispatch_submit(
        {"feature": "text_to_image", "prompt": "mark", "params": {"output_format": "svg"}}, original,
    ) == "orig"
    assert seen == ["svg"]
    rejected = await client.put("/comfyart/provider-admin/tool/to_gif", json={
        "primary": {"provider": "replicate", "model": FLARE},
        "backup": {"provider": "wavespeed", "model": "existing"},
        "fallback": True,
    })
    assert rejected.status == 400
