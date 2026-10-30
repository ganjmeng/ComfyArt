"""#234: context is counted in tokens against the model window.

Input may use 70% of that window (#493: 270k when neither the endpoint nor the
known-model table says). Over the budget, the last 6 turns stay verbatim and
earlier turns become one summary of at most summary_token_cap(window) tokens. The summary keeps goals, requirements, decisions, shapes
and failures — not raw tool output or screenshots. Mocks only.
"""
from __future__ import annotations

import json

from ComfyArt.bot.local_llm import (
    LocalLlmProvider,
    summary_token_cap,
    _VERBATIM_TURNS,
    context_window_tokens,
    count_tokens,
    input_token_budget,
    turn_result_from_blocks,
)
from ComfyArt.bot.providers import TurnHandle, TurnRequest


def _turns(n: int, body: str) -> list[dict]:
    return [{"role": "user", "text": f"T{i}-" + body} for i in range(n)]


def test_input_cap_is_70_percent_of_the_model_window():
    assert input_token_budget(10_000) == 7_000
    assert input_token_budget(32_000) == 22_400
    assert input_token_budget(None) == 189_000  # #493: unknown window falls back to 270k

    short = [{"role": "user", "text": f"turn {i} hello"} for i in range(3)]
    kept = LocalLlmProvider._history_messages(short, context_window=32_000)
    assert [m["content"] for m in kept] == ["turn 0 hello", "turn 1 hello", "turn 2 hello"]

    early = [{"role": "user", "text": f"E{i}" + "x" * 800} for i in range(8)]
    recent = [{"role": "user", "text": f"R{i}"} for i in range(6)]
    history = early + recent
    window = 2_000
    budget = input_token_budget(window)
    assert count_tokens("\n".join(m["text"] for m in history)) > budget
    msgs = LocalLlmProvider._history_messages(history, context_window=window)
    blob = "\n".join(m["content"] for m in msgs)
    assert count_tokens(blob) <= budget
    assert msgs[0]["content"].startswith("Earlier conversation summary:")
    assert "R5" in blob and "x" * 800 not in blob


def test_last_six_turns_stay_verbatim():
    history = [{"role": "user", "text": f"TURN{i}-" + "x" * 200} for i in range(10)]
    msgs = LocalLlmProvider._history_messages(history, context_window=500)
    verbatim = [m["content"] for m in msgs if not m["content"].startswith("Earlier conversation summary:")]
    assert len(verbatim) == _VERBATIM_TURNS == 6
    assert verbatim == [f"TURN{i}-" + "x" * 200 for i in range(4, 10)]
    assert all("TURN0-" not in text and "TURN3-" not in text for text in verbatim)
    assert msgs[0]["role"] == "system"


def test_summary_is_at_most_2000_tokens_and_keeps_the_record():
    shapes = [{
        "id": f"shape:{i}",
        "type": "image",
        "model": "vendor/model",
        "prompt": "word " * 80,
    } for i in range(80)]
    history = [
        {"role": "user", "text": "GOAL_KEEP paint a poster. 数量 4 张，尺寸 3:4，风格 水彩，预算 $2 "
         "data:image/png;base64,BBBB"},
        {"role": "assistant", "text": "决定用 seedream，改为竖版\n"
         "{\"dump\":\"RAW_TOOL_DUMP_9f3\",\"shot\":\"data:image/png;base64,AAAA\"}",
         "result": {"shapes": shapes, "failures": [
             {"attempt": "generate_video", "reason": "insufficient balance"}]}},
        {"role": "user", "text": "z" * 400_000},
        *[{"role": "user", "text": f"RECENT{i}"} for i in range(6)],
    ]
    # #493: the summary cap scales with the window; 40k -> round(40k*5%) = 2000 tokens.
    assert summary_token_cap(40_000) == 2_000
    msgs = LocalLlmProvider._history_messages(history, context_window=40_000)
    summary = msgs[0]["content"]
    assert summary.startswith("Earlier conversation summary:")
    assert count_tokens(summary) <= summary_token_cap(40_000)
    assert count_tokens(summary) > 1_500
    assert "GOAL_KEEP" in summary
    assert "数量 4 张" in summary and "3:4" in summary
    assert "水彩" in summary and "$2" in summary
    assert "seedream" in summary and "竖版" in summary
    assert "id=shape:0" in summary and "type=image" in summary and "model=vendor/model" in summary
    assert "id=shape:79" not in summary
    assert "insufficient balance" in summary
    assert "RAW_TOOL_DUMP_9f3" not in summary
    assert "data:image" not in summary
    assert "z" * 200 not in summary
    verbatim = [m["content"] for m in msgs[1:]]
    assert verbatim == [f"RECENT{i}" for i in range(6)]


def test_unknown_window_falls_back_to_270k():
    assert context_window_tokens(None) == 270_000
    assert context_window_tokens({}) == 270_000
    assert context_window_tokens({"id": "m", "max_tokens": 4096}) == 270_000
    assert context_window_tokens({"context_length": "128000"}) == 128_000
    assert context_window_tokens({"meta": {"n_ctx": 8192}}) == 8192
    assert context_window_tokens({"architecture": {"max_context_length": 16384}}) == 16_384

    body = "y" * 3196
    history = _turns(10, body)
    assert count_tokens(history[0]["text"]) == 800
    assert count_tokens(history[0]["text"]) * 10 <= input_token_budget(None)
    assert count_tokens(history[0]["text"]) * 10 > input_token_budget(10_000)

    plain = LocalLlmProvider._history_messages(history)  # window unknown -> 270k
    assert len(plain) == 10
    assert all(not m["content"].startswith("Earlier") for m in plain)
    assert plain[0]["content"] == history[0]["text"]

    tight = LocalLlmProvider._history_messages(history, context_window=10_000)
    assert tight[0]["content"].startswith("Earlier conversation summary:")
    assert [m["content"] for m in tight[1:]] == [m["text"] for m in history[-6:]]


