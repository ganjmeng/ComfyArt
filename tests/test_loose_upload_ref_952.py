"""#952: a chat-uploaded image is exposed as loose:N; generate_image must accept that id.

The model is told to use shape id loose:0 as a generation ref, but the page only
resolves canvas shape ids and URLs. The server rewrites loose:N to the upload's
file URL (from the chat display block) before the command is relayed, so the
mock generate call receives the file. $0: submit_command and run approval are
mocked; no WaveSpeed, no Playwright.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from ComfyArt.api import chat_store, paid_guard
from ComfyArt.api.bot_turns import loose_src_map, resolve_loose_ref, resolve_loose_refs
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID

UPLOAD_URL = "/api/view?filename=chat-upload-952.png&type=input"
UPLOAD_URL_1 = "/api/view?filename=chat-upload-952-b.png&type=input"

SENT: list = []


@pytest.fixture(autouse=True)
def _clean_paid_guard_turns():
    # generate_image's paid wrap may open __noturn__:anonymous (lang=en).
    # Leave it in TURNS and later ask-card tests pick up English placeholders.
    before = set(paid_guard.TURNS)
    yield
    for k in list(paid_guard.TURNS):
        if k not in before:
            paid_guard.TURNS.pop(k, None)


@pytest.fixture
def relay(monkeypatch):
    SENT.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args), chat))
        return {"ids": ["shape:gen952"], "submitted": True, "model": args.get("edit_model") or args.get("model") or "mock"}

    async def approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", approval)


def _chat_with_uploads(*urls_and_ids):
    """One user message with image display blocks (shape + url), as api/bot.py writes them."""
    chat = chat_store.create_chat(user="default", project="p952", provider="local-llm")
    blocks = []
    for shape, url, name in urls_and_ids:
        blocks.append({"type": "image", "url": url, "shape": shape, "name": name})
    blocks.append({"type": "text", "text": "用这张图做前后对比"})
    chat_store.create_message(chat_id=chat["id"], role="user", blocks=blocks)
    return chat


def _run(chat_id, args):
    token = BOT_CHAT_ID.set(chat_id)

    async def go():
        return await canvas.TOOLS["generate_image"]["handler"](dict(args))

    try:
        return asyncio.run(go())
    finally:
        BOT_CHAT_ID.reset(token)


def test_loose_src_map_latest_message_wins():
    chat = _chat_with_uploads(("loose:0", UPLOAD_URL, "a.png"))
    chat_store.create_message(
        chat_id=chat["id"], role="user",
        blocks=[{"type": "image", "url": UPLOAD_URL_1, "shape": "loose:0", "name": "b.png"}],
    )
    assert loose_src_map(chat["id"]) == {"loose:0": UPLOAD_URL_1}
    assert loose_src_map("") == {}


def test_resolve_loose_ref_unknown_index_errors():
    with pytest.raises(ValueError, match=r'no loose upload "loose:9"'):
        resolve_loose_ref("loose:9", {"loose:0": UPLOAD_URL})
    assert resolve_loose_ref("loose:0", {"loose:0": UPLOAD_URL}) == UPLOAD_URL
    assert resolve_loose_ref("shape:abc", {"loose:0": UPLOAD_URL}) == "shape:abc"
    assert resolve_loose_ref(UPLOAD_URL, {}) == UPLOAD_URL


def test_resolve_loose_refs_rewrites_generate_fields():
    chat = _chat_with_uploads(("loose:0", UPLOAD_URL, "a.png"), ("loose:1", UPLOAD_URL_1, "b.png"))
    out = resolve_loose_refs(
        {"prompt": "p", "refs": ["loose:0", "shape:canvas"], "base": "loose:1"},
        chat["id"],
    )
    assert out["refs"] == [UPLOAD_URL, "shape:canvas"]
    assert out["base"] == UPLOAD_URL_1
    assert out["prompt"] == "p"


def test_generate_image_loose_0_reaches_mock_generate_as_upload_url(relay):
    """The id the model is given (loose:0) is resolved to the upload file on the generate call."""
    chat = _chat_with_uploads(("loose:0", UPLOAD_URL, "photo.png"))
    result = _run(chat["id"], {"prompt": "before after card from the attached photo", "refs": ["loose:0"]})
    assert SENT, result
    action, args, passed_chat = SENT[0]
    assert action == "generate_image"
    assert args["refs"] == [UPLOAD_URL]
    assert "loose:0" not in json.dumps(args)
    assert passed_chat == chat["id"]
    assert result.get("submitted") is True
    assert result.get("ids") == ["shape:gen952"]


def test_generate_image_unknown_loose_index_is_refused(relay):
    chat = _chat_with_uploads(("loose:0", UPLOAD_URL, "photo.png"))
    result = _run(chat["id"], {"prompt": "p", "refs": ["loose:9"]})
    assert SENT == []
    assert result["submitted"] is False
    assert result["generation_succeeded"] is False
    assert result["error"] == 'no loose upload "loose:9"'


def test_generate_image_unknown_loose_index_without_chat_is_refused(relay):
    result = _run("", {"prompt": "p", "refs": ["loose:0"]})
    assert SENT == []
    assert result["submitted"] is False
    assert result["error"] == 'no loose upload "loose:0"'
