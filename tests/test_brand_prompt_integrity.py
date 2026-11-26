"""Confirmed brand snapshot is the assembled request, not a later model rewrite.

The generate POST counted here is the JSON-RPC tools/call that ``_mcp_call_tool``
sends. The loopback answers it. ``wavespeed.submit`` is counted and must stay empty.
"""
from __future__ import annotations

import json

from ComfyArt.api import brand_identity as brand
from ComfyArt.api import wavespeed
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.local_llm import LocalLlmProvider
from test_agent_budget_391 import Rig, calls, reply
from test_brand_identity_1019 import _card1, _logos_ready

LEGIT = "logo a bird on a branch"
UNRELATED = "a red sports car parked in a desert at noon"
APPENDED = LEGIT + "\nMODEL ADDED THIS"


def _step(slot: str, prompt: str) -> dict:
    return {
        "tool": "generate_image",
        "model": brand.QWEN_EDIT,
        "arguments": {
            "skill": brand.SKILL,
            "brand_slot": slot,
            "prompt": prompt,
            "width": brand._BY_ID[slot]["width"],
            "height": brand._BY_ID[slot]["height"],
            "count": 1,
            "refs": ["shape:mood"],
            "edit_model": brand.QWEN_EDIT,
        },
    }


def _generate(slot: str, prompt: str) -> tuple[str, dict]:
    return ("generate_image", dict(_step(slot, prompt)["arguments"]))


class _Session:
    def __init__(self, monkeypatch):
        self.generate_posts: list[dict] = []
        self.wavespeed_posts: list[dict] = []
        self.confirms: list[dict] = []
        self.monkeypatch = monkeypatch

        async def ws_submit(inputs):
            self.wavespeed_posts.append(dict(inputs or {}))
            return "loopback-not-sent"

        monkeypatch.setattr(wavespeed, "submit", ws_submit)
        self.rig = Rig(monkeypatch, reply)

        async def price(model, inputs):
            return (0.03, "quote", "loopback", "q-integrity", "USD")

        monkeypatch.setattr(self.rig.p, "_price_one", price)
        monkeypatch.setattr(self.rig.p, "_models_for", lambda feature: [])

        async def yes(spec, turn, handle, **kwargs):
            self.confirms.append(spec)
            return "start"

        monkeypatch.setattr(self.rig.p, "_confirm_plan", yes)
        inner = self.rig.p._request_json

        async def counting(session, method, url, *, headers, json_body=None, timeout=120):
            body = json_body if isinstance(json_body, dict) else {}
            params = body.get("params") if isinstance(body.get("params"), dict) else {}
            if (method == "POST" and body.get("method") == "tools/call"
                    and params.get("name") == "generate_image"):
                self.generate_posts.append(dict(params.get("arguments") or {}))
                return {"result": {"content": [{
                    "type": "text",
                    "text": json.dumps({"ids": [f"loopback-{len(self.generate_posts)}"]}),
                }]}}
            return await inner(session, method, url, headers=headers, json_body=json_body, timeout=timeout)

        monkeypatch.setattr(self.rig.p, "_request_json", counting)
        monkeypatch.setattr(
            self.rig.p, "_mcp_call_tool",
            LocalLlmProvider._mcp_call_tool.__get__(self.rig.p, LocalLlmProvider))

    async def send(self, script, text="出图"):
        self.rig.script = script
        self.rig.n = 0
        return await self.rig.send(text, goal="")


def _open():
    brand.reset_for_tests()
    token = BOT_CHAT_ID.set("c")
    _logos_ready()
    return token


async def test_unrelated_same_slot_prompt_before_bind_sends_zero_posts(monkeypatch):
    token = _open()
    try:
        session = _Session(monkeypatch)

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": [_step("logo_a", LEGIT)]}))
            if n == 1:
                return calls(_generate("logo_a", UNRELATED))
            return reply("好")

        await session.send(script)
        assert len(session.confirms) == 1
        assert session.generate_posts == []
        assert session.wavespeed_posts == []
        assert brand.grant_still_authorizes([_step("logo_a", UNRELATED)]) is False
        assert brand.submitted_slots(2) == set()
    finally:
        BOT_CHAT_ID.reset(token)


async def test_arbitrary_suffix_before_bind_sends_zero_posts(monkeypatch):
    token = _open()
    try:
        session = _Session(monkeypatch)

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": [_step("logo_a", LEGIT)]}))
            if n == 1:
                return calls(_generate("logo_a", APPENDED))
            return reply("好")

        await session.send(script)
        assert len(session.confirms) == 1
        assert session.generate_posts == []
        assert session.wavespeed_posts == []
        assert brand.submitted_slots(2) == set()
    finally:
        BOT_CHAT_ID.reset(token)


