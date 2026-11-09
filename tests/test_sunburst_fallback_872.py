"""#872: GPT Image 2.6 Sunburst rows fall back to matching Flare at runtime (mocked, $0)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ComfyArt.api import auto_models, wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.local_llm import _result_error_kind
from test_wavespeed import ws  # noqa: F401  — mocked WaveSpeed API fixture

ROOT = Path(__file__).resolve().parents[1]
SUN_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
FLARE_T2I = "openai/gpt-image-2.6-flare/text-to-image"
SUN_EDIT = "openai/gpt-image-2.6-sunburst/edit"
FLARE_EDIT = "openai/gpt-image-2.6-flare/edit"
POSTER = 'Movie poster with the headline "SUMMER"'


@pytest.fixture
def catalog():
    return wavespeed.load_config()


def test_catalog_has_flare_edit_for_masked(catalog):
    ids = {m["id"] for m in catalog["features"]["image_edit"]["models"]}
    assert FLARE_EDIT in ids and SUN_EDIT in ids
    row = auto_models.load_table()["image_edit"]["masked"]
    assert row["model"] == SUN_EDIT and row["fallback"] == FLARE_EDIT


def test_table_registers_sunburst_to_flare():
    table = json.loads((ROOT / "api/auto_models.json").read_text(encoding="utf-8"))
    poster = next(c for c in table["features"]["text_to_image"]["categories"] if c["id"] == "poster_text")
    assert poster["model"] == SUN_T2I and poster["fallback"] == FLARE_T2I
    masked = table["features"]["image_edit"]["masked"]
    assert masked["model"] == SUN_EDIT and masked["fallback"] == FLARE_EDIT


def test_poster_choose_tip_and_runtime_fallback(catalog):
    primary = auto_models.choose("text_to_image", POSTER, None, catalog)
    assert primary["model"] == SUN_T2I and primary["category"] == "poster_text"
    assert primary["reason"]["zh"] == "海报/带字"
    ids = {m["id"] for m in catalog["features"]["text_to_image"]["models"]}
    fb = auto_models.table_runtime_fallback_choice("text_to_image", primary, SUN_T2I, ids)
    assert fb and fb["model"] == FLARE_T2I and fb["fallback"] == SUN_T2I
    assert fb["fallback"] == primary["model"]
    tip = auto_models.pill_tooltip(fb, "zh")
    preferred = auto_models.short_name(fb["fallback"])
    used = auto_models.short_name(fb["model"])
    assert tip == f"自动选择：海报/带字 · 首选 {preferred} 失败，改用 {used}"
    assert auto_models.pill_label(fb) == f"Auto · {used}"


def test_canvas_fallback_choice_uses_row_fallback(catalog):
    choice = canvas._fallback_choice("generate_image", {"prompt": POSTER}, SUN_T2I)
    assert choice["model"] == FLARE_T2I and choice["fallback"] == SUN_T2I
    assert choice["category"] == "poster_text"
    poster = next(c for c in auto_models.load_table()["text_to_image"]["categories"] if c["id"] == "poster_text")
    assert choice["fallback"] == poster["model"]


def test_masked_fallback_choice_uses_flare_edit(catalog):
    choice = canvas._fallback_choice(
        "edit_region",
        {"id": "shape:a", "prompt": "redo the sky", "x": 0, "y": 0, "width": 8, "height": 8},
        SUN_EDIT,
    )
    assert choice["model"] == FLARE_EDIT and choice["fallback"] == SUN_EDIT
    assert choice.get("edit_model") == FLARE_EDIT
    tip = auto_models.pill_tooltip(choice, "zh")
    assert auto_models.short_name(SUN_EDIT) in tip and auto_models.short_name(FLARE_EDIT) in tip


def test_preferred_in_tip_equals_table_row_model_not_hardcoded(catalog):
    poster = next(c for c in auto_models.load_table()["text_to_image"]["categories"] if c["id"] == "poster_text")
    primary = auto_models.choose("text_to_image", POSTER, None, catalog)
    ids = {m["id"] for m in catalog["features"]["text_to_image"]["models"]}
    fb = auto_models.table_runtime_fallback_choice("text_to_image", primary, primary["model"], ids)
    assert fb["fallback"] == poster["model"]
    assert auto_models.short_name(poster["model"]) in auto_models.pill_tooltip(fb, "zh")


@pytest.mark.parametrize("kind,eligible", [
    ("timeout", True),
    ("failed", True),
    ("modelOffline", True),
    ("network", True),
    ("insufficientCredit", False),
    ("moderation", False),
    ("invalidKey", False),
    ("rateLimit", False),
])
def test_fallback_kind_gate(kind, eligible):
    assert auto_models.fallback_kind_eligible(kind) is eligible


def test_fallback_kind_blocks_400_status():
    assert auto_models.fallback_kind_eligible("failed", status=400) is False
    assert auto_models.fallback_kind_eligible("failed", status=502) is True


def test_result_error_kind_parses_balance():
    text = json.dumps({"error": {"kind": "insufficientCredit", "message": "low"}, "status": "failed"})
    assert _result_error_kind(text) == "insufficientCredit"
    assert auto_models.fallback_kind_eligible("insufficientCredit") is False


def test_sunburst_success_no_fallback_when_failed_is_other(catalog):
    primary = auto_models.choose("text_to_image", POSTER, None, catalog)
    ids = {m["id"] for m in catalog["features"]["text_to_image"]["models"]}
    assert auto_models.table_runtime_fallback_choice("text_to_image", primary, FLARE_T2I, ids) is None


def test_both_fail_never_retries_sunburst(catalog):
    primary = auto_models.choose("text_to_image", POSTER, None, catalog)
    ids = {m["id"] for m in catalog["features"]["text_to_image"]["models"]}
    fb = auto_models.table_runtime_fallback_choice("text_to_image", primary, SUN_T2I, ids)
    assert fb["model"] == FLARE_T2I
    assert auto_models.table_runtime_fallback_choice("text_to_image", fb, FLARE_T2I, ids) is None
    choice = canvas._fallback_choice("generate_image", {"prompt": POSTER}, FLARE_T2I)
    assert choice is None  # registered fallback failed → stop


@pytest.mark.asyncio
async def test_soft_timeout_still_running_keeps_polling_no_second_submit(ws, monkeypatch):
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": POSTER, "confirmed": True})
    assert len(ws["submits"]) == 1
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    await wavespeed.poll(task)
    assert len(ws["submits"]) == 1
    job = wavespeed._jobs[task]
    assert job.get("soft_timeout_checked") or int(job.get("soft_timeout_extends") or 0) >= 1
    assert not job.get("done")


@pytest.mark.asyncio
async def test_soft_timeout_later_success_no_flare_submit(ws, monkeypatch):
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": POSTER, "confirmed": True})
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 0.0)
    await wavespeed.poll(task)
    assert len(ws["submits"]) == 1
    # Original later completes — still only one submit
    ws["status"] = "completed"
    ws["outputs"] = ["https://cdn.example/out.png"]
    wavespeed._jobs[task]["started"] = 0
    wavespeed._jobs[task]["soft_timeout_checked"] = False
    wavespeed._jobs[task].pop("result", None)
    # May fail download in mock; critical invariant is submit count
    try:
        await wavespeed.poll(task)
    except Exception:
        pass
    assert len(ws["submits"]) == 1


@pytest.mark.asyncio
async def test_failed_prediction_no_extra_submit(ws, monkeypatch):
    ws["status"] = "failed"
    ws["error"] = "provider 502"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": POSTER, "confirmed": True})
    hist = await wavespeed.poll(task)
    assert hist[f"ws:{task}"]["status"]["completed"] is True
    assert len(ws["submits"]) == 1
