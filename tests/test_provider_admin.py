"""Provider settings: admin config, image contract, LLM isolation. No live paid calls."""
from __future__ import annotations

import asyncio
import json
import os
import stat

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ComfyArt.api import provider_admin, replicate_image, settings
from ComfyArt.api.provider_catalog import audit_rows, audit_summary, render_audit_markdown
from ComfyArt.bot.providers import TurnHandle, TurnRequest, get_provider

TOKEN = "r8_test_not_a_real_token"
DEEPSEEK = "sk-test-not-a-real-deepseek-key"
FLARE = "openai/gpt-image-2.6-flare"
SUNBURST = "openai/gpt-image-2.6-sunburst"
IMAGE = {
    "provider": "replicate",
    "models": {cap: FLARE for cap in ("text_to_image", "image_edit", "text_to_gif", "reference_gif")},
}


@pytest.fixture
async def client():
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    c = TestClient(TestServer(app))
    await c.start_server()
    yield c
    await c.close()


def _mode(path: str) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


async def test_admin_gate_and_empty_config_leaves_routes(client, monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    monkeypatch.setenv("DEEPSEEK_API_KEY", DEEPSEEK)
    denied = await client.get("/comfyart/provider-admin", headers={"comfy-user": "alice"})
    assert denied.status == 403
    res = await client.get("/comfyart/provider-admin")
    body = await res.json()
    raw = await res.text()
    assert res.status == 200
    assert TOKEN not in raw and DEEPSEEK not in raw
    assert body["image"]["active"] is None and body["llm"]["active"] is None
    assert body["image"]["saved"] is False and body["llm"]["saved"] is False
    assert body["llm"]["probe"] == "off"
    assert body["image"]["providers"][1]["configured"] is True
    assert body["llm"]["providers"][1]["configured"] is True
    assert "完全兼容" not in json.dumps(body, ensure_ascii=False)


async def test_missing_keys_are_boolean_only(client, monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    body = await (await client.get("/comfyart/provider-admin")).json()
    replicate = next(p for p in body["image"]["providers"] if p["id"] == "replicate")
    deepseek = next(p for p in body["llm"]["providers"] if p["id"] == "deepseek")
    assert replicate["configured"] is False and replicate["secret_env"] == "REPLICATE_API_TOKEN"
    assert deepseek["configured"] is False and deepseek["secret_env"] == "DEEPSEEK_API_KEY"
    assert all(m["quote"] == "unknown" for m in replicate["models"])


async def test_secret_field_rejected_and_not_stored(client):
    res = await client.put("/comfyart/provider-admin/llm", json={"provider": "deepseek", "model": "deepseek-flash", "api_key": TOKEN})
    assert res.status == 400
    assert not os.path.exists(provider_admin._path())


async def test_image_save_restore_and_file_mode(client):
    res = await client.put("/comfyart/provider-admin/image", json=IMAGE)
    body = await res.json()
    assert res.status == 200
    assert body["image"]["active"]["provider"] == "replicate"
    assert body["image"]["revision"] == 1
    assert _mode(provider_admin._path()) == 0o600
    bad = await client.put("/comfyart/provider-admin/image", json={"provider": "replicate", "models": {"text_to_image": "made/up"}})
    assert bad.status == 400
    assert (await (await client.get("/comfyart/provider-admin")).json())["image"]["revision"] == 1
    restored = await (await client.post("/comfyart/provider-admin/image/restore")).json()
    assert restored["image"]["active"] is None
    assert provider_admin.active_image() is None


async def test_llm_save_is_isolated_from_production_settings(client):
    before = settings.get_setting("bot-model-local-llm")
    url = settings.get_setting("bot-local-llm-url")
    assert before == "deepseek/deepseek-v4.1-flash-1017"
    assert provider_admin.llm_model_override() is None
    res = await client.put("/comfyart/provider-admin/llm", json={"provider": "deepseek", "model": "deepseek-flash"})
    assert res.status == 200
    assert settings.get_setting("bot-model-local-llm") == before
    assert settings.get_setting("bot-local-llm-url") == url
    assert provider_admin.llm_model_override() == "deepseek-flash"
    draft = {"provider": "deepseek", "model": "deepseek-v4-pro"}
    assert provider_admin.llm_model_override() == "deepseek-flash"
    assert draft["model"] != provider_admin.active_llm()["model"]
    restored = await (await client.post("/comfyart/provider-admin/llm/restore")).json()
    assert restored["llm"]["active"] is None
    assert provider_admin.llm_model_override() is None
    assert settings.SETTINGS_SPEC["bot-model-local-llm"] == "deepseek/deepseek-v4.1-flash-1017"


async def test_old_and_invalid_config_stay_passthrough(tmp_path, monkeypatch):
    path = provider_admin._path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"provider": "replicate", "image": {"revision": 3, "active": {"provider": "replicate", "models": {}}}}, handle)
    assert provider_admin.active_image() is None
    assert provider_admin.decide_image({"feature": "text_to_image", "prompt": "x"})["passthrough"] is True


