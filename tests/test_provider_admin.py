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


async def test_to_gif_primary_bans_wavespeed(client, monkeypatch):
    """Still→GIF live default is Replicate·Flare; WaveSpeed cannot be the primary pick."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    body = await (await client.get("/comfyart/provider-admin")).json()
    row = next(t for t in body["tools"] if t["id"] == "to_gif")
    assert row["effective"]["provider"] == "replicate"
    assert row["effective"]["model"] == FLARE
    assert row["gif_default"]["provider"] == "replicate"
    ws = next(c for c in row["choices"] if c["provider"] == "wavespeed")
    assert ws["enabled"] is False
    assert ws["backup"] is False
    assert "WaveSpeed" in ws["backup_reason"] or "备选" in ws["backup_reason"]
    flare = next(c for c in row["choices"] if c["model"] == FLARE)
    assert flare["enabled"] is True
    bad = await client.put("/comfyart/provider-admin/tool/to_gif", json={
        "primary": {"provider": "wavespeed", "model": "existing"}, "backup": None, "fallback": False, "activate": True,
    })
    assert bad.status in {400, 409, 422}
    assert provider_admin._tool_record("to_gif")["active"] is None



async def test_generate_image_keeps_gif_default_but_effective_is_wavespeed(client, monkeypatch):
    """UI must follow effective (WaveSpeed) for generate_image Primary; gif_default is GIF-path hint only."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    body = await (await client.get("/comfyart/provider-admin")).json()
    row = next(t for t in body["tools"] if t["id"] == "generate_image")
    assert row["active"] is None
    assert row["effective"]["provider"] == "wavespeed"
    assert row["gif_default"]["provider"] == "replicate"
    to_gif = next(t for t in body["tools"] if t["id"] == "to_gif")
    assert to_gif["effective"]["provider"] == "replicate"
    assert to_gif["gif_default"]["provider"] == "replicate"

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
    job = {"tool": "edit_image", "feature": "image_edit", "prompt": "e", "image": "https://cdn.example/a.png"}
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit(job)
    token = caught.value.confirm_token
    assert caught.value.status == 409 and caught.value.unpriced and token and posts == []
    provider_admin._runs.clear()
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({**job, "confirmed": True, "confirm_token": token})
    assert len(posts) == 1 and caught.value.kind == "price"
    posts.clear()
    provider_admin._runs.clear()
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({**job, "confirm_token": token})
    assert posts == [] and caught.value.unpriced
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({**job, "prompt": "e-bypass", "confirmed": True})
    assert posts == [] and caught.value.confirm_token
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({**job, "prompt": "e-bypass", "confirmed": True})
    assert posts == []
    estimate = await provider_admin.dispatch_estimate(job, lambda inputs: {"price": 9, "source": "quote"})
    assert estimate["price"] is None and estimate["source"] == "unpriced" and estimate["confirm"] is True
    assert "0.030405" not in json.dumps(estimate)

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
    # Product rule: still+GIF never reaches a provider POST, so WaveSpeed cannot be a backup for it.
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({"tool": "to_gif", "feature": "text_to_image", "prompt": "loop", "image": "https://cdn.example/a.png", "params": {"output_format": "gif"}})
    assert caught.value.kind == "gifStillUnsupported" and len(seen) == 0


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
    assert body["usable"] is False and body["blocked"] == "needs_user_confirm"
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


