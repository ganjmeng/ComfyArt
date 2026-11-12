"""P1 hotfix (#911): Sunburst size tolerance and "a charged image is always delivered".

Bug on main 88cbd358: clothing-swap is pinned to openai/gpt-image-2.6-sunburst/edit and
locked to 1536×2048. Sunburst has no size field (only aspect_ratio + resolution 1k/2k/4k),
so 2k 3:4 comes back as 1664×2224. The exact-pixel size_lock rejected that already-charged
file (pred a266bb741a514ee8b664402a4a825854, $0.117) and the canvas got no image.

Fix (Tech, option A):
1. Sunburst-pinned skills (clothing-swap, studio-model) lock in ratio mode: ratio error <= 1%
   AND long side >= target long side. Pass -> the native file is delivered, no scale, no crop.
2. Every path: a charged file is ALWAYS delivered, even when the check fails. The failure is
   logged and carries a zh/en notice for the user. Nothing is resized to fake the target.

All provider calls go to a local mock (see test_wavespeed.ws). Nothing here is paid.
"""
from __future__ import annotations

import io
import json
import logging
import os
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

from ComfyArt.api import wavespeed
from ComfyArt.api.skill_size import (RATIO_MODE, audit_file, is_sunburst, ratio_error, ratio_ok,
                                     size_notice)
from test_wavespeed import MODELS, ws  # noqa: F401 - pytest fixture (local mock WaveSpeed)

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
SB_EDIT = "openai/gpt-image-2.6-sunburst/edit"
SB_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
QWEN = "wavespeed-ai/qwen-image-2.0/text-to-image"
PRED = "a266bb741a514ee8b664402a4a825854"


def _png(w: int, h: int, rgb=(12, 34, 56)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), rgb).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sunburst_catalog():
    added = [FIXTURE[m] for m in (SB_EDIT, SB_T2I, QWEN) if not any(x.get("model_id") == m for x in MODELS)]
    MODELS.extend(added)
    wavespeed._catalog.update({"at": 0.0, "models": {}})
    yield
    for m in added:
        MODELS.remove(m)
    wavespeed._catalog.update({"at": 0.0, "models": {}})


# ---------- QA 1-4: the ratio-mode validator ----------

def test_qa1_portrait_3x4_1664x2224_accepted_and_delivered_unscaled():
    body = _png(1664, 2224)
    out = audit_file(body, (1536, 2048), RATIO_MODE)
    assert out["match"] is True and out["error"] is None and out["notice"] is None
    assert out["provider_output"] == out["delivered"] == {"width": 1664, "height": 2224}
    assert out["requested"] == {"width": 1536, "height": 2048}
    assert out["ratio_error_pct"] == pytest.approx(0.2398, abs=1e-3)
    # exact mode would still call it a mismatch: the tolerance is only for ratio mode
    assert audit_file(body, (1536, 2048))["match"] is False


def test_qa2_landscape_4x3_2224x1664_accepted():
    out = audit_file(_png(2224, 1664), (2048, 1536), RATIO_MODE)
    assert out["match"] is True
    assert out["delivered"] == {"width": 2224, "height": 1664}


def test_qa3_ratio_error_exactly_1pct_accepted_1_01pct_rejected():
    # 1:1 target
    assert ratio_error((1000, 1000), (1010, 1000)) == Fraction(1, 100)
    assert ratio_ok((1000, 1000), (1010, 1000)) is True
    assert ratio_error((1000, 1000), (10101, 10000)) == Fraction(101, 10000)
    assert ratio_ok((1000, 1000), (10101, 10000)) is False
    # 3:4 target 1536×2048: 1818/2400 = 0.75 × 1.01 ; 30303/40000 = 0.75 × 1.0101
    assert ratio_error((1536, 2048), (1818, 2400)) == Fraction(1, 100)
    assert ratio_ok((1536, 2048), (1818, 2400)) is True
    assert ratio_error((1536, 2048), (30303, 40000)) == Fraction(101, 10000)
    assert ratio_ok((1536, 2048), (30303, 40000)) is False
    assert audit_file(_png(1818, 2400), (1536, 2048), RATIO_MODE)["match"] is True


def test_qa4_long_side_shorter_than_target_rejected():
    out = audit_file(_png(768, 1024), (1536, 2048), RATIO_MODE)
    assert ratio_error((1536, 2048), (768, 1024)) == 0  # ratio is perfect, long side is not
    assert out["match"] is False
    assert out["delivered"] == {"width": 768, "height": 1024}
    assert "768×1024" in out["notice"]["zh"] and "1536×2048" in out["notice"]["en"]
    assert ratio_ok((2048, 1536), (1024, 768)) is False


def test_only_sunburst_ids_get_ratio_mode():
    assert is_sunburst(SB_EDIT) and is_sunburst(SB_T2I)
    assert not is_sunburst("openai/gpt-image-2.5-flare/edit")
    assert not is_sunburst("wavespeed-ai/qwen-image-2.0/text-to-image")


# ---------- QA 5: rejected but charged -> still delivered, logged, notice ----------

