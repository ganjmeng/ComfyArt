"""#1019 brand identity without a director: brief + constraints through the shared tools.

There is no api/brand_identity.py. The skill row in bot/skill_output.OUTPUTS
declares only constraints (agent-planned count and ratios, exact-size model,
opaque output, always-confirm, confirm lifetime). These tests pin that generic
contract. They do not pin any panel count, heading list, ratio split, variant
list, or subject detail: those come from the brief, the cards and the model.
No WaveSpeed or LLM call.
"""
from __future__ import annotations

import asyncio
import io
import re
import time
from pathlib import Path

import pytest
from PIL import Image

from ComfyArt.api import bot_asks
from ComfyArt.api.image_delivery import flatten_opaque, image_is_full_frame_noise
from ComfyArt.bot.plan_quote import EXPIRED_TEXT, build_quote
from ComfyArt.bot.skill_output import (
    OUTPUTS, accepted_image_counts, apply_generate, plan_for, run_hint, scrub_internal_marks,
)

ROOT = Path(__file__).resolve().parents[1]
SKILL = "brand-identity-director"
NOISE = ROOT / "tests" / "fixtures" / "brand_noise"


# --- no director --------------------------------------------------------------------------------

def test_brand_director_module_is_absent():
    assert not (ROOT / "api" / "brand_identity.py").exists()
    shared = ["api/bot.py", "api/bot_asks.py", "api/bot_turns.py", "api/mcp_tools/bot_tools.py",
              "api/mcp_tools/canvas.py", "api/wavespeed.py", "bot/agent_loop.py", "bot/local_llm.py",
              "bot/plan_quote.py", "bot/skill_output.py", "bot/guide.py"]
    for rel in shared:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "brand_identity" not in text, rel
        assert "brand_slot" not in text, rel
        assert 'sid == "brand-identity-director"' not in text, rel


def test_skill_row_is_constraints_only():
    row = OUTPUTS[SKILL]
    assert row["agent_plan"] is True and row["no_template_default"] is True
    assert "stages" not in row  # no fixed default-path stage list
    assert row["always_confirm"] is True and row["confirm_ttl_s"] > 0
    assert row["opaque"] is True
    assert set(row["exact_size_models"]) == {"t2i", "edit"}


# --- sizes come from the call's ratio, count from the plan --------------------------------------

@pytest.mark.parametrize("ratio", sorted(OUTPUTS[SKILL]["ratio_pixels"]))
def test_no_template_call_takes_its_own_ratio(ratio):
    out = apply_generate({"skill": SKILL, "prompt": "x", "ratio": ratio}, user_text="做一个品牌")
    assert (out["width"], out["height"]) == OUTPUTS[SKILL]["ratio_pixels"][ratio]
    assert out["ratio"] == ratio and out["count"] == 1 and out["size_lock"] is True


def test_no_template_count_is_not_fixed():
    assert accepted_image_counts(SKILL, "") is None
    assert plan_for(SKILL, "")["preset"] == ""


def test_exact_size_model_follows_refs_and_marks_opaque():
    """A ratio the skill filled is not an exact-pixel request, so Qwen is not pinned.

    Opaque output stays. The user naming pixels still pins the row's exact-size model,
    and a second relay pass (no user text) keeps that pin.
    """
    from ComfyArt.api.skill_size import RATIO_MODE

    models = OUTPUTS[SKILL]["exact_size_models"]
    t2i = apply_generate({"skill": SKILL, "prompt": "x", "ratio": "16:9",
                          "width": 2048, "height": 1152}, user_text="")
    assert "model" not in t2i and "edit_model" not in t2i and "exact_size_pin" not in t2i
    assert t2i["opaque_output"] is True and t2i["size_lock_mode"] == RATIO_MODE
    edit = apply_generate({"skill": SKILL, "prompt": "guideline sheet", "ratio": "1:1",
                           "refs": ["shape:a"]}, user_text="做一张规范卡")
    assert "edit_model" not in edit and "model" not in edit and "exact_size_pin" not in edit
    again = apply_generate(dict(edit), user_text=None)
    assert (again["width"], again["height"]) == (edit["width"], edit["height"])
    assert "exact_size_pin" not in again
    explicit = apply_generate(
        {"skill": SKILL, "prompt": "guideline sheet", "ratio": "16:9", "refs": ["shape:a"]},
        user_text="按 1584x396 像素出规范卡",
    )
    assert explicit["edit_model"] == models["edit"] and "model" not in explicit
    assert explicit["exact_size_pin"] is True and explicit["opaque_output"] is True
    assert (explicit["width"], explicit["height"]) == (1584, 396)
    kept = apply_generate(dict(explicit), user_text=None)
    assert kept["edit_model"] == models["edit"] and kept["exact_size_pin"] is True
    assert (kept["width"], kept["height"]) == (1584, 396)


