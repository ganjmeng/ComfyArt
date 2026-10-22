"""WaveSpeed provider tests against a local mock server (WAVESPEED_BASE_URL); no real API calls."""
from __future__ import annotations

import io
import json
import os

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from ComfyArt.api import wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest

T2I = "alibaba/qwen-image-3.0/text-to-image"
EDIT = "alibaba/qwen-image-3.0/edit"
KEY = "test-key-not-real"


def _meta(model_id, props, required=("prompt",), price=0.03):
    return {"model_id": model_id, "name": model_id.split("/")[-1], "type": "x", "base_price": price, "description": "d",
            "api_schema": {"api_schemas": [{"request_schema": {"properties": props, "required": list(required)}}]}}


MODELS = [
    _meta(T2I, {"prompt": {"type": "string"}, "size": {"type": "string"}, "seed": {"type": "integer"}}),
    _meta("wavespeed-ai/z-image/turbo", {"prompt": {"type": "string"}, "size": {"type": "string"}}, price=0.005),
    _meta(EDIT, {"prompt": {"type": "string"}, "images": {"type": "array", "maxItems": 3}}, ("prompt", "images")),
    _meta("wavespeed-ai/image-eraser", {"image": {"type": "string"}, "mask_image": {"type": "string"}}, ("image",)),
    _meta("wavespeed-ai/paddle-ocr", {"image": {"type": "string"}, "output_format": {"type": "string", "enum": ["json", "markdown"]}}, ("image",), price=0.01),
    _meta("wavespeed-ai/sam3-image", {"image": {"type": "string"}, "prompt": {"type": "string"}, "point_prompts": {"type": "array"}, "box_prompts": {"type": "array"}, "apply_mask": {"type": "boolean"}, "output_format": {"type": "string", "enum": ["png"]}}, ("image",), price=0.005),
    _meta("bytedance/seedream-v5.0-flash/layer-decomposition", {"image": {"type": "string"}, "prompt": {"type": "string"}, "output_format": {"type": "string", "enum": ["jpeg", "png"]}}, ("image",), price=0.459),
    _meta("bytedance/seedream-v5.0-pro/layer-decomposition", {"image": {"type": "string"}, "prompt": {"type": "string"}}, ("image",), price=0.75),
    _meta("wavespeed-ai/minimax-h3/text-to-video", {"prompt": {"type": "string"}, "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"]}, "duration": {"type": "integer", "enum": [3, 4, 5, 6, 7, 8]}, "resolution": {"type": "string", "enum": ["480p", "540p", "768p", "1080p"]}, "seed": {"type": "integer"}}, price=0.04),
    _meta("alibaba/wan-3.0/text-to-video", {"prompt": {"type": "string"}, "duration": {"type": "integer"}}, price=0.1),
    _meta("wavespeed-ai/minimax-h3/image-to-video", {"prompt": {"type": "string"}, "image": {"type": "string"}, "last_image": {"type": "string"}, "duration": {"type": "integer", "enum": [3, 4, 5, 6, 7, 8]}, "resolution": {"type": "string", "enum": ["480p", "768p", "1080p"]}}, ("prompt", "image"), price=0.04),
    _meta("wavespeed-ai/minimax-h3/reference-to-video", {"prompt": {"type": "string"}, "reference_images": {"type": "array"}, "reference_videos": {"type": "array"}, "reference_audios": {"type": "array"}}, price=0.15),
    _meta("wavespeed-ai/wan-2.2/animate", {"image": {"type": "string"}, "video": {"type": "string"}, "prompt": {"type": "string"}}, ("image", "video"), price=0.2),
    _meta("wavespeed-ai/infinitetalk-fast", {"image": {"type": "string"}, "audio": {"type": "string"}, "prompt": {"type": "string"}}, ("audio", "image"), price=0.075),
    _meta("wavespeed-ai/minimax-h3/video-extend", {"video": {"type": "string"}, "prompt": {"type": "string"}, "duration": {"type": "integer", "enum": [3, 4, 5, 6, 7, 8]}}, ("prompt", "video"), price=0.04),
    _meta("wavespeed-ai/video-upscaler", {"video": {"type": "string"}, "target_resolution": {"type": "string", "enum": ["720p", "1080p", "2k", "4k"]}}, ("video",), price=0.005),
    _meta("wavespeed-ai/video-background-remover", {"video": {"type": "string"}}, ("video",), price=0.01),
    _meta("wavespeed-ai/ace-step-1.5", {"tags": {"type": "string"}, "lyrics": {"type": "string"}, "duration": {"type": "number"}, "seed": {"type": "integer"}}, ("tags", "lyrics"), price=0.0003),
    _meta("elevenlabs/music-v2", {"prompt": {"type": "string"}, "music_length_ms": {"type": "integer"}}, ("prompt", "music_length_ms"), price=0.75),
    _meta("mirelo-ai/sfx-2.0/text-to-audio", {"prompt": {"type": "string"}, "duration": {"type": "number"}}, price=0.016),
    _meta("wavespeed-ai/qwen3-tts/text-to-speech", {"text": {"type": "string"}, "language": {"type": "string", "enum": ["auto", "Chinese", "English"]}, "voice": {"type": "string", "enum": ["Vivian", "Serena", "Uncle_Fu"]}}, ("text", "language", "voice"), price=0.005),
    _meta("wavespeed-ai/qwen3-tts/voice-clone", {"audio": {"type": "string"}, "text": {"type": "string"}, "language": {"type": "string", "enum": ["auto"]}}, ("audio", "text"), price=0.005),
    _meta("wavespeed-ai/trellis-2/image-to-3d", {"image": {"type": "string"}, "seed": {"type": "integer"}}, ("image",), price=0.2),
    _meta("tripo3d/h3.1/multiview-to-3d", {"images": {"type": "array"}}, ("images",), price=0.24),
    _meta("wavespeed-ai/openai-whisper-turbo", {"audio": {"type": "string"}, "language": {"type": "string", "enum": ["auto"]}}, ("audio",), price=0.0007),
    _meta("wavespeed-ai/image-captioner", {"image": {"type": "string"}}, ("image",), price=0.001),
    _meta("wavespeed-ai/image-upscaler", {"image": {"type": "string"}, "target_resolution": {"type": "string", "enum": ["2k", "4k", "8k"]}}, ("image",)),
]