async def _locked(ws, model, feature, body, *, w=1536, h=2048, mode=RATIO_MODE, **extra):
    ws["cdn"] = body
    inputs = {"feature": feature, "model": model, "prompt": "p", "width": w, "height": h, "size_lock": True, "confirmed": True, **extra}
    if mode:
        inputs["size_lock_mode"] = mode
    task = await wavespeed.submit(inputs)
    sent_model, payload = ws["submits"][-1]
    assert sent_model == model
    for key in ("size_lock", "size_lock_mode"):
        assert key not in payload  # internal flags never reach WaveSpeed
    hist = await wavespeed.poll(task)
    return task, payload, hist[f"ws:{task}"]


def _saved(out) -> bytes:
    import folder_paths
    ref = out["outputs"]["ws"]["images"][0]
    return wavespeed._read(os.path.join(folder_paths.get_output_directory(), ref["subfolder"], ref["filename"]))


async def test_qa1_poll_accepts_1664x2224_and_saves_original_bytes(ws, sunburst_catalog):
    body = _png(1664, 2224)
    task, payload, out = await _locked(ws, SB_T2I, "text_to_image", body)
    assert payload.get("aspect_ratio") == "3:4" and payload.get("resolution") == "2k"
    assert "size" not in payload
    assert out["generation_succeeded"] is True
    assert out["size_check"] == {"match": True, "mode": "ratio", "ratio_error_pct": pytest.approx(0.2398, abs=1e-3)}
    assert "size_notice" not in out
    assert out["delivered_size"] == out["provider_output"] == {"width": 1664, "height": 2224}
    assert _saved(out) == body  # not scaled, not cropped
    assert wavespeed._jobs[task]["size_mode"] == RATIO_MODE


async def test_qa5_rejected_but_charged_is_delivered_logged_and_noticed(ws, sunburst_catalog, caplog):
    body = _png(768, 1024)
    caplog.set_level(logging.WARNING)
    task, _payload, out = await _locked(ws, SB_T2I, "text_to_image", body)
    assert out["status"]["status_str"] == "completed"
    assert out["generation_succeeded"] is True
    assert out["outputs"]["ws"]["images"], "a charged image must never be dropped"
    assert _saved(out) == body
    assert out["size_check"]["match"] is False and out["size_check"]["mode"] == "ratio"
    notice = out["size_notice"]
    assert notice["zh"].startswith("尺寸提示：") and "768×1024" in notice["zh"] and "1536×2048" in notice["zh"]
    assert notice["en"].startswith("Size notice:") and "not stretched or cropped" in notice["en"]
    assert any("P1 size check failed for charged task" in r.getMessage() and task in r.getMessage() for r in caplog.records)
    submits = len(ws["submits"])
    await wavespeed.poll(task)
    assert len(ws["submits"]) == submits == 1  # no retry, no second charge


async def test_qa5_main_bug_exact_lock_on_sunburst_no_longer_drops_the_image(ws, sunburst_catalog):
    """The exact main 88cbd358 request (no ratio mode): 1664×2224 vs 1536×2048 is now delivered with a notice."""
    body = _png(1664, 2224)
    _task, _payload, out = await _locked(ws, SB_EDIT, "image_edit", body, mode=None,
                                         images=["https://cdn.test/person.png", "https://cdn.test/garment.png"])
    assert out["generation_succeeded"] is True
    assert _saved(out) == body
    assert out["size_check"] == {"match": False, "mode": "exact"}
    assert "1664×2224" in out["size_notice"]["zh"] and "1536×2048" in out["size_notice"]["en"]


async def test_qa5_exact_skill_mismatch_and_unreadable_also_delivered(ws, sunburst_catalog):
    """Safety net is for all paths, not only Sunburst: linkedin 1584×396 lock, wrong file."""
    t2i = QWEN
    _t, payload, out = await _locked(ws, t2i, "text_to_image", _png(2048, 682), w=1584, h=396, mode=None)
    assert payload.get("size") == "1584*396"
    assert out["generation_succeeded"] is True and out["outputs"]["ws"]["images"]
    assert "2048×682" in out["size_notice"]["zh"]
    _t, _p, dead = await _locked(ws, t2i, "text_to_image", b"NOTPNG", w=1584, h=396, mode=None)
    assert dead["generation_succeeded"] is True and dead["outputs"]["ws"]["images"]
    assert "读不出" in dead["size_notice"]["zh"] or "没能读出" in dead["size_notice"]["zh"]


async def test_ratio_mode_flag_ignored_for_non_sunburst_model(ws, sunburst_catalog):
    t2i = QWEN
    task, _p, out = await _locked(ws, t2i, "text_to_image", _png(1664, 2224))
    assert "size_mode" not in wavespeed._jobs[task]
    assert out["size_check"]["mode"] == "exact" and out["size_check"]["match"] is False
    assert out["generation_succeeded"] is True  # still delivered


def test_size_notice_is_bilingual():
    n = size_notice((1536, 2048), (768, 1024), RATIO_MODE)
    assert set(n) == {"zh", "en"}


# ---------- pin wiring: which skills lock in ratio mode ----------