def test_template_path_keeps_its_declared_stages_and_no_exact_pin():
    out = apply_generate({"skill": SKILL, "preset": "tech", "prompt": "x"}, user_text="")
    assert (out["width"], out["height"], out["ratio"], out["stage"]) == (1024, 1024, "1:1", 1)
    assert "exact_size_pin" not in out and "opaque_output" not in out


def test_no_template_hint_is_constraints_only():
    hint = run_hint(SKILL, "做一个咖啡品牌", preset_id="")
    assert "no template selected" in hint
    for ratio in OUTPUTS[SKILL]["ratio_pixels"]:
        assert ratio in hint
    # No fixed panel count, heading list, ratio split, variant list or subject detail.
    for banned in ("3x3", "seven", "7 panels", "35/25", "logo_a", "spec", "cup", "bag", "storefront",
                   "moodboard", "情绪板", "外带杯", "门头", "#"):
        assert banned not in hint, banned


def test_template_hint_pauses_before_a_declared_stage():
    hint = run_hint(SKILL, "", preset_id="tech")
    assert "stage 1 = 3 image(s)" in hint and "stage 2 = 1 image(s)" in hint
    assert "before stage 2, stop and ask the user" in hint
    assert "width=1024 height=1024 ratio=1:1" in hint and "width=2048 height=1152 ratio=16:9" in hint


# --- LOCK-word scrub is shared ------------------------------------------------------------------

def test_internal_lock_labels_never_reach_any_prompt():
    assert scrub_internal_marks("STRUCTURE LOCK A: a cat. Output lock: x") == "a cat. x"
    for sid in (SKILL, "packaging-design-director"):
        out = apply_generate({"skill": sid, "prompt": "GUIDELINE LOCK: a board"}, user_text="")
        assert "LOCK" not in out["prompt"]


# --- quote: always confirm + lifetime, both declared by the row ----------------------------------

async def _quote(skill, amount=0.04, *, threshold=0.5):
    async def pricer(model, inputs):
        return (amount, "quote", "test")

    async def models_for(feature):
        return []

    steps = [{"tool": "generate_image", "model": "acme/poster",
              "arguments": {"prompt": f"p{i}", "skill": skill}} for i in range(2)]
    return await build_quote(steps, "zh", threshold=threshold, pricer=pricer, models_for=models_for)


async def test_brand_quote_asks_under_the_line_and_expires():
    quote = await _quote(SKILL)
    assert quote is not None and quote.ask is True
    assert "确认线" not in quote.prompt  # under the line the card does not claim the limit was reached
    before = time.time()
    spec = quote.ask_spec()
    assert spec["expires_at"] - spec["created_at"] == pytest.approx(OUTPUTS[SKILL]["confirm_ttl_s"])
    assert spec["created_at"] >= before


async def test_other_skills_keep_the_plain_threshold_and_no_deadline():
    quote = await _quote("packaging-design-director", amount=0.04, threshold=5.0)
    assert quote is None or "expires_at" not in quote.ask_spec()


# --- expiry is generic (bot_asks) ---------------------------------------------------------------

def test_start_after_the_deadline_is_expired_not_approval():
    spec = bot_asks.validate_spec({"prompt": "开始？", "options": [
        {"id": "start", "label": "开始"}, {"id": "cancel", "label": "取消"}]})
    spec["expires_at"] = time.time() - 1
    ask = bot_asks.create_ask("chat-exp", "m1", spec)
    assert bot_asks.confirm_expired(ask.spec)
    assert bot_asks.resolve_confirm_answer(ask, ["start"]) == "expired"
    assert bot_asks.resolve_confirm_answer(ask, ["start"]) == "lost"


def test_start_before_the_deadline_is_answered_and_no_deadline_never_expires():
    spec = bot_asks.validate_spec({"prompt": "开始？", "options": [
        {"id": "start", "label": "开始"}, {"id": "cancel", "label": "取消"}]})
    live = dict(spec, expires_at=time.time() + 60)
    ask = bot_asks.create_ask("chat-live", "m1", live)
    assert bot_asks.resolve_confirm_answer(ask, ["start"]) == "answered"
    plain = bot_asks.create_ask("chat-plain", "m1", dict(spec))
    assert not bot_asks.confirm_expired(plain.spec)
    assert bot_asks.resolve_confirm_answer(plain, ["start"], now=time.time() + 10 ** 6) == "answered"