async def test_unchanged_frozen_snapshot_submits_once(monkeypatch):
    token = _open()
    try:
        session = _Session(monkeypatch)

        def script(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": [_step("logo_a", LEGIT)]}))
            if n == 1:
                return calls(_generate("logo_a", LEGIT))
            return reply("好")

        await session.send(script)
        assert len(session.confirms) == 1
        assert len(session.generate_posts) == 1
        posted = session.generate_posts[0]["prompt"]
        frozen = brand._grant_of(2)["slots"][0]["prompt"]
        assert posted == frozen
        assert posted.startswith(LEGIT)
        assert "主组合" in posted
        assert session.wavespeed_posts == []

        def again(messages, n):
            if n == 0:
                return calls(_generate("logo_a", LEGIT))
            return reply("好")

        await session.send(again)
        assert len(session.confirms) == 1
        assert len(session.generate_posts) == 1
        assert session.wavespeed_posts == []
    finally:
        BOT_CHAT_ID.reset(token)


async def test_requote_of_changed_prompt_submits_once_across_repeat_and_reload(monkeypatch):
    token = _open()
    try:
        session = _Session(monkeypatch)

        def first(messages, n):
            if n == 0:
                return calls(("quote_plan", {"steps": [_step("logo_a", LEGIT)]}))
            return reply("好")

        await session.send(first)
        first_digest = brand._grant_of(2)["digest"]
        assert len(session.confirms) == 1
        assert session.generate_posts == []

        def second(messages, n):
            if n == 0:
                return calls(
                    ("quote_plan", {"steps": [_step("logo_a", UNRELATED)]}),
                    _generate("logo_a", UNRELATED),
                )
            return reply("好")

        await session.send(second)
        assert len(session.confirms) == 2
        assert len(session.generate_posts) == 1
        posted = session.generate_posts[0]["prompt"]
        frozen = brand._grant_of(2)["slots"][0]["prompt"]
        assert posted == frozen
        assert posted.startswith(UNRELATED)
        assert LEGIT not in posted.split("\n", 1)[0]
        assert brand._grant_of(2)["digest"] != first_digest
        assert brand.submitted_slots(2) == {"logo_a"}

        def repeat(messages, n):
            if n == 0:
                return calls(_generate("logo_a", UNRELATED))
            return reply("好")

        await session.send(repeat)
        assert len(session.confirms) == 2
        assert len(session.generate_posts) == 1

        brand.drop_memory_for_tests()
        await session.send(repeat)
        assert len(session.confirms) == 2
        assert len(session.generate_posts) == 1
        assert brand.submitted_slots(2) == {"logo_a"}
        assert session.wavespeed_posts == []
    finally:
        BOT_CHAT_ID.reset(token)


def _moodboard_ready():
    brand.record_card_answer(_card1(), {
        "bi_delivery": {"selected": ["A"]}, "bi_color": {"selected": ["A"]},
        "bi_mark": {"selected": ["A"]}, "bi_source": {"selected": ["A"]},
    })


def _finals_ready():
    _logos_ready()
    progress = brand._progress()
    progress["shapes"]["logo_a"] = "shape:logo-a"
    progress["shapes"]["logo_b"] = "shape:logo-b"
    progress["shapes"]["logo_c"] = "shape:logo-c"
    brand.record_card_answer({"questions": [{
        "id": "bi_direction",
        "prompt": "选定哪个 Logo 方向作为最终标识？",
        "options": [
            {"id": "A", "label": "方向 A"},
            {"id": "B", "label": "方向 B"},
            {"id": "C", "label": "方向 C"},
        ],
    }]}, {"bi_direction": {"selected": ["A"]}})


def _stage_rows():
    return {
        "moodboard": [("moodboard", "mood board source")],
        "logos": [("logo_a", "direction A"), ("logo_b", "direction B"), ("logo_c", "direction C")],
        "finals": [
            ("spec", "spec source"),
            ("cup", "cup source"),
            ("bag", "bag source"),
            ("storefront", "storefront source"),
        ],
    }


async def test_normal_stages_do_not_requote_because_of_program_assembly(monkeypatch):
    """Each default stage quotes once. Assembly does not open a second card."""
    token = BOT_CHAT_ID.set("c")
    try:
        for phase, rows in _stage_rows().items():
            brand.reset_for_tests()
            if phase == "moodboard":
                _moodboard_ready()
            elif phase == "logos":
                _logos_ready()
            else:
                _finals_ready()
            assert brand._progress()["phase"] == phase
            steps = [_step(slot, prompt) for slot, prompt in rows]
            generates = [_generate(slot, prompt) for slot, prompt in rows]
            session = _Session(monkeypatch)

            def first(messages, n, steps=steps, generates=generates):
                if n == 0:
                    return calls(("quote_plan", {"steps": steps}), *generates)
                return reply("好")

            await session.send(first, text=phase)
            assert len(session.confirms) == 1, phase
            assert len(session.generate_posts) == len(rows), phase
            for (slot, prompt), posted in zip(rows, session.generate_posts):
                posted_prompt = str(posted["prompt"])
                assert posted["brand_slot"] == slot
                # Assembly keeps the caller's words and adds the lock. The spec
                # preface leads that prompt; every other slot still starts with the caller.
                assert prompt in posted_prompt
                assert posted_prompt != prompt
                if slot == "spec":
                    assert posted_prompt.startswith("Draw seven separate panels")
                else:
                    assert posted_prompt.startswith(prompt)
            assert session.wavespeed_posts == []

            def second(messages, n, generates=generates):
                if n == 0:
                    return calls(*generates)
                return reply("好")

            await session.send(second, text=phase + " again")
            assert len(session.confirms) == 1, phase
            assert len(session.generate_posts) == len(rows), phase
    finally:
        BOT_CHAT_ID.reset(token)