def _pipeline(skill: str, refs: bool, size: dict) -> dict:
    from ComfyArt.api.mcp_tools import canvas
    from ComfyArt.bot.skill_output import apply_generate

    args = {"prompt": "p", "skill": skill, **size}
    if refs:
        args["refs"] = ["shape:person", "shape:garment"]
    args = apply_generate(args)
    choice = canvas._auto_choice("generate_image", dict(args))
    assert choice and choice.get("category") == "skill"
    return canvas._pin_args(dict(args), choice)


def test_clothing_swap_pin_locks_in_ratio_mode():
    out = _pipeline("clothing-swap", True, {})
    assert out["edit_model"] == SB_EDIT
    assert (out["width"], out["height"], out["ratio"], out["size_lock"]) == (1536, 2048, "3:4", True)
    assert out["size_lock_mode"] == RATIO_MODE


def test_studio_model_pin_locks_in_ratio_mode_only_when_locked():
    locked = _pipeline("studio-model", True, {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True})
    assert locked["edit_model"] == SB_EDIT and locked["size_lock_mode"] == RATIO_MODE
    t2i = _pipeline("studio-model", False, {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True})
    assert t2i["model"] == SB_T2I and t2i["size_lock_mode"] == RATIO_MODE
    free = _pipeline("studio-model", True, {"ratio": "3:4", "width": 1536, "height": 2048})
    assert "size_lock" not in free and "size_lock_mode" not in free


def test_other_pins_never_get_ratio_mode():
    for skill in ("ai-model", "pose-fission"):
        out = _pipeline(skill, True, {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True})
        assert "size_lock_mode" not in out and "size_lock" not in out


# ---------- QA 6 (backend half): clothing-swap / studio-model full flow to a delivered file ----------

def _page_inputs(pinned: dict) -> dict:
    """What generate.ts sends for a pinned call: feature from refs, size_lock + size_lock_mode from meta."""
    edit = bool(pinned.get("edit_model"))
    out = {"feature": "image_edit" if edit else "text_to_image", "model": pinned.get("edit_model") or pinned["model"],
           "prompt": pinned["prompt"], "width": pinned["width"], "height": pinned["height"], "size_lock": True, "confirmed": True}
    if edit:
        out["images"] = ["https://cdn.test/person.png", "https://cdn.test/garment.png"]
    if pinned.get("size_lock_mode"):
        out["size_lock_mode"] = pinned["size_lock_mode"]
    return out


@pytest.mark.parametrize("skill,refs,size", [
    ("clothing-swap", True, {}),
    ("studio-model", True, {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True}),
    ("studio-model", False, {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True}),
])
@pytest.mark.parametrize("file_wh,passes", [((1664, 2224), True), ((768, 1024), False)])
async def test_qa6_skill_full_flow_delivers_the_file(ws, sunburst_catalog, skill, refs, size, file_wh, passes):
    pinned = _pipeline(skill, refs, size)
    body = _png(*file_wh)
    ws["cdn"] = body
    task = await wavespeed.submit(_page_inputs(pinned))
    model, payload = ws["submits"][-1]
    assert model == (SB_EDIT if refs else SB_T2I)
    assert payload.get("aspect_ratio") == "3:4" and payload.get("resolution") == "2k" and "size" not in payload
    out = (await wavespeed.poll(task))[f"ws:{task}"]
    assert out["generation_succeeded"] is True
    assert _saved(out) == body
    assert out["size_check"]["match"] is passes
    assert ("size_notice" in out) is (not passes)


# ---------- page side (sizeLockPref.ts) ----------

def test_page_ratio_check_and_delivery_notice():
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--disable-warning=ExperimentalWarning",
         str(ROOT / "tests/js/size_tolerance_911_run.ts")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    got = json.loads(proc.stdout)
    assert got["qa1"] is None
    assert got["qa2"] is None
    assert got["exact1"] is True and got["over1"] is False
    assert got["exact1_34"] is True and got["over1_34"] is False
    assert got["short"]["mode"] == "ratio" and "768×1024" in got["short"]["notice"]
    assert got["short"]["notice"].startswith("尺寸提示：")
    assert got["exactMismatch"]["mode"] == "exact" and "2048×682" in got["exactMismatch"]["notice"]
    assert got["unread"]["got"] is None
    assert got["noLock"] is None
    jobs = (ROOT / "src/jobs.ts").read_text(encoding="utf-8")
    finish = jobs.split("async function finish(", 1)[1].split("\n}\n", 1)[0]
    assert "lockedDeliveryNotice(holder.meta, media)" in finish
    assert "throw new Error(refused)" not in finish
    # placement happens before (and regardless of) the notice
    assert finish.index("placers[job.placer") < finish.index("reportWarning(")
    for lang in ("zh", "en"):
        loc = json.loads((ROOT / f"src/locales/{lang}.json").read_text(encoding="utf-8"))
        assert "{0}" in loc["jobs.sizeNotice"] and "{1}" in loc["jobs.sizeNotice"]
        assert "{0}" in loc["jobs.sizeNoticeUnread"]