def test_replicate_payload_contract():
    still = replicate_image.build_input("text_to_image", {"prompt": "a lantern", "width": 1024, "height": 1024, "quality": "medium"})
    assert still["prompt"] == "a lantern" and still["aspect_ratio"] == "1024x1024"
    assert "input_images" not in still and still.get("output_format") != "gif"
    assert "openai_api_key" not in still
    edit = replicate_image.build_input("image_edit", {"prompt": "make it blue", "images": ["https://cdn.example/a.png", "https://cdn.example/b.png"]})
    assert edit["input_images"] == ["https://cdn.example/a.png", "https://cdn.example/b.png"]
    assert edit.get("output_format") != "gif"
    gif = replicate_image.build_input("text_to_gif", {"prompt": "the lantern sways", "frame_count": 99, "frame_duration_ms": 5})
    assert gif["output_format"] == "gif" and gif["frame_count"] == 16 and gif["frame_duration_ms"] == 20
    assert "input_images" not in gif
    ref = replicate_image.build_input("reference_gif", {"prompt": "animate this", "image": "https://cdn.example/still.png", "params": {"frame_count": 4, "frame_duration_ms": 200}})
    assert ref["input_images"] == ["https://cdn.example/still.png"] and ref["output_format"] == "gif"
    with pytest.raises(replicate_image.PayloadError):
        replicate_image.build_input("reference_gif", {"prompt": "animate"})
    with pytest.raises(replicate_image.PayloadError):
        replicate_image.build_input("text_to_gif", {"prompt": "x", "images": ["https://cdn.example/a.png"]})
    with pytest.raises(replicate_image.PayloadError):
        replicate_image.build_input("image_edit", {"prompt": "x"})
    body = replicate_image.prediction_body("text_to_image", {"prompt": "x"})
    assert set(body) == {"input"}
    assert replicate_image.prediction_url(FLARE) == f"https://api.replicate.com/v1/models/openai/{FLARE.split('/', 1)[1]}/predictions"


async def test_unsaved_image_job_uses_existing_submit(monkeypatch):
    called = {}

    async def orig(inputs):
        called["inputs"] = inputs
        return "kept"

    monkeypatch.setattr(provider_admin, "_image_orig", orig)
    import ComfyArt.api.wavespeed as wavespeed
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "unchanged", "output_format": "gif"})
    assert task == "kept" and called["inputs"]["prompt"] == "unchanged"


async def test_replicate_blocks_unknown_price_and_keeps_reference(monkeypatch):
    posts = []

    async def post(url, body, token):
        posts.append((url, body, token))
        return "pred_1"

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._save_section("image", IMAGE)
    import ComfyArt.api.wavespeed as wavespeed
    from ComfyArt.api.wavespeed import WaveSpeedError
    estimate = await wavespeed.estimate({"feature": "generate_image", "prompt": "lantern", "output_format": "gif", "image": "https://cdn.example/a.png"})
    assert estimate["quote_status"] == "unknown" and estimate["confirm"] is False and estimate["price"] is None
    assert estimate["provider"] == "replicate" and estimate["capability"] == "reference_gif"
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({"feature": "generate_image", "prompt": "lantern", "output_format": "gif", "image": "https://cdn.example/a.png", "confirmed": True})
    assert caught.value.kind == "quote_unknown" and posts == []


