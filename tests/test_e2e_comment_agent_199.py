"""#199: browser end-to-end tests (mock only) for the two "comment -> Agent" paths that #195 did not cover.

1. 加入对话 / 添加到对话: a comment (from the comment panel, or all open ones from the comments list) is put into the
   composer draft with its image as a reference; sending it in Agent mode reaches the agent with the note text,
   the comment region and the image attached.
2. 总结全部评论: the comments list sends every open comment straight to the agent with the summarize prompt.

The LLM is the conftest FakeProvider (no model is called) and WaveSpeed is the #195 local mock (only the free
click-select SAM call is made, never an edit): $0, no key. Breakage checks: no edit model is submitted, resolved
comments are not sent, and the region / image travel with the note. Skipped when Playwright + Chromium or dist/
are missing (CI has no Playwright, same as #195); run by hand by QA on the shared machine before merge."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import write_settings
from test_e2e_comment_edit import EDIT, SAM, SOURCE, ZH, _point_comment, _until, app_url, mock_ws  # noqa: F401  (fixtures)

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import pytestmark  # noqa: E402,F401

SHOTS = Path("/tmp/pr199-shots")
REGION = re.compile(r"\[on shape:[^,]+, region x=\d+ y=\d+ w=\d+ h=\d+ of 512×512 px\]")


@pytest.fixture
async def page(app_url, tmp_path, monkeypatch):  # noqa: F811
    """Same page as test_e2e_comment_edit, except the host /ws actually delivers the server's events: the stubbed
    PromptServer only records send_sync, so without this the agent's turn (user message, reply) never reaches the UI."""
    from server import PromptServer
    sockets: list = []
    send_sync = PromptServer.instance.send_sync

    def forward(event, data, sid=None):
        send_sync(event, data, sid)
        for ws in sockets:
            ws.send(json.dumps({"type": event, "data": data}))
    monkeypatch.setattr(PromptServer.instance, "send_sync", forward)
    async with pw.async_playwright() as p:
        try:
            browser = await p.chromium.launch()
        except Exception as e:  # browser binaries not installed
            pytest.skip(f"chromium not available: {e}")
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        await ctx.route_web_socket(re.compile(r"/ws(\?|$)"), lambda ws: sockets.append(ws))
        pg = await ctx.new_page()
        await pg.add_init_script("localStorage.setItem('comfyart.lang','zh')")
        src = tmp_path / "src.png"
        src.write_bytes(SOURCE)
        await pg.goto(app_url)
        await pg.wait_for_timeout(1500)
        await pg.mouse.click(28, 83)  # home: new project
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(1500)
        if await pg.locator(".ca-modal").count():
            await pg.locator(".ca-modal button").nth(-2).click()
        await pg.locator("input[type=file][accept*=image]").first.set_input_files(str(src))
        await pg.locator(".tl-image").first.wait_for()
        await pg.wait_for_timeout(800)
        await pg.keyboard.press("Escape")
        yield pg
        await browser.close()


@pytest.fixture
def fake_agent(fake_provider, monkeypatch):
    """Every chat goes to the fake agent; it answers with one canned delta and records the turn it got."""
    from ComfyArt.bot.providers import BotEvent
    write_settings(**{"bot-provider": fake_provider.id, "enable-bot": True, "enable-mcp": True})
    fake_provider.script = [BotEvent(t="delta", text="收到，已整理评论。")]
    return fake_provider


@pytest.fixture
async def agent_page(fake_agent, page):  # noqa: F811
    SHOTS.mkdir(parents=True, exist_ok=True)
    sends: list[dict] = []

    def on_request(req):
        if req.method == "POST" and re.search(r"/comfyart/bot/chats/[^/]+/send$", req.url):
            sends.append(json.loads(req.post_data or "{}"))
    page.on("request", on_request)
    page.sends = sends
    # the agent list is probed after load; sending before it arrives toasts "no agent available", so wait until the
    # composer's mode button names the fake agent
    await page.locator(".ca-composer").get_by_text(fake_agent.label, exact=True).wait_for(timeout=15000)
    yield page


async def _async(v):
    return v


def _edits(mock_ws):  # noqa: F811
    return [b for m, b in mock_ws["submits"] if m == EDIT]


async def _turn(fake_agent, n=1):
    await _until(lambda: _async(fake_agent.last_turn is not None), 20)
    return fake_agent.last_turn


async def _send_draft(pg):
    box = pg.locator(".ca-composer__input")
    await box.wait_for()
    await box.press("Enter")