@pytest.fixture
async def ws(monkeypatch, fresh_user_dir):
    state = {"status": "completed", "submits": [], "polls": 0, "uploads": 0, "auth": set(), "submit_status": 200, "result_status": 200}
    app = web.Application()

    async def models(request):
        state["auth"].add(request.headers.get("Authorization"))
        return web.json_response({"code": 200, "data": MODELS})

    async def submit(request):
        state["auth"].add(request.headers.get("Authorization"))
        if state["submit_status"] != 200:
            return web.json_response({"code": state["submit_status"], "message": "nope"}, status=state["submit_status"])
        state["submits"].append((request.match_info["model"], await request.json()))
        return web.json_response({"code": 200, "data": {"id": f"task{len(state['submits'])}", "status": "created"}})

    async def result(request):
        state["polls"] += 1
        if state["result_status"] != 200:
            return web.json_response({"message": "x"}, status=state["result_status"])
        st = state["status"]
        data = {"id": request.match_info["id"], "status": st, "outputs": [], "error": ""}
        if st == "completed":
            data["outputs"] = state.get("outputs") or [str(request.url.with_path("/cdn/out.png"))]
        if st == "failed":
            data["error"] = "content flagged"
        return web.json_response({"code": 200, "data": data})

    async def upload(request):
        state["uploads"] += 1
        reader = await request.multipart()
        async for part in reader:
            await part.read()
        return web.json_response({"code": 200, "data": {"download_url": f"https://cdn.test/up{state['uploads']}.png"}})

    async def cdn(request):
        return web.Response(body=b"PNGDATA")

    app.router.add_get("/api/v3/models", models)
    app.router.add_post("/api/v3/media/upload/binary", upload)
    app.router.add_get("/api/v3/predictions/{id}/result", result)
    app.router.add_post("/api/v3/{model:.+}", submit)
    app.router.add_get("/cdn/out.png", cdn)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setenv("WAVESPEED_BASE_URL", str(server.make_url("")))
    monkeypatch.setenv("WAVESPEED_API_KEY", KEY)
    monkeypatch.setattr(wavespeed, "POLL_MIN", 0.0)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    wavespeed._jobs.clear()
    wavespeed._submits.clear()
    yield state
    await server.close()


