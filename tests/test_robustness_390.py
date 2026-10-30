"""#390-1 rolling model summary of old turns. The summary model is always mocked."""
from __future__ import annotations

import asyncio

import pytest

from ComfyArt.bot import local_llm
from ComfyArt.bot import robustness as rb
from ComfyArt.bot.local_llm import LlmHttpError, LocalLlmProvider
from ComfyArt.bot.providers import TurnRequest

WINDOW = 8_000


@pytest.fixture(autouse=True)
def kv():
    s = rb.MemoryKeyValueStore()
    rb.set_store(s)
    yield s
    rb.set_store(rb.MemoryKeyValueStore())


def _history(n=30):
    out = []
    for i in range(n // 2):
        out.append({"role": "user", "text": f"第{i}轮需求 " + "细节" * 120})
        out.append({"role": "assistant", "text": f"第{i}轮回复 " + "细节" * 120})
    return out


def _turn(n=30, **ids):
    return TurnRequest(chat_id="c", user_text="继续", history=_history(n), **ids)


class Model:
    def __init__(self, answer="- 目标：一组猫的海报\n- 要求：16:9 水彩"):
        self.calls: list[tuple[str, str, str]] = []
        self.answer = answer

    def install(self, monkeypatch, p):
        async def summ(session, base, model, previous, new_turns):
            self.calls.append((model, previous, new_turns))
            if isinstance(self.answer, BaseException):
                raise self.answer
            if callable(self.answer):
                return await self.answer()
            return self.answer
        monkeypatch.setattr(p, "_summarize_llm", summ)
        return self


async def _hist(p, turn, model="m", window=WINDOW, reserved=0):
    return await p._history_with_model_summary(None, "http://x/v1", model, turn, window, reserved=reserved)


def _p():
    return LocalLlmProvider(base_url=lambda: "http://x/v1")


async def test_history_that_fits_makes_zero_model_calls(monkeypatch):
    p = _p()
    m = Model().install(monkeypatch, p)
    msgs = await _hist(p, _turn(4))
    assert m.calls == [] and all(x["role"] != "system" for x in msgs)


async def test_old_turns_summarized_once_then_cached(monkeypatch):
    p = _p()
    m = Model().install(monkeypatch, p)
    msgs = await _hist(p, _turn())
    assert len(m.calls) == 1 and msgs[0]["role"] == "system" and "水彩" in msgs[0]["content"]
    assert sum(1 for x in msgs if x["role"] == "user") <= local_llm._VERBATIM_TURNS
    again = await _hist(p, _turn())
    assert len(m.calls) == 1 and again == msgs  # same head: 0 recomputation


@pytest.mark.parametrize("ids", [{"workspace_id": "w2"}, {"owner_id": "u2"}, {"project_id": "p2"}])
async def test_other_workspace_owner_or_project_misses_cache(monkeypatch, ids):
    p = _p()
    m = Model().install(monkeypatch, p)
    await _hist(p, _turn())
    await _hist(p, _turn(**ids))
    assert len(m.calls) == 2


async def test_changing_summary_model_misses_cache(monkeypatch):
    p = _p()
    m = Model().install(monkeypatch, p)
    await _hist(p, _turn(), model="m")
    await _hist(p, _turn(), model="m2")
    assert [c[0] for c in m.calls] == ["m", "m2"]


async def test_changing_prompt_version_misses_cache(monkeypatch):
    p = _p()
    m = Model().install(monkeypatch, p)
    await _hist(p, _turn())
    monkeypatch.setattr(rb, "PROMPT_VERSION", "v2")
    await _hist(p, _turn())
    assert len(m.calls) == 2


async def test_one_more_turn_only_summarizes_the_newly_pushed_out_turn(monkeypatch):
    p = _p()
    m = Model().install(monkeypatch, p)
    await _hist(p, _turn(30))
    await _hist(p, _turn(32))  # one more user+assistant turn
    assert len(m.calls) == 2
    _model, previous, new_turns = m.calls[1]
    assert previous == m.answer
    assert new_turns.count("user: ") == 1  # exactly one turn, the one that just left the context
    first_new = m.calls[0][2]
    assert new_turns not in first_new


@pytest.mark.parametrize("answer", ["", LlmHttpError(503, "down"), "slow"])
async def test_empty_error_or_timeout_falls_back_without_cache_and_retries(monkeypatch, kv, answer):
    p = _p()
    if answer == "slow":
        async def slow():
            await asyncio.sleep(5)
            return "late"
        answer = slow
        monkeypatch.setitem(rb.DEFAULTS, "summary_timeout_s", 0.05)
    m = Model(answer).install(monkeypatch, p)
    turn = _turn()
    msgs = await _hist(p, turn)
    assert msgs == LocalLlmProvider._history_messages(turn.history, context_window=WINDOW)
    assert kv._data == {}  # nothing cached
    await _hist(p, turn)
    assert len(m.calls) == 2  # tried again next round


async def test_summary_cut_to_remaining_budget_and_prompt_fits_window(monkeypatch):
    p = _p()
    Model("- 目标 " + "很长的摘要" * 3000).install(monkeypatch, p)
    reserved = 900
    msgs = await _hist(p, _turn(), reserved=reserved)
    summary_tokens = local_llm.count_tokens(msgs[0]["content"])
    assert summary_tokens <= local_llm._SUMMARY_TOKEN_CAP
    assert local_llm._message_tokens(msgs) + reserved <= local_llm.input_token_budget(WINDOW)


async def test_summary_prompt_keeps_goals_requirements_decisions_shapes_failures(monkeypatch):
    p = _p()
    sent = {}

    async def fake(session, method, url, *, headers, json_body=None, timeout=120):
        sent["body"], sent["timeout"] = json_body, timeout
        return {"choices": [{"message": {"content": "- ok"}}]}
    monkeypatch.setattr(p, "_request_json", fake)
    out = await p._summarize_llm(None, "http://x/v1", "m", "旧摘要", "user: 新的一轮")
    assert out == "- ok" and sent["timeout"] <= 20
    system = sent["body"]["messages"][0]["content"]
    for item in ("Goals", "Requirements", "Decisions", "Canvas objects", "Failures"):
        assert item in system
    assert "旧摘要" in sent["body"]["messages"][1]["content"]


def test_store_is_scoped_and_locked():
    s = rb.MemoryKeyValueStore()
    s.put("summary", "k", "v", workspace_id="w", owner_id="o", project_id="p")
    assert s.get("summary", "k", workspace_id="w", owner_id="o", project_id="p") == "v"
    assert s.get("summary", "k", workspace_id="w", owner_id="o", project_id="other") is None
    assert hasattr(s, "_lock")


def test_store_survives_concurrent_readers_and_writers():
    """Threads hammering one small store: no exception, never over capacity, last write wins."""
    import sys
    import threading
    s = rb.MemoryKeyValueStore(max_items=8)
    ids = dict(workspace_id="w", owner_id="o", project_id="p")
    errors: list = []
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        def writer(n):
            try:
                for i in range(3000):
                    s.put("summary", f"{n}-{i}", str(i), **ids)
                    assert len(s._data) <= 8
            except BaseException as e:  # noqa: BLE001
                errors.append(e)

        def reader():
            try:
                for i in range(3000):
                    s.get("summary", f"0-{i}", **ids)
            except BaseException as e:  # noqa: BLE001
                errors.append(e)
        ts = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
        ts += [threading.Thread(target=reader) for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    finally:
        sys.setswitchinterval(old)
    assert not errors, errors[:3]
    assert len(s._data) <= 8


def test_store_evicts_oldest_entry_first_at_512():
    s = rb.MemoryKeyValueStore()
    ids = dict(workspace_id="w", owner_id="o", project_id="p")
    for i in range(512):
        s.put("summary", f"k{i}", str(i), **ids)
    s.put("summary", "k0", "again", **ids)  # overwriting an existing key never evicts
    assert len(s._data) == 512 and s.get("summary", "k0", **ids) == "again"
    s.put("summary", "k512", "512", **ids)  # entry 513 evicts the oldest (k0 kept its slot)
    assert len(s._data) == 512
    assert s.get("summary", "k0", **ids) is None
    assert s.get("summary", "k1", **ids) == "1"
    assert s.get("summary", "k512", **ids) == "512"