async def test_replicate_quote_fixture_posts_once_and_locks(monkeypatch):
    posts = []

    async def post(url, body, token):
        posts.append(body)
        if len(posts) == 1:
            return "pred_locked"
        raise AssertionError("second post")

    async def priced(model, capability, inputs):
        return 1.25, "quote"

    async def status(task, token):
        assert token == TOKEN
        return "processing"

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setattr(provider_admin, "_quote_override", priced)
    monkeypatch.setattr(provider_admin, "_fetch_prediction", status)
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._save_section("image", {**IMAGE, "models": {**IMAGE["models"], "text_to_image": SUNBURST}})
    import ComfyArt.api.wavespeed as wavespeed
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "poster", "width": 768, "height": 768})
    assert task == "pred_locked" and len(posts) == 1
    assert posts[0]["input"]["prompt"] == "poster" and "input_images" not in posts[0]["input"]
    assert TOKEN not in json.dumps(posts[0])
    job = provider_admin._replicate_jobs[task]
    assert job["provider"] == "replicate" and job["model"] == SUNBURST
    provider_admin._save_section("image", {"provider": "wavespeed"})
    assert provider_admin._replicate_jobs[task]["model"] == SUNBURST
    history = await wavespeed.poll(task)
    assert task in next(iter(history))
    assert posts and len(posts) == 1


async def test_timeout_does_not_repost_or_switch(monkeypatch):
    calls = {"post": 0, "orig": 0}

    async def post(url, body, token):
        calls["post"] += 1
        raise TimeoutError()

    async def orig(inputs):
        calls["orig"] += 1
        return "nope"

    async def priced(model, capability, inputs):
        return 1, "quote"

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setattr(provider_admin, "_image_orig", orig)
    monkeypatch.setattr(provider_admin, "_quote_override", priced)
    monkeypatch.setenv("REPLICATE_API_TOKEN", TOKEN)
    provider_admin._save_section("image", IMAGE)
    import ComfyArt.api.wavespeed as wavespeed
    from ComfyArt.api.wavespeed import WaveSpeedError
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "once"})
    assert caught.value.kind == "unknown"
    assert calls == {"post": 1, "orig": 0}


async def test_missing_replicate_token_does_not_post(monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)

    async def post(url, body, token):
        raise AssertionError("posted")

    async def priced(model, capability, inputs):
        return 1, "quote"

    monkeypatch.setattr(provider_admin, "_post_prediction", post)
    monkeypatch.setattr(provider_admin, "_quote_override", priced)
    provider_admin._save_section("image", IMAGE)
    import ComfyArt.api.wavespeed as wavespeed
    from ComfyArt.api.wavespeed import WaveSpeedError
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({"feature": "edit_image", "prompt": "x", "image": "https://cdn.example/a.png"})
    assert caught.value.kind == "provider_unconfigured"


async def test_other_tools_stay_on_wavespeed_and_route_change_blocks(monkeypatch):
    seen = []

    async def orig(inputs):
        seen.append(inputs["feature"])
        return "wave"

    monkeypatch.setattr(provider_admin, "_image_orig", orig)
    provider_admin._save_section("image", IMAGE)
    import ComfyArt.api.wavespeed as wavespeed
    from ComfyArt.api.wavespeed import WaveSpeedError
    assert await wavespeed.submit({"feature": "text_to_video", "prompt": "waves"}) == "wave"
    assert await wavespeed.submit({"feature": "replace_text", "prompt": "logo", "image": "https://cdn.example/a.png"}) == "wave"
    await wavespeed.estimate({"feature": "text_to_image", "prompt": "lock-me"})
    provider_admin._save_section("image", {"provider": "wavespeed"})
    with pytest.raises(WaveSpeedError) as caught:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "lock-me"})
    assert caught.value.kind == "route_changed"
    assert seen == ["text_to_video", "replace_text"]


