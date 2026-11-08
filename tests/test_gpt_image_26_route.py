"""#825 phase 2: the constructed provider request, not just the default string.

Local stand-in only. The session never opens a socket. No paid submit.
"""
import asyncio
import json
from pathlib import Path

import pytest

from ComfyArt.api import gif_image, wavespeed

T2I = "openai/gpt-image-2.6-flare/text-to-image"
EDIT = "openai/gpt-image-2.6-flare/edit"
T2I_25 = "openai/gpt-image-2.5-flare/text-to-image"
EDIT_25 = "openai/gpt-image-2.5-flare/edit"
CATALOG = json.loads((Path(__file__).resolve().parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())


class _Body:
    def __init__(self, payload, status=200):
        self.status = status
        self._payload = payload

    async def json(self, content_type=None):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _Session:
    posts: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def post(self, url, json=None, **kwargs):
        _Session.posts.append((str(url), json))
        if str(url).endswith("/model/price"):
            return _Body({"data": {"price": 0.05, "discounted_price": 0.05}})
        return _Body({"data": {"id": "local-task", "status": "created"}})

    def get(self, *args, **kwargs):
        raise AssertionError("phase 2 route test must not GET a provider")


@pytest.fixture
def local(monkeypatch):
    _Session.posts = []
    monkeypatch.setenv("WAVESPEED_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(wavespeed, "_headers", lambda: {"Authorization": "Bearer test"})

    async def catalog(refresh=False):
        return CATALOG

    monkeypatch.setattr(wavespeed, "catalog", catalog)
    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", _Session)
    wavespeed._quotes.clear()
    return _Session


def _gen(posts):
    return [(url, body) for url, body in posts if not str(url).endswith("/model/price")]


def _price(posts):
    return [(url, body) for url, body in posts if str(url).endswith("/model/price")]


def test_unset_and_auto_post_26_without_quality(local):
    for feature, model in (("text_to_image", T2I), ("image_edit", EDIT)):
        _Session.posts = []
        inputs = {"feature": feature, "prompt": "a red cup"}
        if feature == "image_edit":
            inputs["images"] = ["https://cdn.test/still.png"]
        task = asyncio.run(wavespeed.submit(inputs))
        assert task == "local-task"
        url, body = _gen(_Session.posts)[-1]
        assert url.endswith("/" + model)
        assert body["prompt"] == "a red cup"
        assert "quality" not in body
        assert "complexity" not in body
        if feature == "image_edit":
            assert body["images"] == ["https://cdn.test/still.png"]
        quote = _price(_Session.posts)[-1][1]
        assert quote["model_id"] == model
        assert "quality" not in quote["inputs"]
        assert "frame_count" not in quote["inputs"]
    _Session.posts = []
    asyncio.run(wavespeed.submit({"feature": "text_to_image", "model": "auto", "prompt": "auto cup"}))
    url, body = _gen(_Session.posts)[-1]
    assert url.endswith("/" + T2I) and "quality" not in body


def test_explicit_25_stays_on_25_and_still_omits_quality(local):
    asyncio.run(wavespeed.submit({"feature": "text_to_image", "model": T2I_25, "prompt": "rollback"}))
    url, body = _gen(_Session.posts)[-1]
    assert url.endswith("/" + T2I_25)
    assert "quality" not in body and "2.6" not in url
    asyncio.run(wavespeed.submit({"feature": "image_edit", "model": EDIT_25, "prompt": "rollback", "images": ["https://cdn.test/still.png"]}))
    url, body = _gen(_Session.posts)[-1]
    assert url.endswith("/" + EDIT_25)
    assert body["images"] == ["https://cdn.test/still.png"] and "quality" not in body


def test_explicit_quality_is_sent_and_unset_is_not(local):
    asyncio.run(wavespeed.submit({"feature": "text_to_image", "prompt": "tier", "params": {"quality": "high"}}))
    url, body = _gen(_Session.posts)[-1]
    assert url.endswith("/" + T2I) and body["quality"] == "high"
    asyncio.run(wavespeed.submit({"feature": "text_to_image", "prompt": "no tier"}))
    assert "quality" not in _gen(_Session.posts)[-1][1]


def test_gif_stays_26_t2i_and_still_reference_is_not_a_video(local):
    asyncio.run(wavespeed.submit({"feature": "text_to_image", "prompt": "做成动图"}))
    url, body = _gen(_Session.posts)[-1]
    assert url.endswith("/" + T2I)
    assert "video" not in url and "/edit" not in url
    assert body["output_format"] == "gif" and body["frame_count"] == 9 and body["frame_duration_ms"] == 200
    assert "quality" not in body
    assert "frame_count" not in _price(_Session.posts)[-1][1]["inputs"]
    asyncio.run(wavespeed.submit({
        "feature": "image_edit", "model": EDIT_25, "image": "https://cdn.test/still.png",
        "prompt": "把这张做成动图", "output_format": "gif",
    }))
    url, body = _gen(_Session.posts)[-1]
    assert url.endswith("/" + T2I)
    assert "video" not in url and not url.endswith("/edit")
    assert body["output_format"] == "gif" and "quality" not in body


def test_quote_and_confirm_name_the_same_model_as_submit(local, monkeypatch):
    est = asyncio.run(wavespeed.estimate({"feature": "text_to_image", "prompt": "a cup"}))
    assert est["model"] == T2I and est["price"] == 0.05 and "quality" not in str(est.get("tier") or "")
    edit = asyncio.run(wavespeed.estimate({"feature": "image_edit", "model": "auto", "prompt": "换背景", "images": ["https://cdn.test/still.png"]}))
    assert edit["model"] == EDIT
    gif = asyncio.run(wavespeed.estimate({"feature": "image_edit", "image": "https://cdn.test/still.png", "prompt": "做成动图"}))
    assert gif["model"] == T2I and gif["gif_route"] == "reference_t2i"
    assert "编辑模型没有 gif" in gif["gif_note"] and "does not use a video model" in gif["gif_note"]
    assert "GIF" in gif["tier"]
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0)
    with pytest.raises(wavespeed.WaveSpeedError) as err:
        asyncio.run(wavespeed.submit({"feature": "image_edit", "image": "https://cdn.test/still.png", "prompt": "做成动图"}))
    assert err.value.status == 409 and err.value.model == T2I
    assert "quality" not in (err.value.tier or "")
    body = wavespeed._respond_error(err.value)
    payload = json.loads(body.body)
    assert payload["error"]["model"] == T2I
    assert "编辑模型没有 gif" in payload["error"]["gif_note"]
    assert _gen(_Session.posts) == []  # confirm stops before the provider POST


# Official request fields, read 2026-11-08 from
# https://wavespeed.ai/docs/docs-api/openai/openai-gpt-image-2.6-flare-text-to-image
# plus the two global options that page names. No image, images, or reference field.
OFFICIAL_T2I_FIELDS = {
    "prompt", "aspect_ratio", "resolution", "quality", "complexity", "output_format",
    "frame_count", "frame_duration_ms", "enable_sync_mode", "enable_base64_output",
}


def test_committed_fixture_matches_official_t2i_fields_and_post_drops_still_url(local):
    props = set(CATALOG[T2I]["api_schema"]["api_schemas"][0]["request_schema"]["properties"])
    assert props <= OFFICIAL_T2I_FIELDS
    assert not ({"image", "images", "reference_image", "refs"} & props)
    still = "https://cdn.test/user-still.png"
    asyncio.run(wavespeed.submit({
        "feature": "image_edit", "image": still, "prompt": "把这张做成动图", "output_format": "gif", "frame_count": 99,
    }))
    url, body = _gen(_Session.posts)[-1]
    assert url.endswith("/" + T2I) and "video" not in url
    blob = json.dumps(body)
    assert still not in blob
    assert body["output_format"] == "gif" and body["frame_count"] == 16
    est = asyncio.run(wavespeed.estimate({
        "feature": "image_edit", "image": still, "prompt": "把这张做成动图", "output_format": "gif", "frame_count": 99,
    }))
    assert est["gif"]["frame_count"] == 16 and "16f" in est["tier"]
    assert "不会送进请求" in est["gif_note"] and "not sent" in est["gif_note"]
    assert "不会改走视频" in est["gif_note"] or "does not use a video model" in est["gif_note"]


def test_clamped_frame_count_matches_across_quote_confirm_and_post(local, monkeypatch):
    job = {"feature": "text_to_image", "prompt": "loop", "params": {"output_format": "gif", "frame_count": 99, "frame_duration_ms": 5}}
    est = asyncio.run(wavespeed.estimate(dict(job)))
    assert est["gif"]["frame_count"] == 16 and est["gif"]["frame_duration_ms"] == 20
    assert "16f" in est["tier"] and "20ms" in est["tier"]
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0)
    with pytest.raises(wavespeed.WaveSpeedError) as err:
        asyncio.run(wavespeed.submit(dict(job)))
    assert err.value.status == 409 and "16f" in err.value.tier and "20ms" in err.value.tier
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0.5)
    _Session.posts = []
    task = asyncio.run(wavespeed.submit(dict(job)))
    assert task == "local-task"
    body = _gen(_Session.posts)[-1][1]
    assert body["frame_count"] == 16 and body["frame_duration_ms"] == 20
    low = {"feature": "text_to_image", "prompt": "loop", "params": {"output_format": "gif", "frame_count": 1}}
    assert asyncio.run(wavespeed.submit(low)) == "local-task"
    assert _gen(_Session.posts)[-1][1]["frame_count"] == 2