async def test_confirm_token_is_bound_single_use_and_durable(client, monkeypatch):
    import os
    import threading
    import ComfyArt.api.wavespeed as wavespeed
    from ComfyArt.api.wavespeed import WaveSpeedError
    posts = []

    async def post(url, body, token):
        posts.append(url)
        return "pred_once"

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    saved = await client.put("/comfyart/provider-admin/tool/edit_image", json=_route())
    assert saved.status == 200
    saved_body = await saved.json()
    revision = next(row["revision"] for row in saved_body["tools"] if row["id"] == "edit_image")
    job = {"tool": "edit_image", "feature": "image_edit", "prompt": "bound", "image": "https://cdn.example/a.png", "params": {"quality": "low"}}
    first = await client.post("/comfyart/wavespeed/run", json={"inputs": job})
    body = await first.json()
    token = body["error"]["confirm_token"]
    assert first.status == 409 and body["error"]["unpriced"] is True and "封顶价" in body["error"]["message"] and posts == []
    assert "0.03" not in json.dumps(body)
    mode = os.stat(provider_admin._confirm_path()).st_mode & 0o777
    assert mode == 0o600

    other = await client.post("/comfyart/wavespeed/run", json={"inputs": {**job, "confirm_token": token}}, headers={"comfy-user": "alice"})
    assert other.status == 409 and posts == []
    changed = await client.post("/comfyart/wavespeed/run", json={"inputs": {**job, "confirm_token": token, "params": {"quality": "max"}}})
    assert changed.status == 409 and posts == []
    provider_admin._write_tool("edit_image", {
        "revision": revision + 5,
        "active": {"primary": {"provider": "replicate", "model": FLARE}, "backup": None, "fallback": False},
        "previous": None,
    })
    stale = await client.post("/comfyart/wavespeed/run", json={"inputs": {**job, "confirm_token": token}})
    assert stale.status == 409 and posts == []
    provider_admin._write_tool("edit_image", {
        "revision": revision,
        "active": {"primary": {"provider": "replicate", "model": FLARE}, "backup": None, "fallback": False},
        "previous": None,
    })
    ok = await client.post("/comfyart/wavespeed/run", json={"inputs": {**job, "confirm_token": token}})
    assert ok.status == 200 and len(posts) == 1
    provider_admin._runs.clear()
    replay = await client.post("/comfyart/wavespeed/run", json={"inputs": {**job, "confirm_token": token}})
    assert replay.status == 409 and len(posts) == 1

    fresh = await client.post("/comfyart/wavespeed/run", json={"inputs": {**job, "prompt": "race"}})
    race = (await fresh.json())["error"]["confirm_token"]
    decision = {"tool": "edit_image", "provider": "replicate", "model": FLARE, "revision": revision, "capability": "image_edit"}
    wins = []

    def claim():
        provider_admin.bind_confirm_user("default")
        wins.append(provider_admin._take_confirm(race, decision, {**job, "prompt": "race"}))

    threads = [threading.Thread(target=claim) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert wins.count(True) == 1

    monkeypatch.setattr(provider_admin, "CONFIRM_TTL", -1)
    expired = await client.post("/comfyart/wavespeed/run", json={"inputs": {**job, "prompt": "old"}})
    expired_token = (await expired.json())["error"]["confirm_token"]
    again = await client.post("/comfyart/wavespeed/run", json={"inputs": {**job, "prompt": "old", "confirm_token": expired_token}})
    assert again.status == 409


async def test_llm_rehearsal_does_not_call_or_save(client, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    before = provider_admin.active_llm()
    res = await client.post("/comfyart/provider-admin/llm/rehearse", json={"provider": "deepseek", "model": "deepseek-flash"})
    body = await res.json()
    assert res.status == 200 and body["calls"] == 0 and body["network"] is False and body["connected"] is False
    assert body["kind"] == "rehearsal" and "没有联网" in body["message"]
    assert body["thinking"] == "disabled" and body["round"][1]["tool_calls"][0]["id"] == "call_local"
    assert provider_admin.active_llm() == before


async def test_gif_defaults_to_replicate_26_and_llm_defaults_official(monkeypatch):
    from ComfyArt.api.wavespeed import WaveSpeedError
    from ComfyArt.bot.providers import TurnRequest, get_provider
    posts = []

    async def post(url, body, token):
        posts.append(url)
        return "pred_gif"

    async def orig(inputs):
        return "wave"

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-a-real-deepseek-key")
    assert await provider_admin.dispatch_submit({"feature": "text_to_image", "prompt": "still"}, orig) == "wave"
    assert await provider_admin.dispatch_submit({"feature": "text_to_video", "prompt": "clip"}, orig) == "wave"
    gif = {"feature": "text_to_image", "prompt": "loop", "params": {"output_format": "gif"}}
    with pytest.raises(WaveSpeedError) as caught:
        await provider_admin.dispatch_submit(gif, orig)
    assert caught.value.unpriced and caught.value.confirm_token and posts == []
    assert await provider_admin.dispatch_submit({**gif, "confirm_token": caught.value.confirm_token}, orig) == "pred_gif"
    assert posts == ["https://api.replicate.com/v1/models/openai/gpt-image-2.6-flare/predictions"]
    again = await provider_admin.dispatch_submit({**gif, "confirm_token": "spent"}, orig)
    assert again == "pred_gif" and len(posts) == 1
    sun = {"feature": "text_to_image", "prompt": "sun", "model": "openai/gpt-image-2.6-sunburst/text-to-image", "params": {"output_format": "gif"}}
    with pytest.raises(WaveSpeedError) as caught:
        await provider_admin.dispatch_submit(sun, orig)
    posts.clear()
    assert await provider_admin.dispatch_submit({**sun, "confirm_token": caught.value.confirm_token}, orig) == "pred_gif"
    assert posts == ["https://api.replicate.com/v1/models/openai/gpt-image-2.6-sunburst/predictions"]
    monkeypatch.delenv("REPLICATE_API_TOKEN")

    async def wave(inputs):
        posts.append("wave")
        return "wave"

    with pytest.raises(WaveSpeedError) as caught:
        await provider_admin.dispatch_submit({"feature": "text_to_image", "prompt": "nokey", "params": {"output_format": "gif"}}, wave)
    assert caught.value.kind == "provider_unconfigured" and "wave" not in posts
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._write_tool("to_gif", {
        "revision": 3,
        "active": {"primary": {"provider": "wavespeed", "model": "existing"}, "backup": None, "fallback": False},
        "previous": None,
    })
    # Explicit WaveSpeed to_gif: pure text GIF passes through. Still+GIF is refused before provider.
    ref = {"tool": "to_gif", "feature": "text_to_image", "prompt": "keep", "params": {"output_format": "gif"}}
    assert await provider_admin.dispatch_submit(ref, orig) == "wave"
    with pytest.raises(WaveSpeedError) as still:
        await provider_admin.dispatch_submit({**ref, "image": "https://cdn.example/a.png"}, orig)
    assert still.value.kind == "gifStillUnsupported"
    route = provider_admin.llm_route()
    assert route["model"] == "deepseek-flash" and route["base_url"] == "https://api.deepseek.com"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    missed = await get_provider("local-llm").send(TurnRequest(chat_id="c", user_text="hi"), None, None)
    assert "DEEPSEEK_API_KEY" in missed.error and "未发送" in missed.error
    provider_admin._save_section("llm", {"provider": "wavespeed", "model": "existing"})
    assert provider_admin.llm_route() is None
    assert provider_admin.active_llm()["provider"] == "wavespeed"


# --- Source contract: ProviderAdmin draft/live (mutation must fail if gif_default unscoped) ---
import re as _re
from pathlib import Path as _Path

_PROVIDER_ADMIN_SRC = (_Path(__file__).resolve().parents[1] / "src/ui/ProviderAdmin.tsx").read_text(encoding="utf-8")


def _provider_admin_fn(name: str) -> str:
    m = _re.search(rf"function {name}\(tool: ToolRow\): ToolRoute \{{(.*?)\n\}}", _PROVIDER_ADMIN_SRC, _re.S)
    assert m, f"missing {name}"
    return m.group(1)


def test_live_baseline_gif_default_only_for_to_gif():
    body = _provider_admin_fn("liveBaseline")
    assert "gif_default" in body
    assert "tool.id === 'to_gif'" in body or 'tool.id === "to_gif"' in body
    # Bare `if (tool.gif_default)` (no to_gif on the same statement) is the mutation QA used.
    assert _re.search(r"if\s*\(\s*tool\.gif_default\s*\)", body) is None
    assert _re.search(r"tool\.id\s*===\s*['\"]to_gif['\"]\s*&&\s*tool\.gif_default", body)


def test_draft_route_delegates_to_live_baseline():
    body = _provider_admin_fn("draftRoute")
    assert "liveBaseline(tool)" in body


async def test_auto_still_estimate_tip_follows_generate_image_effective(monkeypatch):
    """Empty Auto still tip stamps WaveSpeed provider; keeps submit-aligned model (flare id OK)."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._write_tool("generate_image", {"revision": 0, "active": None, "previous": None, "draft": None})

    async def orig(inputs):
        # Mimic wavespeed.estimate resolving Auto → curated flare (submit path).
        return {"price": 0.045, "currency": "USD", "source": "estimate", "model": FLARE, "tier": "1k"}

    job = {"tool": "generate_image", "feature": "text_to_image", "prompt": "a cat"}
    body = await provider_admin.dispatch_estimate(job, orig)
    assert body["provider"] == "wavespeed"
    assert body["model"] == FLARE  # must stay quote/submit model — never rewrite to Live existing
    assert body["effective"] is True
    assert body["effective_model"] == "existing"
    assert body["price"] == 0.045

    # Explicit model pick: no effective overlay.
    body2 = await provider_admin.dispatch_estimate({**job, "model": FLARE}, orig)
    assert body2["model"] == FLARE
    assert body2.get("effective") is not True

    # GIF path is out of scope for this tip rewrite.
    gif_job = {"tool": "generate_image", "feature": "text_to_image", "prompt": "loop", "params": {"output_format": "gif"}}
    body3 = await provider_admin.dispatch_estimate(gif_job, orig)
    assert body3.get("effective") is not True


async def test_auto_still_estimate_tip_follows_saved_replicate_live(monkeypatch):
    """When Live Primary is Replicate flare, empty Auto tip follows that effective, not WaveSpeed."""
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._write_tool("generate_image", {
        "revision": 1,
        "active": {"primary": {"provider": "replicate", "model": FLARE}, "backup": None, "fallback": False},
        "previous": None,
        "draft": None,
    })

    async def orig(inputs):
        return {"price": 0.045, "currency": "USD", "source": "estimate", "model": "other", "tier": "1k"}

    # Saved Replicate primary: dispatch_estimate takes the Replicate branch (not wavespeed orig overlay).
    body = await provider_admin.dispatch_estimate(
        {"tool": "generate_image", "feature": "text_to_image", "prompt": "a"},
        orig,
    )
    assert body["provider"] == "replicate"
    assert body["model"] == FLARE