async def test_text_to_image_submit_poll_download(ws):
    task = await wavespeed.submit({"feature": "generate_image", "prompt": "a red apple", "width": 1024, "height": 768, "seed": 7})
    model, payload = ws["submits"][0]
    assert model == T2I  # product default when no model is given
    assert payload == {"prompt": "a red apple", "size": "1024*768", "seed": 7}
    assert ws["auth"] == {f"Bearer {KEY}"}
    hist = await wavespeed.poll(task)
    out = hist[f"ws:{task}"]
    assert out["status"]["completed"] is True
    ref = out["outputs"]["ws"]["images"][0]
    assert ref["subfolder"] == "wavespeed" and ref["type"] == "output"
    import folder_paths
    assert wavespeed._read(os.path.join(folder_paths.get_output_directory(), "wavespeed", ref["filename"])) == b"PNGDATA"
    # finished results are cached: no second poll or download
    polls = ws["polls"]
    await wavespeed.poll(task)
    assert ws["polls"] == polls


async def test_model_choice_is_honored_and_validated(ws):
    await wavespeed.submit({"feature": "text_to_image", "model": "wavespeed-ai/z-image/turbo", "prompt": "x"})
    assert ws["submits"][0][0] == "wavespeed-ai/z-image/turbo"
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "model": "made/up-model", "prompt": "x"})
    assert e.value.status == 400 and "unknown model" in str(e.value)
    assert len(ws["submits"]) == 1  # rejected before any (paid) submit


async def test_edit_uploads_local_input(ws):
    import folder_paths
    os.makedirs(os.path.join(folder_paths.get_input_directory(), "comfyart"), exist_ok=True)
    wavespeed._write(os.path.join(folder_paths.get_input_directory(), "comfyart", "a.png"), b"img")
    await wavespeed.submit({"feature": "edit_image", "image": "comfyart/a.png [input]", "prompt": "make it blue"})
    model, payload = ws["submits"][0]
    assert model == EDIT and payload["images"] == ["https://cdn.test/up1.png"] and payload["prompt"] == "make it blue"


async def test_erase_converts_mask(ws):
    import folder_paths
    from PIL import Image
    inp = folder_paths.get_input_directory()
    os.makedirs(inp, exist_ok=True)
    Image.new("RGB", (8, 8)).save(os.path.join(inp, "src.png"))
    mask = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
    mask.putpixel((1, 1), (255, 255, 255, 0))
    mask.save(os.path.join(inp, "mask.png"))
    await wavespeed.submit({"feature": "erase_region", "image": "src.png [input]", "mask": "mask.png [input]"})
    payload = ws["submits"][0][1]
    assert set(payload) == {"image", "mask_image"}
    white = Image.open(io.BytesIO(wavespeed.mask_to_white(wavespeed._read(os.path.join(inp, "mask.png")))))
    assert white.getpixel((1, 1)) == 255 and white.getpixel((0, 0)) == 0


async def test_failed_task_reports_error(ws):
    ws["status"] = "failed"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    msgs = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"]
    assert msgs[0][0] == "execution_error" and "content flagged" in msgs[0][1]["exception_message"]


async def test_timeout(ws, monkeypatch):
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["completed"] is False
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    msgs = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"]
    assert "timed out" in msgs[0][1]["exception_message"]


async def test_401_on_submit_and_poll(ws):
    ws["submit_status"] = 401
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    assert e.value.status == 401 and KEY not in str(e.value)
    ws["submit_status"] = 200
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    ws["result_status"] = 401
    msg = (await wavespeed.poll(task))[f"ws:{task}"]["status"]["messages"][0][1]["exception_message"]
    assert "401" in msg and KEY not in msg


