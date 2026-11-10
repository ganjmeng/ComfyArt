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
    assert poster["model"] == FLARE_T2I and "fallback" not in poster
    masked = table["features"]["image_edit"]["masked"]
    assert masked["model"] == SUN_EDIT and masked["fallback"] == FLARE_EDIT


def test_poster_choose_tip_and_no_runtime_fallback(catalog):
    """poster_text is Flare with no registered fallback; a failure goes through #236."""
    primary = auto_models.choose("text_to_image", POSTER, None, catalog)
    assert primary["model"] == FLARE_T2I and primary["category"] == "poster_text"
    assert primary["reason"]["zh"] == "海报/带字"
    assert auto_models.pill_tooltip(primary, "zh") == "自动选择：海报/带字"
    assert auto_models.pill_label(primary) == "Auto · GPT Image 2.6 Flare"
    ids = {m["id"] for m in catalog["features"]["text_to_image"]["models"]}
    assert auto_models.table_runtime_fallback_choice("text_to_image", primary, FLARE_T2I, ids) is None
    assert auto_models.registered_runtime_fallback("text_to_image", primary, ids) in (None, "", [])


def test_canvas_fallback_choice_has_no_poster_row_fallback(catalog):
    """Auto Flare on a poster prompt has no registered row fallback; #236 also has no distinct default."""
    choice = canvas._fallback_choice("generate_image", {"prompt": POSTER, "auto_model": True}, FLARE_T2I)
    assert choice is None


def test_masked_fallback_choice_uses_flare_edit(catalog):
    choice = canvas._fallback_choice(
        "edit_region",
        {"id": "shape:a", "prompt": "redo the sky", "x": 0, "y": 0, "width": 8, "height": 8, "auto_model": True},
        SUN_EDIT,
    )
    assert choice["model"] == FLARE_EDIT and choice["fallback"] == SUN_EDIT
    assert choice.get("edit_model") == FLARE_EDIT
    tip = auto_models.pill_tooltip(choice, "zh")
    assert auto_models.short_name(SUN_EDIT) in tip and auto_models.short_name(FLARE_EDIT) in tip


def test_preferred_in_tip_equals_table_row_model_not_hardcoded(catalog):
    """Masked still registers a runtime fallback; the tip names the table row model (not a hardcoded id)."""
    masked = auto_models.load_table()["image_edit"]["masked"]
    primary = auto_models.choose("image_edit", "redo the sky", None, catalog, masked=True)
    ids = {m["id"] for m in catalog["features"]["image_edit"]["models"]}
    fb = auto_models.table_runtime_fallback_choice("image_edit", primary, primary["model"], ids)
    assert fb["fallback"] == masked["model"]
    assert auto_models.short_name(masked["model"]) in auto_models.pill_tooltip(fb, "zh")


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


def test_poster_has_no_table_runtime_fallback(catalog):
    primary = auto_models.choose("text_to_image", POSTER, None, catalog)
    ids = {m["id"] for m in catalog["features"]["text_to_image"]["models"]}
    assert auto_models.table_runtime_fallback_choice("text_to_image", primary, SUN_T2I, ids) is None
    assert auto_models.table_runtime_fallback_choice("text_to_image", primary, FLARE_T2I, ids) is None


def test_poster_flare_failure_has_no_registered_retry(catalog):
    primary = auto_models.choose("text_to_image", POSTER, None, catalog)
    ids = {m["id"] for m in catalog["features"]["text_to_image"]["models"]}
    assert auto_models.table_runtime_fallback_choice("text_to_image", primary, FLARE_T2I, ids) is None
    choice = canvas._fallback_choice("generate_image", {"prompt": POSTER, "auto_model": True}, FLARE_T2I)
    assert choice is None  # no registered fallback; default is also Flare


@pytest.mark.asyncio
async def test_timeout_cap_running_fails_logs_id_no_flare(ws, monkeypatch, caplog):
    from ComfyArt.bot.local_llm import model_call_failed
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": POSTER, "confirmed": True})
    started = wavespeed._jobs[task]["started"]
    monkeypatch.setattr(wavespeed, "IMAGE_JOB_TIMEOUT", 1.0)
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 1.0)
    monkeypatch.setattr(wavespeed.time, "time", lambda: started + 2)
    with caplog.at_level("WARNING"):
        hist = await wavespeed.poll(task)
    entry = hist[f"ws:{task}"]
    assert entry["status"]["completed"]
    assert entry["generation_succeeded"] is False
    info = entry["status"]["messages"][0][1]
    assert info["ws_kind"] == "timeout" and info["ws_task_id"] == task
    assert info["fallback_blocked"] is True
    assert task in caplog.text and "no Flare" in caplog.text and "timeout=" in caplog.text
    # Tool-result shaped payload carrying the poll failure info
    tool = {"status": "error", "error": {"kind": "timeout", "fallback_blocked": True, "task_id": task},
            "model": SUN_T2I}
    assert model_call_failed("generate_image", {"prompt": POSTER}, json.dumps(tool)) is None
    assert model_call_failed("generate_image", {"prompt": POSTER}, json.dumps(hist)) is None
    assert len(ws["submits"]) == 1
    assert wavespeed._jobs[task]["started"] == started
    assert await wavespeed.poll(task) == hist
    assert len(ws["submits"]) == 1


