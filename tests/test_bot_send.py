from __future__ import annotations

import zipfile

import av
import pytest
from PIL import Image

from ComfyArt.api import bot_send
from ComfyArt.api.bot_media import video_frames, view_path


def _image(base, name="a.png"):
    folder = base / "output" / "comfyart"
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2048, 1024), (200, 10, 10)).save(folder / name)
    return f"/api/view?filename={name}&subfolder=comfyart&type=output"


def test_parse_refs_and_kits_validate_shapes():
    assert bot_send.parse_refs([{"src": "/v", "id": "shape:a"}])[0]["kind"] == "image"
    with pytest.raises(ValueError):
        bot_send.parse_refs([{"id": "shape:a"}])
    with pytest.raises(ValueError):
        bot_send.parse_kits([{"name": "k", "images": [1]}])


def test_view_path_stays_inside_the_folder(fresh_user_dir):
    _image(fresh_user_dir)
    with pytest.raises(ValueError):
        view_path("/api/view?filename=../../secret.txt&type=output")
    with pytest.raises(ValueError):
        view_path("/api/view?filename=a.png&type=models")


async def test_attachments_are_downscaled_and_bad_kit_images_skipped(fresh_user_dir):
    src = _image(fresh_user_dir)
    refs = bot_send.parse_refs([{"src": src, "id": "shape:a", "name": "poster-differentiated-compiler"}])
    kits = bot_send.parse_kits([{"name": "Brand", "description": "Brand kit", "images": [src, "/api/view?filename=missing.png&type=output"]}])
    attachments, lines = await bot_send.prepare_attachments(refs, kits)
    assert len(attachments) == 2 and attachments[0]["media_type"] == "image/jpeg"
    assert "shape id shape:a" in lines[0]
    assert "could not be attached" in lines[-1]


async def test_a_missing_canvas_ref_is_an_error(fresh_user_dir):
    with pytest.raises(ValueError):
        await bot_send.prepare_attachments(bot_send.parse_refs([{"src": "/api/view?filename=nope.png&type=output"}]), [])


def _video(base, name="clip.mp4", seconds=2, fps=10):
    folder = base / "output" / "comfyart"
    folder.mkdir(parents=True, exist_ok=True)
    with av.open(str(folder / name), "w") as out:
        stream = out.add_stream("mpeg4", rate=fps)
        stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
        for i in range(seconds * fps):
            frame = av.VideoFrame.from_image(Image.new("RGB", (64, 48), (i * 10 % 255, 0, 0)))
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return f"/api/view?filename={name}&subfolder=comfyart&type=output"


def _docx(base, name="brief.docx"):
    folder = base / "input"
    folder.mkdir(parents=True, exist_ok=True)
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = (f'<w:document xmlns:w="{w}"><w:body>'
            '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Spring launch</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Use warm </w:t></w:r><w:r><w:t>colors.</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(folder / name, "w") as z:
        z.writestr("word/document.xml", body)
    return f"/api/view?filename={name}&type=input"


async def test_audio_refs_send_their_transcript_and_no_picture(fresh_user_dir):
    refs = bot_send.parse_refs([{"src": "/api/view?filename=v.mp3&type=input", "id": "shape:s", "kind": "audio", "transcript": "hello there"}])
    attachments, lines = await bot_send.prepare_attachments(refs, [])
    assert attachments == []
    assert 'Transcript: "hello there"' in lines[0] and "reference_audios" in lines[0]


async def test_video_refs_attach_a_frame_sheet(fresh_user_dir):
    src = _video(fresh_user_dir)
    attachments, lines = await bot_send.prepare_attachments(bot_send.parse_refs([{"src": src, "kind": "video"}]), [])
    assert len(attachments) == 1 and "view_video" in lines[0]
    frames, duration = video_frames(view_path(src), 4)
    assert len(frames) == 4 and 1.5 < duration <= 2.1
    assert [round(at, 2) for at, _ in frames] == [round(duration * (i + 0.5) / 4, 2) for i in range(4)]


async def test_documents_send_their_text(fresh_user_dir):
    src = _docx(fresh_user_dir)
    docs = bot_send.parse_docs([{"src": src, "name": "brief.docx"}])
    attachments, lines = await bot_send.prepare_attachments([], [], docs)
    assert attachments == []
    assert "# Spring launch\nUse warm colors." in lines[0] and 'Attached document "brief.docx"' in lines[0]
    with pytest.raises(ValueError):
        bot_send.parse_docs([{"name": "x"}])


def _png_ihdr(width: int, height: int) -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def _view_file(base, name: str, data: bytes, kind: str = "input") -> str:
    folder = base / kind
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    return f"/api/view?filename={name}&type={kind}"


async def test_chat_send_downscales_a_16384_jpeg_into_the_llm_request(fresh_user_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("COMFYART_LLM_USD_GATE", "1")
    """The chat attachment path drafts the JPEG, then the planner request carries that copy."""
    import base64
    import io

    from PIL import Image

    from ComfyArt.api import provider_admin
    from ComfyArt.bot.local_llm import LocalLlmProvider
    from ComfyArt.bot.providers import TurnHandle, TurnRequest
    from test_llm_usd_gate import _route

    frame = Image.new("RGB", (16384, 12288), (30, 60, 90))
    blob = io.BytesIO()
    frame.save(blob, format="JPEG", quality=20)
    del frame
    src = _view_file(fresh_user_dir, "wide.jpg", blob.getvalue())
    attachments, _lines = await bot_send.prepare_attachments(
        bot_send.parse_refs([{"src": src, "id": "shape:wide"}]), [])
    assert attachments[0]["media_type"] == "image/jpeg"
    with Image.open(io.BytesIO(base64.b64decode(attachments[0]["data"]))) as sent:
        assert max(sent.size) <= 1568

    posted = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        if str(url).endswith("/chat/completions"):
            posted.append(json_body)
            return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        if (json_body or {}).get("method") == "tools/list":
            return {"result": {"tools": []}}
        return {"data": [{"id": "deepseek-flash", "context_length": 1000000}]}

    provider = LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")

    async def _request_json(session, method, url, *, headers, json_body=None, timeout=120):
        return await provider_admin.gated_llm_http(
            session, method, url, headers=headers, json_body=json_body, timeout=timeout,
            transport=transport, ledger_path=str(tmp_path / "send.json"), bound_fn=None)

    provider._request_json = _request_json
    provider._run_store = lambda: None

    async def _emit(_event):
        return None

    token = provider_admin._llm_lock.set(_route())
    try:
        result = await provider.send(TurnRequest(
            chat_id="send-wide", user_text="look", lang="en", model="deepseek-flash",
            mcp_endpoint="http://mock-no-network/mcp", project_id="local",
            attachments=attachments), _emit, TurnHandle())
    finally:
        provider_admin._llm_lock.reset(token)
    assert not result.error, result.error
    assert posted
    url = posted[0]["messages"][-1]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    with Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))) as im:
        assert max(im.size) <= 1568