async def test_poll_is_throttled_to_2s(ws, monkeypatch):
    monkeypatch.setattr(wavespeed, "POLL_MIN", 2.0)
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    wavespeed._jobs[task]["next_poll"] = 0
    await wavespeed.poll(task)
    await wavespeed.poll(task)  # within 2 s: answered from cache, no API call
    assert ws["polls"] == 1


async def test_missing_key(ws, monkeypatch):
    monkeypatch.delenv("WAVESPEED_API_KEY")
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    assert "WAVESPEED_API_KEY" in str(e.value)


async def test_pending_features_not_available_yet(ws):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "depth", "image": "x.png [input]"})  # configured but unused
    assert "not available in cloud mode" in str(e.value) and not ws["submits"]


async def test_app_concurrency_limit(ws, monkeypatch):
    ws["status"] = "processing"
    monkeypatch.setattr(wavespeed, "limits", lambda: {"app_concurrent": 1, "wavespeed_concurrent": 300, "wavespeed_submits_per_minute": 500, "batch_max": 50, "confirm_usd": 0.5})
    await wavespeed.submit({"feature": "text_to_image", "prompt": "x"})
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "prompt": "y"})
    assert e.value.status == 429 and len(ws["submits"]) == 1


async def test_list_models_curated_only(ws):
    out = await canvas.TOOLS["list_models"]["handler"]({})
    t2i = out["features"]["text_to_image"]
    ids = [m["id"] for m in t2i["models"]]
    assert t2i["default"] == T2I and ids[0] == T2I
    assert "made/up-model" not in ids and len(ids) == len(wavespeed.load_config()["features"]["text_to_image"]["models"])
    assert next(m for m in t2i["models"] if m["id"] == T2I)["price"] == 0.03
    assert out["features"]["image_to_video"]["available"] is True and out["features"]["depth"]["available"] is False
    assert out["features"]["split_layers"]["available"] is True and out["features"]["segment"]["available"] is True
    assert "model" in canvas.TOOLS["edit_image"]["inputSchema"]["properties"]


async def test_routes_run_and_history(ws):
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post("/comfyart/wavespeed/run", json={"inputs": {"feature": "text_to_image", "prompt": "hi"}})
        pid = (await res.json())["prompt_id"]
        assert pid.startswith("ws:")
        hist = await (await client.get(f"/comfyart/wavespeed/history/{pid[3:]}")).json()
        assert hist[pid]["outputs"]["ws"]["images"]
        models = await (await client.get("/comfyart/wavespeed/models")).json()
        assert KEY not in json.dumps(models) and models["enabled"] is True
        bad = await client.post("/comfyart/wavespeed/run", json={"inputs": {"feature": "text_to_image", "model": "x/y", "prompt": "hi"}})
        assert bad.status == 400
    finally:
        await client.close()


