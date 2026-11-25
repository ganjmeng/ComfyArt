"""Second check inside _dispatch_one_confirmed_brand, after the slot is bound.

The check before binding cannot see a prompt that changes after bind, or a
grant that expires between that check and the provider call. No WaveSpeed call.
"""
from __future__ import annotations

from ComfyArt.api import brand_identity as brand
from test_agent_budget_391 import calls, reply
from test_brand_template_quote_gate import _active_rig, _logos_phase


def _logo_script(messages, n):
    if n == 0:
        return calls(("generate_image", {
            "prompt": "logo a",
            "skill": brand.SKILL,
            "brand_slot": "logo_a",
        }))
    return reply("done")


def _texts(events) -> str:
    return "\n".join(getattr(ev, "text", "") or "" for ev in events)


def _stage2(brand_mod) -> dict:
    rec = brand_mod._stage_record(2)
    return rec if isinstance(rec, dict) else {}


async def test_prompt_mutated_after_binding_does_not_submit(monkeypatch):
    """A confirmed logo_a whose prompt changes after bind submits nothing."""
    real_bind = brand.bind_brand_generate

    def bind(args, quote_steps=None, claimed=None):
        prepared = real_bind(args, quote_steps, claimed)
        if isinstance(prepared, dict):
            prepared["prompt"] = "mutated after binding"
        return prepared

    monkeypatch.setattr(brand, "bind_brand_generate", bind)
    rig, _asked, _dispatch = await _active_rig(monkeypatch, _logo_script)
    _logos_phase()
    _res, events = await rig.send("出方向 A", goal="")
    prompts = [args.get("prompt") for _name, args in rig.paid_mcp()]
    rec = _stage2(brand)
    assert prompts == [], prompts
    assert "mutated after binding" not in prompts
    assert "参数已变化" in _texts(events)
    assert brand.submitted_slots(2) == set()
    assert list(rec.get("dispatching_slots") or []) == []
    assert brand._progress()["phase"] == "logos"
    saved = [str(row.get("prompt") or "") for row in ((brand._grant_of(2) or {}).get("slots") or [])]
    assert saved and all(row.startswith("logo a") for row in saved)
    assert all("mutated after binding" not in row for row in saved)


async def test_grant_expired_at_dispatch_does_not_submit(monkeypatch):
    """The grant is still valid at the pre-bind check and expired before submit."""
    armed = {"jump": False}
    real_clock = brand._clock
    real_block = brand.submit_block_reason

    def clock():
        now = real_clock()
        return now + 700 if armed["jump"] else now

    def block(args, turn=None, now=None):
        result = real_block(args, turn, now=now)
        armed["jump"] = True
        return result

    monkeypatch.setattr(brand, "_clock", clock)
    monkeypatch.setattr(brand, "submit_block_reason", block)
    rig, _asked, _dispatch = await _active_rig(monkeypatch, _logo_script)
    _logos_phase()
    _res, events = await rig.send("出方向 A", goal="")
    rec = _stage2(brand)
    assert rig.paid_mcp() == []
    assert "报价已过期" in _texts(events)
    assert brand.submitted_slots(2) == set()
    assert list(rec.get("dispatching_slots") or []) == []
    assert brand._progress()["phase"] == "logos"


async def test_confirmed_logo_a_submits_once_and_is_recorded(monkeypatch):
    """A normal confirmed default logo_a still submits once and records the slot."""
    rig, _asked, _dispatch = await _active_rig(monkeypatch, _logo_script)
    _logos_phase()
    await rig.send("出方向 A", goal="")
    gens = [args for _name, args in rig.paid_mcp()]
    assert len(gens) == 1, gens
    assert gens[0].get("brand_slot") == "logo_a"
    assert str(gens[0].get("prompt") or "").startswith("logo a")
    assert brand.submitted_slots(2) == {"logo_a"}
    assert brand._progress()["phase"] == "logos"