def test_each_turn_records_shape_id_and_model():
    blocks = [
        {"type": "tool_use", "name": "generate_image",
         "input": {"prompt": "a watercolor cat. extra detail", "model": "bytedance/seedream"}},
        {"type": "tool_result", "name": "generate_image", "status": "success",
         "text": json.dumps({"ids": ["job:1"], "model": "bytedance/seedream"})},
        {"type": "tool_use", "name": "wait_generation", "input": {"ids": ["job:1"]}},
        {"type": "tool_result", "name": "wait_generation", "status": "success",
         "text": json.dumps({"status": "done", "results": [
             {"id": "job:1", "status": "done", "shapes": ["shape:cat1"]}]})},
        {"type": "tool_use", "name": "mcp__comfyart__generate_video", "input": {"prompt": "ocean"}},
        {"type": "tool_result", "name": "generate_video", "status": "error",
         "text": "[tool error] insufficient balance data:image/png;base64,CCCC"},
    ]
    recorded = turn_result_from_blocks(blocks)
    assert recorded["shapes"] == [{
        "id": "shape:cat1", "type": "image", "model": "bytedance/seedream",
        "prompt": "a watercolor cat.",
    }]
    assert recorded["failures"] == [{"attempt": "generate_video", "reason": "insufficient balance"}]
    assert "data:image" not in json.dumps(recorded)

    history = [
        {"role": "user", "text": "draw a cat"},
        {"role": "assistant", "text": "done", "result": recorded},
    ]
    msgs = LocalLlmProvider._history_messages(history, context_window=32_000)
    assert msgs[1]["content"].startswith("done\n[turn result] ")
    assert "id=shape:cat1" in msgs[1]["content"]
    assert "type=image" in msgs[1]["content"]
    assert "model=bytedance/seedream" in msgs[1]["content"]
    assert "prompt=a watercolor cat." in msgs[1]["content"]


def test_replay_attaches_the_turn_result():
    from ComfyArt.api import chat_store
    from ComfyArt.api.bot_turns import _replay_history

    chat = chat_store.create_chat(user="default", project="p234", provider="local-llm")
    first = chat_store.create_message(chat_id=chat["id"], role="user",
                                      blocks=[{"type": "text", "text": "draw a cat"}])
    chat_store.create_message(
        chat_id=chat["id"], role="assistant", parent_id=first["id"], blocks=[
            {"type": "text", "text": "done"},
            {"type": "tool_use", "name": "generate_image",
             "input": {"prompt": "a cat", "model": "vendor/model"}},
            {"type": "tool_result", "name": "generate_image", "status": "success",
             "text": json.dumps({"ids": ["job:1"], "model": "vendor/model"})},
            {"type": "tool_use", "name": "wait_generation", "input": {"ids": ["job:1"]}},
            {"type": "tool_result", "name": "wait_generation", "status": "success",
             "text": json.dumps({"status": "done", "results": [
                 {"id": "job:1", "status": "done", "shapes": ["shape:cat1"]}]})},
        ])
    nxt = chat_store.create_message(chat_id=chat["id"], role="user",
                                    blocks=[{"type": "text", "text": "brighter"}])
    current = chat_store.create_message(chat_id=chat["id"], role="assistant",
                                        blocks=[], status="streaming", parent_id=nxt["id"])
    history = _replay_history(chat["id"], current["id"])
    assert history[0] == {"role": "user", "text": "draw a cat"}
    assert history[1]["role"] == "assistant" and history[1]["text"] == "done"
    assert history[1]["result"]["shapes"][0]["id"] == "shape:cat1"
    assert history[1]["result"]["shapes"][0]["model"] == "vendor/model"
    assert history[1]["result"]["shapes"][0]["type"] == "image"


async def test_send_counts_tokens_against_the_model_window(monkeypatch):
    """The window comes from /models for the selected model; a payload with no
    window uses the 270k fallback, so the same history is not compressed."""
    body = "y" * 3196
    history = _turns(10, body)

    async def _run(models_payload):
        provider = LocalLlmProvider(base_url=lambda: "http://x/v1")
        seen = {}

        async def fake_request(session, method, url, *, headers, json_body=None, timeout=120):
            if url.endswith("/models"):
                return models_payload
            seen["messages"] = json_body["messages"]
            return {"choices": [{"message": {"content": "ok", "tool_calls": []}}]}

        monkeypatch.setattr(provider, "_request_json", fake_request)
        result = await provider.send(
            TurnRequest(chat_id="c", user_text="next", history=history, model="m1"),
            _noop, TurnHandle())
        assert result.error == ""
        return seen["messages"]

    tight = await _run({"data": [{"id": "m1", "context_length": 10_000}]})
    assert tight[0]["content"].startswith("Earlier conversation summary:")
    assert len(tight) == 8  # summary + last 6 turns + the new user message

    wide = await _run({"data": [{"id": "m1"}]})
    assert len(wide) == 11  # 10 history turns + the new user message
    assert all(not m["content"].startswith("Earlier") for m in wide)


async def _noop(_ev):
    return None