async def test_builtin_agent_one_sentence_image(ws):
    """Built-in agent (OpenAI-compatible endpoint, mocked) turns one sentence into a WaveSpeed image."""
    llm_calls = []
    replies = [
        {"tool_calls": [{"id": "1", "function": {"name": "list_models", "arguments": "{}"}}]},
        {"tool_calls": [{"id": "2", "function": {"name": "generate_image", "arguments": json.dumps({"prompt": "a cat astronaut"})}}]},
        {"tool_calls": [{"id": "3", "function": {"name": "wait_generation", "arguments": json.dumps({"ids": ["shape:g"]})}}]},
        {"content": "Done: your cat astronaut is on the canvas.", "tool_calls": []},
    ]
    llm = web.Application()

    async def completions(request):
        body = await request.json()
        llm_calls.append(body)
        return web.json_response({"choices": [{"message": {"content": "", **replies.pop(0)}}]})

    llm.router.add_post("/v1/chat/completions", completions)
    llm_server = TestServer(llm)
    await llm_server.start_server()
    jobs = {}

    async def fake_mcp(session, endpoint, name, arguments):
        if name == "list_models":
            return json.dumps(await canvas.TOOLS["list_models"]["handler"](arguments)), []
        if name == "generate_image":  # what the page does: queue the pseudo graph
            jobs["shape:g"] = await wavespeed.submit({"feature": "text_to_image", "model": arguments.get("model"), "prompt": arguments["prompt"], "width": 1024, "height": 1024})
            return json.dumps({"ids": ["shape:g"]}), []
        if name == "wait_generation":
            return json.dumps(await wavespeed.poll(jobs["shape:g"])), []
        raise AssertionError(name)

    async def fake_tools(session, endpoint):
        return [{"name": n, "description": "", "inputSchema": {"type": "object"}} for n in ("list_models", "generate_image", "wait_generation")]

    provider = LocalLlmProvider(base_url=lambda: str(llm_server.make_url("/v1")))
    provider._mcp_call_tool = fake_mcp
    provider._mcp_list_tools = fake_tools
    events = []

    async def emit(ev):
        events.append(ev)

    try:
        result = await provider.send(TurnRequest(chat_id="c", user_text="画一只宇航员猫", mcp_endpoint="http://x/mcp", model="kimi"), emit, TurnHandle())
    finally:
        await llm_server.close()
    assert result.error == ""
    assert [m for m, _ in ws["submits"]] == [T2I]
    assert ws["submits"][0][1]["prompt"] == "a cat astronaut"
    assert [e.name for e in events if e.t == "tool_use"] == ["list_models", "generate_image", "wait_generation"]
    assert events[-1].text.startswith("Done")
    assert len(llm_calls) == 4


async def test_ocr_runs_on_wavespeed(ws, bot_client, fresh_user_dir):
    from PIL import Image
    path = fresh_user_dir / "output" / "sale.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 24), "white").save(path)
    ws["outputs"] = [json.dumps({"layout": [{"block_content": "SUMMER SALE", "block_bbox": [4, 2, 70, 20]}, {"text": "50%", "poly": [[1, 1], [9, 1], [9, 5], [1, 5]], "score": 0.9}]})]
    res = await bot_client.post("/comfyart/ocr", json={"src": "/api/view?filename=sale.png&subfolder=&type=output"})
    assert res.status == 200, await res.text()
    lines = (await res.json())["lines"]
    assert [ln["text"] for ln in lines] == ["SUMMER SALE", "50%"] and all(len(ln["box"]) == 4 for ln in lines)
    model, payload = ws["submits"][0]
    assert model == "wavespeed-ai/paddle-ocr" and payload["output_format"] == "json" and payload["image"].startswith("https://cdn.test/")


def _input_png(name="src.png"):
    import folder_paths
    from PIL import Image
    os.makedirs(folder_paths.get_input_directory(), exist_ok=True)
    Image.new("RGB", (8, 8)).save(os.path.join(folder_paths.get_input_directory(), name))
    return f"{name} [input]"


async def test_sam_segment_points_and_text(ws):
    image = _input_png()
    pts = [{"x": 3, "y": 4, "label": 1}]
    task = await wavespeed.submit({"feature": "segment", "image": image, "params": {"apply_mask": False, "output_format": "png", "point_prompts": pts}})
    model, payload = ws["submits"][0]
    assert model == "wavespeed-ai/sam3-image"
    assert payload == {"image": "https://cdn.test/up1.png", "apply_mask": False, "output_format": "png", "point_prompts": pts}
    assert (await wavespeed.poll(task))[f"ws:{task}"]["outputs"]["ws"]["images"]
    await wavespeed.submit({"feature": "edit_elements", "image": image, "prompt": "person", "params": {"apply_mask": False}})
    assert ws["submits"][1][1]["prompt"] == "person"