def test_read_path_shows_a_stale_pending_card_as_expired():
    messages = [{"blocks": [{"type": "ask", "status": "pending", "expires_at": 1.0},
                            {"type": "ask", "status": "pending"}]}]
    bot_asks.mark_expired_blocks(messages, now=2.0)
    assert [b["status"] for b in messages[0]["blocks"]] == ["expired", "pending"]
    assert EXPIRED_TEXT["zh"] and EXPIRED_TEXT["en"]


async def test_confirm_plan_returns_expired_at_the_deadline(monkeypatch):
    from ComfyArt.bot.local_llm import LocalLlmProvider
    from ComfyArt.bot.providers import TurnHandle

    calls = {}

    async def fake_await(chat_id, state, spec, *, timeout=None, keep_pending_on_timeout=False,
                         wait_forever=False):
        calls["timeout"], calls["forever"] = timeout, wait_forever
        return {"status": "expired", "ask_id": "a1"}

    class _State:
        awaiting = ""

    class _Turn:
        chat_id = "chat-ttl"

    from ComfyArt.api import bot_turns
    from ComfyArt.api.mcp_tools import bot_tools
    monkeypatch.setattr(bot_tools, "_await_ask", fake_await)
    monkeypatch.setitem(bot_turns.ACTIVE_TURNS, "chat-ttl", _State())
    p = LocalLlmProvider(base_url=lambda: "http://x/v1")
    got = await p._confirm_plan({"expires_at": time.time() + 30}, _Turn(), TurnHandle())
    assert got == "expired"
    assert calls["forever"] is False and 0 < calls["timeout"] <= 30
    got = await p._confirm_plan({}, _Turn(), TurnHandle())
    assert calls["forever"] is True


# --- delivery checks are shared (api/image_delivery) --------------------------------------------

def _png(draw) -> bytes:
    img = Image.new("RGB", (96, 96), (240, 236, 228))
    draw(img)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_flatten_puts_alpha_on_white_and_leaves_opaque_bytes():
    opaque = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(opaque, format="PNG")
    raw = opaque.getvalue()
    assert flatten_opaque(raw) == raw
    transparent = io.BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 0)).save(transparent, format="PNG")
    with Image.open(io.BytesIO(flatten_opaque(transparent.getvalue()))) as img:
        assert img.mode == "RGB" and img.getpixel((0, 0)) == (255, 255, 255)
    full = io.BytesIO()
    Image.new("RGBA", (4, 4), (10, 20, 30, 255)).save(full, format="PNG")
    with Image.open(io.BytesIO(flatten_opaque(full.getvalue()))) as img:
        assert img.mode == "RGB" and img.getpixel((0, 0)) == (10, 20, 30)


def test_real_sheets_separate_noise_from_reviewable_crops():
    files = sorted(NOISE.glob("*.png"))
    assert len(files) == 25
    for path in files:
        assert image_is_full_frame_noise(path.read_bytes()) == path.name.startswith("pos-"), path.name


def test_synthetic_noise_is_flagged_and_a_sheet_is_not():
    import random
    rng = random.Random(7)

    def noise(img):
        px = img.load()
        for y in range(img.size[1]):
            for x in range(img.size[0]):
                px[x, y] = (rng.randrange(256), rng.randrange(256), rng.randrange(256))

    def sheet(img):
        px = img.load()
        for y in range(20, 76):
            for x in range(12, 84):
                px[x, y] = (92, 64, 48)

    assert image_is_full_frame_noise(_png(noise))
    assert not image_is_full_frame_noise(_png(sheet))
    assert not image_is_full_frame_noise(b"")


def test_completed_noise_is_a_charged_failure_for_any_opaque_job():
    from ComfyArt.api import wavespeed
    noise = (NOISE / "pos-4a41cc5a-spec.png").read_bytes()
    good = (NOISE / "neg-lovart-spec.png").read_bytes()
    failed = wavespeed.completed_noise_failure("task-n", {"opaque_output": True, "quoted": 0.12}, [noise])
    entry = failed["ws:task-n"]
    assert entry["status"]["status_str"] == "error" and entry["outputs"] == {}
    assert entry["charged"] is True and entry["refunded"] is False and entry["charged_usd"] == 0.12
    assert wavespeed.completed_noise_failure("task-ok", {"opaque_output": True, "quoted": 0.12}, [good]) is None
    # A job that did not opt in is never judged.
    assert wavespeed.completed_noise_failure("task-x", {"quoted": 0.12}, [noise]) is None


