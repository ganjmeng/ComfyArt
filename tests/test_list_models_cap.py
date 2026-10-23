"""list_models must fit the agent's tool-result cap (#72: the 44 KB list was cut at 4000 chars,
so the agent never saw video ids and guessed ~20 times). Mock catalog only, no WaveSpeed calls."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from ComfyArt.api import wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot._cli_common import TOOL_RESULT_CAP
from ComfyArt.bot.local_llm import LocalLlmProvider
from ComfyArt.bot.providers import TurnHandle, TurnRequest

# trimmed copy of the real /api/v3/models entries for every curated id (name, price, enums only)
FIXTURE = Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json"


@pytest.fixture(autouse=True)
def mock_catalog(monkeypatch):
    models = json.loads(FIXTURE.read_text())

    async def fake_catalog(refresh=False):
        return models
    monkeypatch.setattr(wavespeed, "catalog", fake_catalog)
    monkeypatch.setattr(canvas, "grouped_models", wavespeed.grouped_models)


def _text(payload) -> str:  # what api/mcp.py sends back to the agent
    return json.dumps(payload, ensure_ascii=False, default=str)


def _ids(feature: str) -> list[str]:
    return [m["id"] for m in wavespeed.load_config()["features"][feature]["models"]]


def test_cap_is_unchanged():
    assert TOOL_RESULT_CAP == 4000


async def test_full_list_is_over_the_cap():
    # the old output (every feature with descriptions and inputs) was what got truncated
    old = _text({"features": await wavespeed.grouped_models(), "tool_features": wavespeed.load_config()["tool_features"]})
    assert len(old) > TOOL_RESULT_CAP


@pytest.mark.parametrize("kind", [None, *wavespeed.MODEL_KINDS])
async def test_every_list_models_result_fits_under_cap(kind):
    out = await canvas._list_models({"type": kind} if kind else {})
    assert len(_text(out)) < TOOL_RESULT_CAP


async def test_index_lists_kinds_and_defaults():
    out = await canvas._list_models({})
    f = out["features"]
    assert f["defaults"]["text_to_video"] == "bytedance/seedance-2.0/text-to-video"
    assert "text_to_video" in f["kinds"]["video"] and "image_to_3d" in f["kinds"]["3d"]
    assert "type" in f["hint"]


async def test_video_type_has_every_generate_video_id():
    out = await canvas._list_models({"type": "video"})
    f = out["features"]
    for feature in ("text_to_video", "image_to_video"):
        assert [m["id"] for m in f[feature]["models"]] == _ids(feature)
        assert "generate_video" in f[feature]["tools"]
    assert not any(n in f for n in ("text_to_image", "music"))


async def test_feature_name_as_type_and_bad_type():
    out = await canvas._list_models({"type": "text_to_video"})
    assert list(out["features"]) == ["text_to_video"]
    with pytest.raises(wavespeed.WaveSpeedError, match="unknown type"):
        await canvas._list_models({"type": "hologram"})


def test_unknown_model_error_lists_valid_ids():
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        wavespeed.resolve_model("image_to_video", "kling-guess")
    msg = str(e.value)
    assert "kling-guess" in msg and all(i in msg for i in _ids("image_to_video"))
    assert "default bytedance/seedance-2.0/image-to-video" in msg


async def test_agent_loop_sees_untruncated_video_ids(monkeypatch):
    """Local LLM loop: list_models(type=video) reaches the model whole and the id it picks next is valid."""
    provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
    sent: list[dict] = []
    replies = [
        {"choices": [{"message": {"content": "", "tool_calls": [
            {"id": "t1", "function": {"name": "list_models", "arguments": '{"type": "video"}'}}]}}]},
        {"choices": [{"message": {"content": "done", "tool_calls": []}}]},
    ]

    async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
        if url.endswith("/chat/completions"):
            sent.append(json_body)
            return replies.pop(0)
        return {"result": {"tools": [{"name": "list_models"}]}}

    async def fake_call(session, endpoint, name, arguments):
        return _text(await canvas.TOOLS[name]["handler"](arguments)), []

    monkeypatch.setattr(provider, "_request_json", fake_request)
    monkeypatch.setattr(provider, "_mcp_call_tool", fake_call)
    events = []

    async def emit(ev):
        events.append(ev)
    result = await provider.send(TurnRequest(chat_id="c", user_text="做个视频", mcp_endpoint="http://x/mcp", model="m"),
                                 emit, TurnHandle())
    assert result.error == ""
    tool_msg = next(m for m in sent[1]["messages"] if m.get("role") == "tool")
    assert "truncated" not in tool_msg["content"]
    seen = json.loads(tool_msg["content"])["features"]
    for i in _ids("text_to_video") + _ids("image_to_video"):
        assert i in tool_msg["content"]
    assert wavespeed.resolve_model("image_to_video", seen["image_to_video"]["models"][-1]["id"])