async def test_split_layers_default_runs_without_confirmation(ws):
    await wavespeed.submit({"feature": "split_layers", "image": _input_png(), "png": True, "layers": 4})
    model, payload = ws["submits"][0]
    assert model == "bytedance/seedream-v5.0-flash/layer-decomposition" and payload["output_format"] == "png"
    assert payload["prompt"] == "Separate into 4 layers."
    await wavespeed.submit({"feature": "split_layers", "image": _input_png(), "prompt": "keep the logo", "layers": 3})
    assert ws["submits"][1][1]["prompt"] == "keep the logo. Separate into 3 layers."
    await wavespeed.submit({"feature": "split_layers", "image": _input_png(), "prompt": "poster.", "layers": 3})
    assert ws["submits"][2][1]["prompt"] == "poster. Separate into 3 layers."


async def test_jobs_over_50_cents_need_confirmation(ws):
    image = _input_png()
    job = {"feature": "split_layers", "model": "bytedance/seedream-v5.0-pro/layer-decomposition", "image": image}
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(job)
    assert e.value.status == 409 and e.value.confirm == 0.75 and not ws["submits"]
    await wavespeed.submit({**job, "confirmed": True})
    assert ws["submits"][0][0] == "bytedance/seedream-v5.0-pro/layer-decomposition"


async def test_confirmation_route_answers_409_with_price(ws):
    import server
    _input_png()
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        res = await client.post("/comfyart/wavespeed/run", json={"inputs": {"feature": "split_layers", "model": "bytedance/seedream-v5.0-pro/layer-decomposition", "image": "src.png [input]"}})
        assert res.status == 409 and (await res.json())["error"]["confirm_usd"] == 0.75
    finally:
        await client.close()


def _input_file(name, data=b"x"):
    import folder_paths
    os.makedirs(folder_paths.get_input_directory(), exist_ok=True)
    wavespeed._write(os.path.join(folder_paths.get_input_directory(), name), data)
    return f"{name} [input]"


async def test_text_to_video_default_and_mapping(ws):
    task = await wavespeed.submit({"feature": "text_to_video", "prompt": "waves", "ratio": "16:9", "duration": 5, "resolution": "768p", "seed": 3})
    model, payload = ws["submits"][0]
    assert model == "wavespeed-ai/minimax-h3/text-to-video"
    assert payload == {"prompt": "waves", "aspect_ratio": "16:9", "duration": 5, "resolution": "768p", "seed": 3}
    assert (await wavespeed.poll(task))[f"ws:{task}"]["outputs"]["ws"]["images"]


async def test_video_duration_snaps_to_enum_and_model_validated(ws):
    await wavespeed.submit({"feature": "text_to_video", "prompt": "x", "duration": 10})
    assert ws["submits"][0][1]["duration"] == 8
    await wavespeed.submit({"feature": "text_to_video", "model": "alibaba/wan-3.0/text-to-video", "prompt": "x", "duration": 10})
    assert ws["submits"][1] == ("alibaba/wan-3.0/text-to-video", {"prompt": "x", "duration": 10})
    with pytest.raises(wavespeed.WaveSpeedError):
        await wavespeed.submit({"feature": "text_to_video", "model": "wavespeed-ai/minimax-h3/image-to-video", "prompt": "x"})
    assert len(ws["submits"]) == 2


async def test_image_to_video_with_last_frame(ws):
    img = _input_png()
    await wavespeed.submit({"feature": "animate_image", "image": img, "last_image": img, "prompt": "move", "duration": 3})
    model, payload = ws["submits"][0]
    assert model == "wavespeed-ai/minimax-h3/image-to-video" and payload["image"].startswith("https://cdn.test/") and payload["last_image"] == payload["image"] and payload["duration"] == 3


async def test_reference_motion_lipsync(ws):
    img, vid, aud = _input_png(), _input_file("m.mp4"), _input_file("s.wav")
    await wavespeed.submit({"feature": "reference_to_video", "prompt": "p", "reference_images": [img], "reference_videos": [vid], "reference_audios": [aud]})
    await wavespeed.submit({"feature": "motion_control", "image": img, "video": vid})
    await wavespeed.submit({"feature": "lip_sync", "image": img, "audio": aud})
    (m1, p1), (m2, p2), (m3, p3) = ws["submits"]
    assert m1 == "wavespeed-ai/minimax-h3/reference-to-video" and len(p1["reference_images"]) == len(p1["reference_videos"]) == len(p1["reference_audios"]) == 1
    assert m2 == "wavespeed-ai/wan-2.2/animate" and set(p2) == {"image", "video"}
    assert m3 == "wavespeed-ai/infinitetalk-fast" and set(p3) == {"image", "audio"}