def test_built_bundle_charges_when_the_error_says_it_may_have_been_charged():
    """Run the compiled charge function. A string search is not the check."""
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    blobs = "\n".join(p.read_text(encoding="utf-8", errors="ignore")
                      for p in (ROOT / "dist" / "assets").glob("*.js"))
    match = re.search(
        r"function (\w+)\((\w)\)\{let (\w+)=/refunded\|已退款/\.test\(\2\);return\{charged:(.+?),refunded:\3\}\}",
        blobs,
    )
    assert match, "built bundle is missing the compiled charge function"
    script = (
        match.group(0)
        + "\nconst hit = " + match.group(1)
        + "('The task finished but returned no image, and it may have been charged about $0.12.');\n"
        + "if (hit.charged !== true || hit.refunded !== false) process.exit(2);\n"
        + "const clean = " + match.group(1) + "('Cancelled this generation; nothing was charged');\n"
        + "if (clean.charged !== false) process.exit(3);\n"
    )
    done = subprocess.run(["node", "-e", script], check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr or done.stdout


# --- shared loop: the agent's staged plan runs through quote + confirm ---------------------------

def _rig(monkeypatch, batches, *, confirm="start", budget=True):
    import json as _json

    from ComfyArt.api.mcp_tools._context import BOT_CHAT_ID
    from ComfyArt.bot.run_budget import resolve_policy
    from test_agent_budget_391 import Rig, calls, reply

    BOT_CHAT_ID.set("c")

    def script(messages, n):
        if n < len(batches):
            out = calls(*(("generate_image", args) for args in batches[n]))
            # A real model gives every tool call its own id; the shared helper restarts at 0.
            for tc in out["choices"][0]["message"]["tool_calls"]:
                tc["id"] = f"b{n}-{tc['id']}"
            return out
        return reply("完成")

    def mcp(name, args, i):
        return _json.dumps({"ids": [f"h-{i}"]} if name == "generate_image" else {})

    rig = Rig(monkeypatch, script, mcp=mcp)
    if not budget:
        pol = resolve_policy(env={"COMFYART_AGENT_BUDGET_LOOP": "0"})
        monkeypatch.setattr(rig.p, "_run_policy", lambda: pol)

    async def local_price(model, inputs):
        return (0.04, "quote", "test")

    monkeypatch.setattr(rig.p, "_price_one", local_price)
    seen = []
    if confirm == "start":
        async def yes(spec, turn, handle, **_kw):
            seen.append(spec)
            return "start"

        monkeypatch.setattr(rig.p, "_confirm_plan", yes)
    elif confirm == "expired":
        async def late(spec, turn, handle, **_kw):
            seen.append(spec)
            return "expired"

        monkeypatch.setattr(rig.p, "_confirm_plan", late)
    return rig, seen


_N = iter(range(10 ** 6))


def _call(ratio, **extra):
    return {"prompt": f"image {next(_N)} {ratio}", "skill": SKILL, "ratio": ratio, **extra}


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_agent_planned_stages_each_confirm_and_all_run(monkeypatch, budget):
    """1 + 3 + 4 images in three steps: one card per step, every image submitted.
    The confirmed card raises the run's image budget; no skill-specific budget hook."""
    batches = [[_call("16:9")], [_call("1:1") for _ in range(3)],
               [_call("3:4"), _call("3:4"), _call("3:4"), _call("16:9")]]
    rig, seen = _rig(monkeypatch, batches, budget=budget)
    _res, _events = await rig.send("做一个品牌", goal="")
    assert len(rig.paid_mcp()) == 8
    assert len(seen) == 3
    assert all("expires_at" in spec for spec in seen)


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_expired_confirm_submits_nothing_and_says_so(monkeypatch, budget):
    rig, _seen = _rig(monkeypatch, [[_call("16:9")]], confirm="expired", budget=budget)
    res, events = await rig.send("做一个品牌", goal="")
    assert rig.paid_mcp() == []
    text = "\n".join(e.text for e in events if e.t == "delta" and e.text)
    assert EXPIRED_TEXT["zh"] in text or EXPIRED_TEXT["zh"] in (res.error or "")


@pytest.mark.parametrize("budget", [True, False], ids=["agent_loop", "local_llm"])
async def test_template_call_under_the_line_still_needs_a_person(monkeypatch, budget):
    """No live turn: the always-confirm card is not approved, so the template call does not run."""
    rig, _seen = _rig(monkeypatch, [[_call("1:1", preset="tech")]], confirm="production", budget=budget)
    await rig.send("做一个品牌", goal="")
    assert rig.paid_mcp() == []