async def _chat(client, provider="fake-test"):
    resp = await client.post("/comfyart/bot/chats", json={"project": "p", "provider": provider})
    assert resp.status == 200, await resp.text()
    return (await resp.json())["chat"]


async def test_chat_send_still_accepts_a_4000_png(fresh_user_dir):
    import base64
    import io

    from PIL import Image

    frame = Image.new("RGB", (4000, 4000), (200, 10, 10))
    blob = io.BytesIO()
    frame.save(blob, format="PNG")
    src = _view_file(fresh_user_dir, "fourk.png", blob.getvalue())
    attachments, _lines = await bot_send.prepare_attachments(
        bot_send.parse_refs([{"src": src}]), [])
    assert attachments[0]["media_type"] == "image/jpeg"
    with Image.open(io.BytesIO(base64.b64decode(attachments[0]["data"]))) as im:
        assert max(im.size) <= 1568


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_header_only_png_and_remote_url_are_unreadable(bot_client, fake_provider, fresh_user_dir, lang):
    from conftest import write_settings
    from ComfyArt.bot.llm_usd_gate import official_input_bound, price_snapshot, user_notice
    import base64

    write_settings(**{"enable-mcp": True, "enable-bot": True})

    raw = _png_ihdr(12000, 9000)
    src = _view_file(fresh_user_dir, f"hdr-{lang}.png", raw)
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode()
    bound = official_input_bound(
        {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "look"},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]}]},
        price_snapshot("deepseek-flash"),
    )
    assert bound.code == "unbounded_multimodal"

    header = await bot_client.post(
        f"/comfyart/bot/chats/{(await _chat(bot_client))['id']}/send",
        json={"text": "look", "lang": lang, "refs": [{"src": src}]})
    assert header.status == 400
    assert (await header.json())["error"] == user_notice("unbounded_multimodal", lang)
    assert fake_provider.last_turn is None

    remote = await bot_client.post(
        f"/comfyart/bot/chats/{(await _chat(bot_client))['id']}/send",
        json={"text": "look", "lang": lang, "refs": [{"src": "https://example.com/photo.png"}]})
    assert remote.status == 400
    body = await remote.json()
    assert body["error"] == user_notice("unbounded_multimodal", lang)
    assert "not a ComfyUI file URL" not in body["error"]
    assert "这次生成没有完成" not in body["error"]
    assert fake_provider.last_turn is None


async def test_declared_over_250mp_chat_ref_is_too_large_with_zero_posts(bot_client, fake_provider, fresh_user_dir):
    from conftest import write_settings
    from ComfyArt.bot.llm_usd_gate import user_notice

    write_settings(**{"enable-mcp": True, "enable-bot": True})

    src = _view_file(fresh_user_dir, "huge.png", _png_ihdr(20000, 15000))
    chat = await _chat(bot_client)
    resp = await bot_client.post(
        f"/comfyart/bot/chats/{chat['id']}/send",
        json={"text": "look", "lang": "zh", "refs": [{"src": src}]})
    assert resp.status == 400
    assert (await resp.json())["error"] == user_notice("image_too_large", "zh")
    assert fake_provider.last_turn is None


def test_compose_puts_memory_first_and_skill_instruction_before_the_text():
    text = bot_send.compose_provider_text("make it", skill_name="Poster", memory="MEM", lines=["[ref]"])
    assert text.startswith("MEM\n\nUse the ComfyArt skill 'Poster'")
    assert text.endswith("make it\n\n[ref]")
