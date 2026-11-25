"""A brand industry template uses the ordinary single-call quote gate.

``_dispatch_tools`` prices the call through ``_quote_steps`` / ``build_quote``
before any submit. Under the confirm line that quote is None and the call
runs, the same passthrough ``origin/main`` uses for one cheap generation.
Over the line ``_confirm_plan`` has to answer start. Skipping the brand
grant does not skip that gate. No WaveSpeed call.
"""
from __future__ import annotations

from ComfyArt.api import brand_identity as brand
from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
from ComfyArt.bot.local_llm import LocalLlmProvider
from test_agent_budget_391 import Rig, calls, reply

LOCK = (
    "Use the ComfyArt skill 'brand-identity-director' for this task.\n"
    "Output lock: template=geometric exactly 3 separate images"
)


def _turn(messages: list) -> str:
    for message in reversed(messages or []):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, list):
                content = " ".join(
                    str(part.get("text") or "") for part in content if isinstance(part, dict))
            return str(content or "")
    return ""


def _script(messages, n):
    """The #979 model: three direction proposals, then one guideline board."""
    last = _turn(messages)
    stage2 = "选第一个方向" in last
    if stage2:
        if n == 0:
            return calls(("generate_image", {
                "prompt": "guideline board for the chosen direction",
                "skill": brand.SKILL, "preset": "geometric", "stage": 2,
            }))
        return reply("规范板已生成。")
    if n < 3:
        return calls(("generate_image", {
            "prompt": f"logo direction {n + 1}",
            "skill": brand.SKILL,
        }))
    return reply("三个方向已出。")


def _gens(rig: Rig) -> list[dict]:
    return [args for name, args in rig.mcp if name == "generate_image"]


async def _rig(monkeypatch, *, price: float):
    brand.reset_for_tests()
    BOT_CHAT_ID.set("template-gate")
    rig = Rig(monkeypatch, _script)
    asked: list[dict] = []
    original = LocalLlmProvider._confirm_plan

    async def local_price(model, inputs):
        return (price, "quote", "test")

    async def watch(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        return await original(self, spec, turn, handle, **kwargs)

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", watch)
    return rig, asked


async def test_template_preset_without_confirmation_does_not_submit(monkeypatch):
    """Over the confirm line, nobody answering the card submits nothing."""
    rig, asked = await _rig(monkeypatch, price=0.60)
    await rig.send(LOCK, goal="")
    assert asked, "the template call never reached _confirm_plan"
    assert _gens(rig) == []


async def test_template_preset_confirmation_submits_three_then_one(monkeypatch):
    """Under the line, the ordinary gate passes the call through: 3, then 1.

    This is the #979 path. The model names no preset and no size. The output
    lock selects geometric, and no confirm card is required for a known price
    under the line.
    """
    rig, asked = await _rig(monkeypatch, price=0.04)
    await rig.send(LOCK, goal="")
    first = _gens(rig)
    assert len(first) == 3, first
    assert asked == []
    assert [(a.get("width"), a.get("height"), a.get("ratio"), a.get("preset"), a.get("stage"))
            for a in first] == [(1024, 1024, "1:1", "geometric", 1)] * 3

    rig.n = 0
    rig.mcp.clear()
    await rig.send("选第一个方向，直接出规范板", goal="")
    second = _gens(rig)
    assert len(second) == 1, second
    assert asked == []
    assert (second[0].get("width"), second[0].get("height"), second[0].get("ratio"),
            second[0].get("preset"), second[0].get("stage")) == (2048, 1152, "16:9", "geometric", 2)


async def test_template_preset_start_is_what_submits_the_over_line_call(monkeypatch):
    """The same over-line call submits only after _confirm_plan returns start."""
    rig, asked = await _rig(monkeypatch, price=0.60)

    async def start(self, spec, turn, handle, **kwargs):
        asked.append(spec)
        return "start"

    monkeypatch.setattr(LocalLlmProvider, "_confirm_plan", start)
    await rig.send(LOCK, goal="")
    gens = _gens(rig)
    assert asked, "start was not a confirm-gate answer"
    assert len(gens) == 3, gens
    assert all(a.get("preset") == "geometric" and not a.get("brand_slot") for a in gens)