async def test_llm_switch_is_locked_to_the_turn_and_hides_the_key(monkeypatch, caplog):
    provider = get_provider("local-llm")
    assert provider is not None
    calls = []
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        auth = headers.get("Authorization", "")
        calls.append({"method": method, "url": url, "body": json_body, "auth": auth})
        if method == "POST":
            started.set()
            await release.wait()
            return {"choices": [{"message": {"content": "ok"}}], "usage": {}}
        return {"data": [{"id": "deepseek-flash"}]}

    monkeypatch.setattr(provider_admin, "_llm_http", fake)
    monkeypatch.setenv("DEEPSEEK_API_KEY", DEEPSEEK)
    provider_admin._save_section("llm", {"provider": "deepseek", "model": "deepseek-flash"})

    async def emit(event):
        return None

    caplog.set_level("INFO")
    task = asyncio.create_task(provider.send(
        TurnRequest(chat_id="c", user_text="hi", model="deepseek/deepseek-v4.1-flash-1017"),
        emit, TurnHandle()))
    await started.wait()
    provider_admin._save_section("llm", {"provider": "wavespeed", "model": "existing"})
    release.set()
    result = await task
    assert result.error in (None, "")
    post = next(call for call in calls if call["method"] == "POST")
    assert post["url"] == "https://api.deepseek.com/chat/completions"
    assert post["body"]["model"] == "deepseek-flash"
    assert post["body"]["thinking"] == {"type": "disabled"}
    assert post["body"].get("stream") is not True
    assert "tools" not in post["body"] or isinstance(post["body"].get("tools"), list)
    assert post["auth"] == f"Bearer {DEEPSEEK}"
    assert DEEPSEEK not in caplog.text
    assert all("llm.wavespeed.ai" not in call["url"] for call in calls)


async def test_llm_without_key_does_not_call_and_unsaved_stays(monkeypatch):
    provider = get_provider("local-llm")
    calls = []

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(url)
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(provider_admin, "_llm_http", fake)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    provider_admin._save_section("llm", {"provider": "deepseek", "model": "deepseek-v4-pro"})

    async def emit(event):
        return None

    result = await provider.send(TurnRequest(chat_id="c", user_text="hi", model="deepseek/deepseek-v4.1-flash-1017"), emit, TurnHandle())
    assert "DEEPSEEK_API_KEY" in (result.error or "")
    assert calls == []
    provider_admin._restore_section("llm")
    assert provider_admin.llm_route() is None


def test_llm_body_adapter_does_not_run_without_a_saved_route():
    body = {"model": "deepseek/deepseek-v4.1-flash-1017", "temperature": 0.2, "stream": True}
    assert provider_admin.adapt_llm_body(body, "https://llm.wavespeed.ai/v1/chat/completions")["stream"] is True


def test_audit_separates_implemented_routes_from_the_catalog():
    rows = audit_rows()
    summary = audit_summary()
    enabled = [row for row in rows if row["enabled"]]
    assert enabled
    assert {row["replicate_model"] for row in enabled} <= {FLARE, SUNBURST}
    assert {row["feature"] for row in enabled} <= {"text_to_image", "image_edit"}
    assert all(row["verdict"] == "mapped_with_differences" for row in enabled)
    video = [row for row in rows if "video" in row["feature"]]
    assert video and all(not row["enabled"] for row in video)
    tools = {row["tool"]: row["replicate_enabled"] for row in summary["tools"]}
    assert tools["generate_image"] and tools["edit_image"]
    assert tools["generate_video"] is False and tools["text_to_speech"] is False
    text = render_audit_markdown()
    assert "完全兼容" not in text
    assert "价格未知" in text or "费用" in text
    assert "deepseek-flash" in text and "deepseek/deepseek-v4.1-flash-1017" in text
    assert "input_images" in text
    from ComfyArt.api.provider_catalog import ROOT
    curated = json.loads((ROOT / "curated_models.json").read_text(encoding="utf-8"))["features"]
    for feature, spec in curated.items():
        ids = set(spec.get("models") or []) | set(spec.get("more") or [])
        found = {row["wavespeed_model"] for row in rows if row["feature"] == feature}
        assert ids <= found