def test_gif_copy_names_26_as_the_unnamed_model():
    from ComfyArt.api.mcp_tools import canvas
    banned = (
        "默认模型仍是 GPT Image 2.5",
        "default model stays GPT Image 2.5",
        "stable 2.5 default",
        "stable default stays 2.5",
    )
    blobs = [
        gif_image.note_line("text_to_image"),
        gif_image.note_line("reference_t2i"),
        canvas.SPECS["generate_image"]["description"],
    ]
    for blob in blobs:
        for bad in banned:
            assert bad not in blob, bad
        assert "2.6" in blob
    desc = canvas.SPECS["generate_image"]["description"]
    assert "image default" in desc
    assert "no reference-image field" in desc


def test_picked_quality_confirm_tier_matches_payload(local, monkeypatch):
    monkeypatch.setattr(wavespeed, "confirm_usd", lambda: 0)
    with pytest.raises(wavespeed.WaveSpeedError) as err:
        asyncio.run(wavespeed.submit({"feature": "text_to_image", "model": T2I_25, "prompt": "x", "params": {"quality": "high"}}))
    assert err.value.model == T2I_25
    quoted = _price(_Session.posts)[-1][1]
    assert quoted["model_id"] == T2I_25 and quoted["inputs"].get("quality") == "high"
    assert gif_image.documented_usd(T2I) == 0.05
    assert gif_image.documented_usd(T2I_25) == 0.024
