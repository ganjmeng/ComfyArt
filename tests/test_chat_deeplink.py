"""Deep link chat read: server checks project access and chat.project before any transcript."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ComfyArt.api import chat_store, project_store

ROOT = Path(__file__).resolve().parent.parent
SECRET = "OTHER_PROJECT_SECRET"
HIDDEN = '{"error": "chat not found"}'


def _owns(user: str, project_id: str) -> None:
    project_store.save_project(user, project_id, "{}", project_id, [])


async def _text(resp) -> str:
    return await resp.text()


async def test_chat_read_hides_unknown_unauthorized_and_mismatched(bot_client, fake_provider):
    _owns("default", "proj-a")
    _owns("default", "proj-b")
    _owns("alice", "proj-alice")
    created = await bot_client.post("/comfyart/bot/chats", json={"project": "proj-a", "provider": "fake-test"})
    assert created.status == 200
    chat = (await created.json())["chat"]
    chat_store.create_message(chat_id=chat["id"], role="user", blocks=[{"type": "text", "text": SECRET}])
    orphan = chat_store.create_chat(user="default", project="proj-alice", provider="fake-test", title="orphan-title")
    chat_store.create_message(chat_id=orphan["id"], role="user", blocks=[{"type": "text", "text": SECRET}])

    newer = await bot_client.post("/comfyart/bot/chats", json={"project": "proj-a", "provider": "fake-test", "title": "newer-chat"})
    assert newer.status == 200
    latest = (await newer.json())["chat"]
    chat_store.create_message(chat_id=latest["id"], role="user", blocks=[{"type": "text", "text": "LATEST_OTHER_CHAT"}])

    ok = await bot_client.get(f"/comfyart/bot/chats/{chat['id']}?project=proj-a")
    assert ok.status == 200
    body = await ok.json()
    assert body["chat"]["id"] == chat["id"]
    assert body["chat"]["project"] == "proj-a"
    assert SECRET in json.dumps(body)
    assert "LATEST_OTHER_CHAT" not in json.dumps(body)

    unknown = await bot_client.get("/comfyart/bot/chats/does-not-exist?project=proj-a")
    mismatch = await bot_client.get(f"/comfyart/bot/chats/{chat['id']}?project=proj-b")
    unauthorized = await bot_client.get(f"/comfyart/bot/chats/{orphan['id']}?project=proj-alice")
    invalid_project = await bot_client.get(f"/comfyart/bot/chats/{chat['id']}?project=no-such-project")
    missing_project = await bot_client.get(f"/comfyart/bot/chats/{chat['id']}")
    texts = []
    for resp in (unknown, mismatch, unauthorized, invalid_project, missing_project):
        assert resp.status == 404
        text = await _text(resp)
        texts.append(text)
        assert text == HIDDEN
        assert SECRET not in text
        assert "orphan-title" not in text
        assert "messages" not in text
        assert json.loads(text) == {"error": "chat not found"}
    assert len(set(texts)) == 1


def _trace_path(tmp_path: Path) -> Path:
    """Writable trace file. COMFYART_CHATLINK_TRACE overrides; otherwise pytest's tmp_path."""
    override = os.environ.get("COMFYART_CHATLINK_TRACE", "").strip()
    return Path(override) if override else tmp_path / "startbot-chain-trace.txt"


def test_startbot_refresh_finally_does_not_reopen_a_cancelled_init(tmp_path):
    """Real startBot: deferred refreshBot, then cleanup or a later link, then the old refresh resolves."""
    out = tmp_path / "chatlink-chain.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/chatlink/rolldown.chain.mjs"],
        cwd=ROOT, check=True, env={**os.environ, "OUT": str(out)},
    )
    proc = subprocess.run(["node", str(out)], cwd=ROOT, check=True, capture_output=True, text=True)
    trace = _trace_path(tmp_path)
    trace.write_text(proc.stdout + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else ""), encoding="utf-8")
    lines = [line for line in proc.stdout.splitlines() if line]
    assert lines[-1] == "ok", proc.stdout + proc.stderr
    for case in ("ok chain-cleanup-then-refresh", "ok chain-A-finishes-after-B", "ok chain-no-chat"):
        assert case in lines, proc.stdout
    assert "trace mark switch-after-B-refresh selected=B" in proc.stdout
    assert "trace mark switch-after-A-finish selected=B" in proc.stdout
    assert "trace mark cleanup-after-old-refresh selected=null" in proc.stdout
    assert "selected=A" not in proc.stdout, proc.stdout
    assert "/comfyart/bot/chats/A?" not in proc.stdout, proc.stdout


def test_chat_link_parser_and_stale_reads(tmp_path):
    out = tmp_path / "chatlink-deeplink.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/chatlink/rolldown.config.mjs"],
        cwd=ROOT, check=True, env={**os.environ, "OUT": str(out)},
    )
    proc = subprocess.run(["node", str(out)], cwd=ROOT, check=True, capture_output=True, text=True)
    lines = [line for line in proc.stdout.splitlines() if line]
    assert lines[-1] == "ok", proc.stdout
    for case in ("ok cleanup-then-finish", "ok A-finishes-after-B", "ok no-chat", "ok url-A-to-B"):
        assert case in lines, proc.stdout
    src = (ROOT / "src/bot.ts").read_text(encoding="utf-8")
    assert "settleBotInit(" in src
    assert "initEpoch.cancel()" in src
    assert "if (chat) void openChat(chat)" in src
    assert "openChat(chats" not in src and "chats[0]" not in src
    assert "void loadChats().then(() => openChat(chatIdAtom.get()))" in src
    assert "chatReads.invalidate()" in src
    assert "chatReadPath(requestedProject, id)" in src
    assert "chatReadStillCurrent" in src
    panel = (ROOT / "src/ui/AgentPanel.tsx").read_text(encoding="utf-8")
    assert "bot.chatOpenFailed" in panel and "returnToCurrentProject" in panel
    home = (ROOT / "src/main.tsx").read_text(encoding="utf-8")
    assert 'chatLink="invalid"' in home
    assert "chatLink={project && chatParam ? 'denied' : undefined}" in home
