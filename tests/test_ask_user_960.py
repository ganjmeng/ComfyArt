"""#960 — ask_user missing/invalid spec: actionable error, no empty card, fix-and-continue.

$0: mock/fake only. No real LLM, no WaveSpeed, no paid call.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from conftest import SENT
from ComfyArt.api import bot_asks, chat_store, mcp
from ComfyArt.api.bot_turns import ACTIVE_TURNS, _TurnState
from ComfyArt.api.mcp_tools import bot_tools
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.providers import TurnHandle

# The three card-1 questions the YouTube skill tells the agent to send (review-assets d7672d03).
CARD1 = {
    "questions": [
        {"id": "yt_delivery", "prompt": "这次横幅想怎么交付？（影响后续步骤与文字精度）", "allow_other": True,
         "options": [{"id": "A", "label": "先出三方向选择板，再做终稿"},
                     {"id": "B", "label": "直接出一张终稿，文字用精确排版渲染"},
                     {"id": "C", "label": "直接出一张终稿，文字由图像模型生成"}],
         "placeholder": "其它想法（比如一次出多个方向终稿）..."},
        {"id": "yt_banner_text", "prompt": "横幅上实际要出现哪些文字？", "allow_other": True,
         "options": [{"id": "A", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流 ＋ 每周二/五更新"},
                     {"id": "B", "label": "Loomi Studio ＋ AI 绘画教程和创意工作流"},
                     {"id": "C", "label": "只有 Loomi Studio"}],
         "placeholder": "自己指定文案（含大小写、符号、换行）..."},
        {"id": "yt_brand_assets", "prompt": "有需要放进去的品牌资产吗？（Logo／头像／真人）", "allow_other": True,
         "options": [{"id": "A", "label": "没有，纯图形＋文字构成识别"},
                     {"id": "B", "label": "有 Logo／头像，我上传给你"},
                     {"id": "C", "label": "需要预留真人出镜位置"}],
         "placeholder": "其它（比如指定参考图／配色）..."},
    ],
    "allow_skip": True,
    "page_count": 3,
}
# The user's real answers in this test are B / C+free text / A — never the fabricated A/A/A.
USER_ANSWERS = {
    "yt_delivery": {"selected": ["B"]},
    "yt_banner_text": {"selected": ["C"], "other_text": "Loomi Studio"},
    "yt_brand_assets": {"selected": ["A"]},
}


@pytest.fixture(autouse=True)
def _clean_pending():
    bot_asks.PENDING.clear()
    bot_asks.ANSWERED_RUN_APPROVALS.clear()
    yield
    bot_asks.PENDING.clear()
    bot_asks.ANSWERED_RUN_APPROVALS.clear()


# --- the error is actionable and localized ------------------------------------------------

def test_agent_facing_tool_description_states_the_required_shape() -> None:
    """Mutation: drop the requirement from the ask_user schema description -> agents keep sending {}."""
    desc = bot_tools.TOOLS["ask_user"]["description"]
    assert "Required: non-empty questions[] or prompt+options" in desc
    assert "renders no card" in desc


def test_missing_prompt_and_questions_zh_says_what_to_send(monkeypatch) -> None:
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    with pytest.raises(ValueError) as e:
        bot_asks.validate_spec({"allow_skip": True})
    msg = str(e.value)
    assert "prompt is required" in msg
    assert "没有渲染卡片" in msg and "没有记录任何回答" in msg
    assert "questions" in msg and '"prompt"' in msg and '"id"' in msg
    assert "allow_other" in msg and "page_count" in msg
    assert "重新调用 ask_user" in msg and "不要跳过" in msg
    assert bot_asks.PENDING == {}


def test_missing_prompt_and_questions_en_says_what_to_send(monkeypatch) -> None:
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "en")
    with pytest.raises(ValueError) as e:
        bot_asks.validate_spec({"allow_skip": True})
    msg = str(e.value)
    assert "prompt is required" in msg
    assert "no card was shown" in msg and "no answer was recorded" in msg
    assert "questions" in msg and "allow_other" in msg and "page_count" in msg
    assert "call ask_user again" in msg and "do not skip" in msg


@pytest.mark.parametrize("bad,detail", [
    ({"questions": []}, "non-empty list"),
    ({"questions": "nope"}, "non-empty list"),
    ({"questions": [{}]}, "needs id and prompt"),
    ({"questions": [{"id": "q", "prompt": "p"}]}, "needs options"),
    ({"prompt": "   ", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]}, "prompt is required"),
    ({"questions": [{"id": "q", "prompt": "p", "options": [{"id": "A", "label": "A"},
                                                            {"id": "A", "label": "B"}]}]}, "duplicate option id"),
    ({"questions": [{"id": "q", "prompt": "p", "allow_other": True},
                    {"id": "q", "prompt": "p2", "allow_other": True}]}, "duplicate question ids"),
])
def test_malformed_specs_keep_their_reason_and_add_recovery(monkeypatch, bad, detail) -> None:
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    with pytest.raises(ValueError) as e:
        bot_asks.validate_spec(bad)
    msg = str(e.value)
    assert detail in msg, msg
    assert "没有渲染卡片" in msg and "questions" in msg
    assert bot_asks.PENDING == {}


# --- a legal card 1 is three answerable questions, nothing preselected --------------------

def test_youtube_card1_is_three_answerable_questions_zh(monkeypatch) -> None:
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "zh")
    spec = bot_asks.validate_spec(CARD1)
    assert spec["page_count"] == 3 and spec["allow_skip"] is True
    assert [q["id"] for q in spec["questions"]] == ["yt_delivery", "yt_banner_text", "yt_brand_assets"]
    assert "defaults" not in spec and not any("defaults" in q for q in spec["questions"])
    assert [q["page"] for q in spec["questions"]] == [1, 2, 3]
    for q in spec["questions"]:
        assert q["prompt"] and q["placeholder"]
        assert q["allow_other"] is True
        assert len(q["options"]) >= 2
        assert not any(o.get("recommended") for o in q["options"])
    assert spec["prompt"] == spec["questions"][0]["prompt"]
    bot_asks.validate_answer(spec, [], "")  # skip is allowed
    bot_asks.validate_answer(spec, [], "", USER_ANSWERS)  # the real per-question answers validate


def test_youtube_card1_renders_for_english_question_text_too(monkeypatch) -> None:
    """中英一致: an en-locale card sent with the same question ids still renders and can be answered."""
    monkeypatch.setattr(bot_asks, "card_lang", lambda: "en")
    en = {"questions": [
        {"id": "yt_delivery", "prompt": "How should this banner be delivered?", "allow_other": True,
         "options": [{"id": "A", "label": "Three-direction board first"},
                     {"id": "B", "label": "One final with exact text layout"},
                     {"id": "C", "label": "One final with model-rendered text"}]},
        {"id": "yt_banner_text", "prompt": "What text should appear on the banner?", "allow_other": True,
         "options": [{"id": "A", "label": "Loomi Studio + AI tutorials + Tue/Fri"},
                     {"id": "B", "label": "Loomi Studio + AI tutorials"},
                     {"id": "C", "label": "Loomi Studio only"}]},
        {"id": "yt_brand_assets", "prompt": "Any brand assets to include?", "allow_other": True,
         "options": [{"id": "A", "label": "None"}, {"id": "B", "label": "Logo / avatar upload"},
                     {"id": "C", "label": "Reserve a person slot"}]},
    ], "allow_skip": True, "page_count": 3}
    spec = bot_asks.validate_spec(en)
    assert len(spec["questions"]) == 3 and spec["page_count"] == 3
    assert [q["id"] for q in spec["questions"]] == ["yt_delivery", "yt_banner_text", "yt_brand_assets"]
    for q in spec["questions"]:
        assert q["prompt"] and q["options"] and q["allow_other"] is True
    bot_asks.validate_answer(spec, [], "", USER_ANSWERS)


async def test_answer_records_the_users_real_choice_not_preselected_as(monkeypatch) -> None:
    spec = bot_asks.validate_spec(CARD1)
    monkeypatch.setattr(bot_asks, "_store_put", lambda ask: None)
    monkeypatch.setattr(bot_asks, "_store_delete", lambda ask_id: None)
    ask = bot_asks.create_ask("c960", "m960", spec)
    future = ask.future
    bot_asks.resolve_ask(ask.id, "answered", answers=USER_ANSWERS)
    out = await future
    assert out["answers"] == USER_ANSWERS
    assert out["answers"]["yt_delivery"]["selected"] == ["B"]
    assert out["answers"]["yt_banner_text"]["selected"] == ["C"]
    assert out["answers"] != {
        "yt_delivery": {"selected": ["A"]},
        "yt_banner_text": {"selected": ["A"]},
        "yt_brand_assets": {"selected": ["A"]},
    }
    assert bot_asks.PENDING == {}


# --- no card for an invalid call; fix → card → answer → continue --------------------------

async def test_invalid_call_never_creates_a_card_or_records_an_answer(monkeypatch) -> None:
    monkeypatch.setattr(bot_tools, "bot_turn_state", lambda: ("c960", object()))

    async def must_not_run(*_a, **_k):
        raise AssertionError("an invalid ask_user spec must not create/render a card")

    monkeypatch.setattr(bot_tools, "_await_ask", must_not_run)
    with pytest.raises(ValueError) as e:
        await bot_tools.ask_user({"allow_skip": True})
    assert "没有渲染卡片" in str(e.value) or "no card was shown" in str(e.value)
    assert bot_asks.PENDING == {}


async def test_missing_params_then_fixed_card_continues_the_turn(monkeypatch) -> None:
    monkeypatch.setattr(bot_tools, "bot_turn_state", lambda: ("c960", object()))
    with pytest.raises(ValueError):
        await bot_tools.ask_user({"allow_skip": True})  # the QA failure: no prompt, no questions

    seen: dict = {}

    async def answered(chat_id, state, spec):
        seen["spec"] = spec
        return {"status": "answered", "selected": [], "other_text": "", "answers": USER_ANSWERS}

    monkeypatch.setattr(bot_tools, "_await_ask", answered)
    out = await bot_tools.ask_user(CARD1)  # the agent's corrected call in the same turn
    assert out["status"] == "answered"
    assert out["answers"] == USER_ANSWERS  # recorded exactly as the user answered
    assert len(seen["spec"]["questions"]) == 3 and seen["spec"]["page_count"] == 3


# --- the real MCP entry: error row, no turn_ask broadcast, then the real HTTP answer ------

async def _chat(client):
    resp = await client.post("/comfyart/bot/chats", json={"project": "p", "provider": "fake-test"})
    assert resp.status == 200
    return (await resp.json())["chat"]


async def _answer_when_pending(client, chat_id):
    ask = None
    for _ in range(600):
        pending = bot_asks.list_pending_for_chat(chat_id)
        if pending:
            ask = pending[0]
            break
        await asyncio.sleep(0.01)
    assert ask is not None, "the fixed ask_user call never rendered a card"
    resp = await client.post(f"/comfyart/bot/chats/{chat_id}/asks/{ask.id}/answer",
                             json={"selected": [], "other_text": "", "answers": USER_ANSWERS})
    assert resp.status == 202, await resp.text()
    return ask


async def test_real_mcp_rejects_then_renders_card1_and_records_answers(bot_client, fake_provider, caplog) -> None:
    chat = await _chat(bot_client)
    msg = chat_store.create_message(chat_id=chat["id"], role="assistant", blocks=[], status="streaming")
    ACTIVE_TURNS[chat["id"]] = _TurnState(TurnHandle(), chat["id"], msg["id"])
    token = BOT_CHAT_ID.set(chat["id"])
    try:
        with caplog.at_level("WARNING", logger="comfyart"):
            bad = await mcp._tools_call({"name": "ask_user", "arguments": {"allow_skip": True}})
        assert bad["isError"] is True
        text = bad["content"][0]["text"]
        assert text.startswith("ValueError:")
        assert "prompt is required" in text and "questions" in text
        assert "没有渲染卡片" in text and "重新调用 ask_user" in text
        assert bot_asks.PENDING == {}
        assert ACTIVE_TURNS[chat["id"]].blocks == []  # no empty card block
        assert not any(d.get("event") == "turn_ask" for _ev, d in SENT)  # nothing broadcast to the UI
        assert any("ask_user rejected, no card rendered" in rec.getMessage() and "allow_skip" in rec.getMessage()
                   for rec in caplog.records)

        task = asyncio.create_task(_answer_when_pending(bot_client, chat["id"]))
        good = await mcp._tools_call({"name": "ask_user", "arguments": CARD1})
        ask = await task
    finally:
        BOT_CHAT_ID.reset(token)
        ACTIVE_TURNS.pop(chat["id"], None)
        chat_store.update_message(chat["id"], msg["id"], status="done")

    assert good["isError"] is False
    payload = json.loads(good["content"][0]["text"])
    assert payload["status"] == "answered"
    assert payload["answers"] == USER_ANSWERS
    assert payload["answers"]["yt_delivery"]["selected"] == ["B"]
    assert payload["answers"] != {"yt_delivery": {"selected": ["A"]},
                                  "yt_banner_text": {"selected": ["A"]},
                                  "yt_brand_assets": {"selected": ["A"]}}
    # the card block persisted on the assistant message, with the real answers
    stored = next(m for m in chat_store.list_messages(chat["id"]) if m["id"] == msg["id"])
    block = next(b for b in stored["blocks"] if b.get("type") == "ask")
    assert block["status"] == "answered" and block["answers"] == USER_ANSWERS
    assert block["page_count"] == 3 and len(block["questions"]) == 3
    assert "defaults" not in block
    rendered = [data for _ev, data in SENT if data.get("event") == "turn_ask" and data.get("ask_id") == ask.id]
    assert len(rendered) == 1
    assert len(rendered[0]["questions"]) == 3 and rendered[0]["page_count"] == 3
    resolved = [data for _ev, data in SENT if data.get("event") == "turn_ask_resolved" and data.get("ask_id") == ask.id]
    assert resolved and resolved[0]["status"] == "answered"
    assert resolved[0]["answers"] == USER_ANSWERS