async def test_comment_panel_add_to_chat_then_send_to_agent(agent_page, mock_ws, fake_agent):  # noqa: F811
    pg = agent_page
    panel = await _point_comment(pg, mock_ws, "把杯子换成蓝色")
    await panel.get_by_role("button", name=ZH["libraryPanel.addToChat"]).click()
    await pg.keyboard.press("Escape")
    draft = await pg.locator(".ca-composer__input").input_value()
    assert draft.startswith("- 把杯子换成蓝色") and REGION.search(draft), draft  # note + region go into the draft
    await pg.screenshot(path=str(SHOTS / "199-01-add-to-chat-zh.png"))
    await _send_draft(pg)
    await _until(lambda: _async(len(pg.sends) == 1), 15)
    body = pg.sends[0]
    assert "把杯子换成蓝色" in body["text"] and REGION.search(body["text"]), body["text"]
    assert [r["kind"] for r in body["refs"]] == ["image"], body["refs"]  # the commented image is attached as the reference
    turn = await _turn(fake_agent)
    assert "把杯子换成蓝色" in turn.user_text and REGION.search(turn.user_text)
    assert len(turn.attachments) >= 1
    await _until(lambda: _body_has(pg, "收到，已整理评论。"), 15)
    await pg.screenshot(path=str(SHOTS / "199-02-agent-reply-zh.png"))
    assert _edits(mock_ws) == []  # sending to the agent never runs the edit model itself
    assert all(m == SAM for m, _ in mock_ws["submits"])


async def test_comments_list_add_all_to_chat_skips_resolved(agent_page, mock_ws, fake_agent):  # noqa: F811
    pg = agent_page
    await _point_comment(pg, mock_ws, "左上角加一朵云", 0.2, 0.2)
    await pg.keyboard.press("Escape")
    await _point_comment(pg, mock_ws, "右下角加一棵树", 0.8, 0.8)
    await pg.keyboard.press("Escape")
    await _point_comment(pg, mock_ws, "这条已经处理过", 0.5, 0.5)
    await pg.keyboard.press("Escape")
    await pg.locator(f'button[title="{ZH["common.allComments"]}"]').click()
    row = pg.locator(".ca-comment-row").filter(has_text="这条已经处理过")
    await row.hover()  # the row actions only show on hover
    await row.locator(f'button[title="{ZH["commentsList.markAsResolved"]}"]').click()
    add = pg.get_by_role("button", name=ZH["commentsList.addToChat"].replace("{0}", "2"))
    await add.wait_for()
    await add.click()
    draft = await pg.locator(".ca-composer__input").input_value()
    assert "左上角加一朵云" in draft and "右下角加一棵树" in draft and "这条已经处理过" not in draft, draft
    assert len(REGION.findall(draft)) == 2
    await _send_draft(pg)
    await _until(lambda: _async(len(pg.sends) == 1), 15)
    body = pg.sends[0]
    assert len(body["refs"]) == 1  # both notes sit on the same image: it is attached once
    turn = await _turn(fake_agent)
    assert "左上角加一朵云" in turn.user_text and "这条已经处理过" not in turn.user_text
    assert _edits(mock_ws) == []


async def test_comments_list_summarize_sends_straight_to_agent(agent_page, mock_ws, fake_agent):  # noqa: F811
    pg = agent_page
    await _point_comment(pg, mock_ws, "标题字号再大一点", 0.3, 0.3)
    await pg.keyboard.press("Escape")
    await _point_comment(pg, mock_ws, "背景换成米色", 0.7, 0.7)
    await pg.keyboard.press("Escape")
    await pg.locator(f'button[title="{ZH["common.allComments"]}"]').click()
    await pg.screenshot(path=str(SHOTS / "199-03-comments-list-zh.png"))
    await pg.get_by_role("button", name=ZH["commentsList.summarizeAllComments"]).click()
    await _until(lambda: _async(len(pg.sends) == 1), 15)
    body = pg.sends[0]
    head = ZH["commentsList.summarize"].split("{0}")[0]
    assert body["text"].startswith(head), body["text"]  # the summarize prompt, not the raw notes
    assert "标题字号再大一点" in body["text"] and "背景换成米色" in body["text"]
    assert len(REGION.findall(body["text"])) == 2 and len(body["refs"]) == 1
    turn = await _turn(fake_agent)
    assert turn.user_text.count("region x=") == 2
    assert await pg.locator(".ca-composer__input").input_value() == ""  # summarize does not touch the draft
    await _until(lambda: _body_has(pg, "收到，已整理评论。"), 15)
    await pg.screenshot(path=str(SHOTS / "199-04-summarize-reply-zh.png"))
    assert _edits(mock_ws) == []


async def test_summarize_disabled_without_open_comments(agent_page, mock_ws, fake_agent):  # noqa: F811
    pg = agent_page
    await pg.locator(f'button[title="{ZH["common.allComments"]}"]').click()
    btn = pg.get_by_role("button", name=ZH["commentsList.summarizeAllComments"])
    await btn.wait_for()
    assert await btn.is_disabled()
    assert await pg.get_by_role("button", name=ZH["commentsList.addToChat"].replace("{0}", "0")).is_disabled()
    await pg.wait_for_timeout(500)
    assert pg.sends == [] and fake_agent.last_turn is None


async def _body_has(pg, s):
    return s in await pg.locator("body").inner_text()