async def test_video_tools(ws):
    vid = _input_file("v.mp4")
    await wavespeed.submit({"feature": "extend_video", "video": vid, "prompt": "go on", "duration": 5})
    await wavespeed.submit({"feature": "upscale_video", "video": vid, "params": {"target_resolution": "4k"}})
    await wavespeed.submit({"feature": "remove_video_background", "video": vid})
    assert [m for m, _ in ws["submits"]] == ["wavespeed-ai/minimax-h3/video-extend", "wavespeed-ai/video-upscaler", "wavespeed-ai/video-background-remover"]
    assert ws["submits"][1][1]["target_resolution"] == "4k"


async def test_audio_tools(ws):
    await wavespeed.submit({"feature": "generate_music", "prompt": "lofi", "lyrics": "", "duration": 30})
    await wavespeed.submit({"feature": "generate_sound_effect", "prompt": "door slam", "duration": 3})
    await wavespeed.submit({"feature": "text_to_speech", "text": "你好", "voice": "Uncle_fu"})
    await wavespeed.submit({"feature": "voice_clone", "text": "hi", "audio": _input_file("ref.wav")})
    (m1, p1), (m2, p2), (m3, p3), (m4, p4) = ws["submits"]
    assert m1 == "wavespeed-ai/ace-step-1.5" and p1 == {"tags": "lofi", "lyrics": "[instrumental]", "duration": 30}
    assert m2 == "mirelo-ai/sfx-2.0/text-to-audio" and p2 == {"prompt": "door slam", "duration": 3}
    assert m3 == "wavespeed-ai/qwen3-tts/text-to-speech" and p3 == {"text": "你好", "voice": "Uncle_Fu", "language": "auto"}
    assert m4 == "wavespeed-ai/qwen3-tts/voice-clone" and p4["text"] == "hi" and p4["audio"].startswith("https://cdn.test/")


async def test_expensive_music_reuses_confirmation(ws):
    job = {"feature": "music", "model": "elevenlabs/music-v2", "prompt": "epic", "duration": 30}
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit(job)
    assert e.value.status == 409 and e.value.confirm == 0.75 and not ws["submits"]
    await wavespeed.submit({**job, "confirmed": True})
    assert ws["submits"][0][1] == {"prompt": "epic", "music_length_ms": 30000}


async def test_3d_single_and_multiview(ws):
    img = _input_png()
    task = await wavespeed.submit({"feature": "image_to_3d", "image": img})
    await wavespeed.submit({"feature": "image_to_3d", "model": "tripo3d/h3.1/multiview-to-3d", "images": [img, _input_png("b.png")]})
    (m1, p1), (m2, p2) = ws["submits"]
    assert m1 == "wavespeed-ai/trellis-2/image-to-3d" and set(p1) == {"image"}
    assert m2 == "tripo3d/h3.1/multiview-to-3d" and len(p2["images"]) == 2
    assert (await wavespeed.poll(task))[f"ws:{task}"]["status"]["completed"] is True


async def test_transcribe_route(ws, bot_client, fresh_user_dir):
    path = fresh_user_dir / "input" / "voice.webm"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"audio")
    ws["outputs"] = ["你好世界"]
    res = await bot_client.post("/comfyart/wavespeed/transcribe", json={"src": "/api/view?filename=voice.webm&subfolder=&type=input"})
    assert res.status == 200, await res.text()
    assert (await res.json())["text"] == "你好世界"
    assert ws["submits"][0][0] == "wavespeed-ai/openai-whisper-turbo"