@pytest.mark.asyncio
async def test_before_cap_running_keeps_original(ws, monkeypatch):
    ws["status"] = "processing"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": POSTER, "confirmed": True})
    started = wavespeed._jobs[task]["started"]
    monkeypatch.setattr(wavespeed, "IMAGE_JOB_TIMEOUT", 100)
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 100)
    monkeypatch.setattr(wavespeed.time, "time", lambda: started + 10)
    hist = await wavespeed.poll(task)
    assert not hist[f"ws:{task}"]["status"]["completed"]
    assert len(ws["submits"]) == 1
    assert wavespeed._jobs[task]["started"] == started


@pytest.mark.asyncio
async def test_timeout_cap_status_completed_uses_original_no_flare(ws, monkeypatch):
    """At JOB_TIMEOUT a final free status GET that finds completed uses the original image; no Flare."""
    ws["status"] = "completed"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": POSTER, "confirmed": True})
    started = wavespeed._jobs[task]["started"]
    monkeypatch.setattr(wavespeed, "IMAGE_JOB_TIMEOUT", 1.0)
    monkeypatch.setattr(wavespeed, "JOB_TIMEOUT", 1.0)
    monkeypatch.setattr(wavespeed.time, "time", lambda: started + 2)
    hist = await wavespeed.poll(task)
    entry = hist[f"ws:{task}"]
    assert entry["generation_succeeded"] is True
    assert entry.get("model_choice") is None or entry.get("model_choice", {}).get("fallback") is None
    assert len(ws["submits"]) == 1
    assert wavespeed._jobs[task].get("fallback_blocked") is not True


@pytest.mark.asyncio
async def test_failed_prediction_no_extra_submit(ws, monkeypatch):
    ws["status"] = "failed"
    ws["error"] = "provider 502"
    task = await wavespeed.submit({"feature": "text_to_image", "prompt": POSTER, "confirmed": True})
    hist = await wavespeed.poll(task)
    assert hist[f"ws:{task}"]["status"]["completed"] is True
    assert len(ws["submits"]) == 1


def test_image_vs_video_job_timeout_constants():
    """#873: image jobs 10 min; video/other keep 30 min (split from the old shared 30 min)."""
    assert wavespeed.IMAGE_JOB_TIMEOUT == 10 * 60
    assert wavespeed.JOB_TIMEOUT == 30 * 60
    assert wavespeed._job_timeout_for({"feature": "text_to_image"}) == wavespeed.IMAGE_JOB_TIMEOUT
    assert wavespeed._job_timeout_for({"feature": "image_edit"}) == wavespeed.IMAGE_JOB_TIMEOUT
    assert wavespeed._job_timeout_for({"feature": "text_to_video"}) == wavespeed.JOB_TIMEOUT
    assert wavespeed._job_timeout_for({"feature": "image_to_video"}) == wavespeed.JOB_TIMEOUT
    assert wavespeed._job_timeout_for({"feature": "music"}) == wavespeed.JOB_TIMEOUT


def test_manual_sunburst_never_triggers_872_auto_fallback(catalog):
    """Manually picked Sunburst must not take the #873 tip-row Flare path (no auto_model)."""
    choice = canvas._fallback_choice(
        "generate_image", {"prompt": POSTER, "model": SUN_T2I}, SUN_T2I)
    assert choice is not None  # #236 may still offer the feature default after confirm
    assert choice["category"] == "fallback"  # not poster_text / tip-row
    assert choice["model"] == FLARE_T2I and choice["fallback"] == SUN_T2I
    assert "首选" not in (choice.get("reason") or {}).get("zh", "")
    tip = auto_models.pill_tooltip(choice, "zh")
    # #873 auto tip-row starts with 「自动选择：海报/带字」; #236 must stay on the table/default fallback shape
    assert not tip.startswith("自动选择：海报/带字"), tip
    assert "按对应表改用备用模型" in tip