async def test_storyboard_chains_last_frame_and_concats(ws, monkeypatch):
    frames, joined = [], []
    monkeypatch.setattr(wavespeed, "_last_frame", lambda src, out: (frames.append(src), wavespeed._write(out, b"png")))
    monkeypatch.setattr(wavespeed, "_concat", lambda paths, out: (joined.extend(paths), wavespeed._write(out, b"mp4")))
    scenes = [{"prompt": "a", "duration": 3}, {"prompt": "b", "duration": 4}, {"prompt": "c", "duration": 3}]
    group = await wavespeed.submit({"feature": "text_to_video", "prompt": "x", "scenes": scenes})
    for _ in range(10):
        hist = (await wavespeed.poll(group))[f"ws:{group}"]
        if hist["status"]["completed"]:
            break
    assert hist["status"]["status_str"] == "completed"
    models = [m for m, _ in ws["submits"]]
    assert models == ["wavespeed-ai/minimax-h3/text-to-video"] + ["wavespeed-ai/minimax-h3/image-to-video"] * 2
    assert [p["prompt"] for _, p in ws["submits"]] == ["a", "b", "c"]
    assert all(p["image"].startswith("https://cdn.test/") for _, p in ws["submits"][1:])
    assert len(frames) == 2 and len(joined) == 3
    assert hist["outputs"]["ws"]["images"][0]["filename"].endswith("_storyboard.mp4")


async def test_storyboard_confirms_total_price(ws):
    scenes = [{"prompt": str(i), "duration": 3} for i in range(13)]  # 13 x $0.04 = $0.52
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_video", "prompt": "x", "scenes": scenes})
    assert e.value.status == 409 and e.value.confirm == 0.52 and not ws["submits"]


def test_last_frame_and_concat_with_ffmpeg(tmp_path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    clips = []
    for i, color in enumerate(["red", "blue"]):
        out = tmp_path / f"c{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color={color}:s=64x64:d=0.5:r=10", "-pix_fmt", "yuv420p", str(out)], check=True)
        clips.append(str(out))
    wavespeed._last_frame(clips[0], str(tmp_path / "last.png"))
    assert (tmp_path / "last.png").stat().st_size > 0
    wavespeed._concat(clips, str(tmp_path / "all.mp4"))
    import av
    with av.open(str(tmp_path / "all.mp4")) as box:
        assert sum(1 for _ in box.decode(video=0)) == 9  # 5 + 5 - dropped first frame of clip 2


async def test_caption_route(ws, bot_client, fresh_user_dir):
    path = fresh_user_dir / "input" / "pic.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    ws["outputs"] = ["a red bicycle"]
    res = await bot_client.post("/comfyart/wavespeed/caption", json={"src": "/api/view?filename=pic.png&subfolder=&type=input"})
    assert res.status == 200, await res.text()
    assert (await res.json())["text"] == "a red bicycle"
    assert ws["submits"][0][0] == "wavespeed-ai/image-captioner"


async def test_llm_complete_uses_openai_compatible_endpoint(bot_client, monkeypatch):
    from conftest import write_settings
    seen = {}
    app = web.Application()

    async def models(request):
        return web.json_response({"data": [{"id": "my-model"}]})

    async def chat(request):
        seen.update(await request.json())
        seen["auth"] = request.headers.get("Authorization")
        return web.json_response({"choices": [{"message": {"content": "hello there"}}]})

    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", chat)
    server = TestServer(app)
    await server.start_server()
    try:
        write_settings(**{"enable-mcp": True, "enable-bot": True, "bot-local-llm-url": str(server.make_url("/v1"))})
        monkeypatch.setenv("COMFYART_LOCAL_LLM_API_KEY", "llm-test")
        res = await bot_client.post("/comfyart/llm/complete", json={"text": "hi", "system": "be brief", "images": []})
        assert res.status == 200, await res.text()
        assert (await res.json())["text"] == "hello there"
        assert seen["model"] == "my-model" and seen["messages"][0] == {"role": "system", "content": "be brief"} and seen["auth"] == "Bearer llm-test"
    finally:
        await server.close()
