"""#1003 (Refs #911) product 23:0x ruling: finals attach ONLY the selected cell crop.

No paid API, no network, no browser. The crop uses the actually detected grid dividers
(cells are unequal), removes grid lines and the panel number, is archived with its
detected coordinates and sha256, and replaces the whole delivered grid as the
composition reference. Uncertain detection blocks the final instead of guessing thirds.
A short direction-free per-panel content note may reach finals; directional wording is
rejected, never scrubbed. The preview stage is byte-for-byte unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import io
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from multi_angle_plan_fixture import HEADPHONES_PLAN, GRID_X, GRID_Y, grid_png, preview_url
from ComfyArt.api import multi_angle as ma, multi_angle_crop as mc
from test_multi_angle_stages_911 import run, setup, choose, REF  # noqa: F401

REAL_PREVIEW = Path("/workspace/qa1003-5cf1a349-paid-preview/downloads/preview-9x16.png")
REAL_PLAN = Path("/workspace/qa1003-5cf1a349-paid-preview/structured-plan.json")
# sha256 of the assembled preview prompt for HEADPHONES_PLAN at f99887e9 (before this change).
PREVIEW_PROMPT_SHA_F99887E9 = "e3610817d925343dd139ffb5f9182ea1ee69a00f7e1eabbdfbf54938e85d415f"


def _ink(png: bytes):
    import numpy as np
    return np.asarray(Image.open(io.BytesIO(png)).convert("L")) < mc.DARK


def deliver(rows, *, url=None, plan=HEADPHONES_PLAN):
    setup(rows)
    args, blocked = ma.prepare({"composition_plan": plan, "skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None, blocked
    meta = args["_multi_angle"]
    assert ma.reserve(meta) is None
    ma.submitted(meta, {"ids": ["preview-holder"], "submitted": True})
    row = {"id": "preview-holder", "status": "done", "placed": True, "shapes": ["preview-shape"]}
    if url is not False:
        row["urls"] = [url or preview_url()]
    ma.record_wait({"results": [row]})
    return args


# ---- divider detection -------------------------------------------------------------------

@pytest.mark.skipif(not REAL_PREVIEW.is_file(), reason="real 5cf1 preview archive not on this box")
def test_real_5cf1_preview_dividers_are_detected_not_equal_thirds():
    data = REAL_PREVIEW.read_bytes()
    grid = mc.detect_grid(Image.open(io.BytesIO(data)).convert("RGB"))
    assert grid["size"] == [1440, 2560]
    (x1, x2), (y1, y2) = grid["x"], grid["y"]
    assert abs(x1 - 500) <= 4 and abs(x2 - 958) <= 4
    assert abs(y1 - 861) <= 4 and abs(y2 - 1702) <= 4
    assert abs(x1 - 1440 / 3) > 10  # really unequal: not the 480/960 equal-thirds split
    for cell in (1, 2, 3):
        png, info = mc.crop_cell(data, cell)
        ink = _ink(png)
        assert info["label_removed"] is True
        # No divider/frame remains: no near-continuous ink column/row along any crop edge.
        assert ink[:, :4].mean() < 0.02 and ink[:, -4:].mean() < 0.02
        assert ink[:4].mean() < 0.02 and ink[-4:].mean() < 0.02
        lx0, ly0, lx1, ly1 = info["label_box"]
        assert not ink[ly0:ly1, lx0:lx1].any()  # the number glyph is gone
        assert ink.mean() > 0.01  # the drawing itself is kept


@pytest.mark.parametrize("slant", [0, 12])
def test_synthetic_unequal_grid_dividers_and_crop_exclude_lines_and_label(slant):
    data = grid_png(slant=slant)
    grid = mc.detect_grid(Image.open(io.BytesIO(data)).convert("RGB"))
    assert [round(v) for v in grid["x"]] == list(GRID_X)
    assert [round(v) for v in grid["y"]] == list(GRID_Y)
    bx, by = [0, *GRID_X, 900], [0, *GRID_Y, 1600]
    for cell in range(1, 10):
        png, info = mc.crop_cell(data, cell)
        r, c = divmod(cell - 1, 3)
        x0, y0, x1, y1 = info["box"]
        assert bx[c] < x0 < bx[c] + 20 and bx[c + 1] - 20 < x1 < bx[c + 1]
        assert by[r] < y0 < by[r] + 20 and by[r + 1] - 20 < y1 < by[r + 1]
        ink = _ink(png)
        assert ink[:, :3].sum() == 0 and ink[:, -3:].sum() == 0 and ink[:3].sum() == 0 and ink[-3:].sum() == 0
        assert info["label_removed"] and not ink[:60, :60].any()  # synthetic label lives at +10..+40
        assert ink.mean() > 0.005  # the ellipse drawing survives
        assert info["sha256"] == hashlib.sha256(png).hexdigest()


def test_drawing_is_never_whitened_when_no_isolated_label():
    data = grid_png(labels=False)
    png, info = mc.crop_cell(data, 5)
    assert info["label_removed"] is False and info["label_box"] is None
    x0, y0, x1, y1 = info["box"]
    original = Image.open(io.BytesIO(data)).convert("RGB").crop((x0, y0, x1, y1))
    assert Image.open(io.BytesIO(png)).convert("RGB").tobytes() == original.tobytes()


def _ambiguous():
    img = Image.open(io.BytesIO(grid_png())).convert("RGB")
    ImageDraw.Draw(img).line([(220, 0), (220, 1600)], fill="black", width=3)  # rival divider in the same band
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize("data", [grid_png(lines=False), grid_png(xs=(450, 460)), _ambiguous(),
                                  b"not an image"], ids=["no-lines", "off-thirds", "rival-line", "garbage"])
def test_low_confidence_detection_raises(data):
    with pytest.raises(mc.CropError):
        mc.crop_cell(data, 1)


# ---- final wiring ------------------------------------------------------------------------

def test_final_refs_are_subject_then_cell_crop_never_whole_grid(run):
    rows, _ = run
    url = preview_url()
    deliver(rows, url=url)
    choose(rows, ("1", "2", "3"))
    for panel in ("1", "2", "3"):
        final, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": panel})
        assert blocked is None, blocked
        crop = final["_multi_angle"]["composition_crop"]
        assert final["refs"] == [REF, crop["ref"]] and final["ref_modes"] == ["content", "composition"]
        assert "preview-shape" not in final["refs"] and url not in final["refs"]
        assert crop["cell"] == int(panel) and crop["source"] == url
        assert [round(v) for v in crop["dividers"]["x"]] == list(GRID_X)
        assert [round(v) for v in crop["dividers"]["y"]] == list(GRID_Y)
        # The archived crop exists under the app output dir and matches the recorded sha256.
        from ComfyArt.api._common import view_path
        path = view_path(crop["ref"])
        assert hashlib.sha256(open(path, "rb").read()).hexdigest() == crop["sha256"]
        assert os.path.commonpath([path, ma_out()]) == ma_out()
        assert "The attached composition reference IS that selected cell" in final["prompt"]
        # Ledger audit trail on reserve and after submission.
        assert ma.reserve(final["_multi_angle"]) is None
        assert ma._root("chat-ma")[1][ma.LEDGER][f"final:{panel}"]["composition_crop"] == crop
        ma.submitted(final["_multi_angle"], {"ids": [f"f{panel}"], "submitted": True})
        assert ma._root("chat-ma")[1][ma.LEDGER][f"final:{panel}"]["composition_crop"] == crop


def ma_out():
    import folder_paths
    return os.path.abspath(os.path.join(folder_paths.get_output_directory(), mc.SUBFOLDER))


@pytest.mark.parametrize("url", [False, "/api/view?filename=missing.png&subfolder=wavespeed&type=output"])
def test_unknown_preview_file_blocks_final_no_whole_grid_fallback(run, url):
    rows, sent = run
    deliver(rows, url=url)
    choose(rows, ("1",))
    _, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "1"})
    assert blocked is not None and blocked["submitted"] is False
    assert "final:1" not in ma._root("chat-ma")[1][ma.LEDGER] and sent == []


def test_low_confidence_preview_blocks_final(run):
    rows, sent = run
    import folder_paths
    root = os.path.join(folder_paths.get_output_directory(), "wavespeed")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "nolines.png"), "wb") as f:
        f.write(grid_png(lines=False))
    deliver(rows, url="/api/view?filename=nolines.png&subfolder=wavespeed&type=output")
    choose(rows, ("2",))
    _, blocked = ma.prepare({"skill": ma.SKILL, "multi_angle_stage": "final", "composition_id": "2"})
    assert blocked["submitted"] is False and "no equal-thirds guess" in blocked["error"]
    assert sent == []


# ---- per-panel content ------------------------------------------------------------------

CONTENT = {"1": "both earcups and the padded headband fully visible",
           "2": "earcup depth, yokes, headband curve",
           "3": "single earcup outer shell disc and the headband edge as a strict side profile"}


def test_final_time_panel_content_is_injected_without_mutating_frozen_plan(run):
    rows, _ = run
    deliver(rows)
    frozen = copy.deepcopy(ma._root("chat-ma")[1][ma.LEDGER]["composition_plan"])
    choose(rows, ("1", "2", "3"))
    for panel, text in CONTENT.items():
        final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": panel, "panel_content": text})
        assert blocked is None, blocked
        assert final["prompt"].endswith(f"\nPanel content: {text}")
        assert "panel_content" not in final  # never forwarded to the page/provider
    assert ma._root("chat-ma")[1][ma.LEDGER]["composition_plan"] == frozen
    final, _ = ma.prepare({"skill": ma.SKILL, "composition_id": "1"})
    assert "Panel content:" not in final["prompt"]


@pytest.mark.parametrize("text", [
    "earcup closer to the camera", "toward the viewer's right", "subject's left earcup", "left earcup shell",
    "facing right", "镜头右侧", "机位偏左", "观者一侧的耳罩", "x" * 201, 7])
def test_directional_or_invalid_content_is_rejected_not_edited(run, text):
    rows, sent = run
    deliver(rows)
    choose(rows, ("2",))
    _, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "2", "panel_content": text})
    assert blocked is not None and blocked["submitted"] is False and sent == []
    plan = copy.deepcopy(HEADPHONES_PLAN)
    plan["panels"][1]["content"] = text
    with pytest.raises(ValueError):
        ma.validate_plan(plan)


def test_plan_content_field_is_optional_frozen_and_injected(run):
    rows, _ = run
    plan = copy.deepcopy(HEADPHONES_PLAN)
    for panel in plan["panels"]:
        panel["content"] = CONTENT.get(panel["id"], "")
    assert "content" not in ma.validate_plan(HEADPHONES_PLAN)["panels"][0]  # legacy plans unchanged
    clean = ma.validate_plan(plan)
    assert clean["panels"][1]["content"] == CONTENT["2"] and "content" not in clean["panels"][4]
    deliver(rows, plan=plan)
    choose(rows, ("2",))
    final, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "2"})
    assert blocked is None and final["prompt"].endswith(f"\nPanel content: {CONTENT['2']}")
    _, blocked = ma.prepare({"skill": ma.SKILL, "composition_id": "2", "panel_content": "yokes only"})
    assert blocked is not None and "frozen plan wins" in blocked["error"]


def test_panel_content_on_preview_is_blocked(run):
    rows, _ = run
    setup(rows)
    _, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "panel_content": CONTENT["2"]})
    assert blocked is not None and blocked["submitted"] is False


# ---- preview unchanged ------------------------------------------------------------------

def test_preview_prompt_is_byte_identical_to_f99887e9_and_ignores_content(run):
    rows, _ = run
    setup(rows)
    args, blocked = ma.prepare({"composition_plan": HEADPHONES_PLAN, "skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None
    assert hashlib.sha256(args["prompt"].encode()).hexdigest() == PREVIEW_PROMPT_SHA_F99887E9
    assert args["refs"] == [REF] and args["ref_modes"] == ["content"]
    plan = copy.deepcopy(HEADPHONES_PLAN)
    for panel in plan["panels"]:
        panel["content"] = CONTENT.get(panel["id"], "")
    with_content, blocked = ma.prepare({"composition_plan": plan, "skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None and with_content["prompt"] == args["prompt"]


# ---- default agent flow: planner-produced content (no harness panel_content) -----------

def test_agent_hint_and_schema_ask_planner_for_direction_free_content():
    from ComfyArt.bot import skill_output
    from ComfyArt.api.mcp_tools import canvas
    hint = skill_output.run_hint(ma.SKILL)
    assert "panels:[{id,name,description,geometry,appearance,content} x9]" in hint
    assert "Give every panel a short content (max 200 characters)" in hint
    assert "never left/right, camera, facing or other direction words in content" in hint
    assert "pass the same kind of short note as panel_content on that final call" in hint
    props = canvas.SPECS["generate_image"]["inputSchema"]["properties"]
    panel = props["composition_plan"]["properties"]["panels"]["items"]["properties"]
    assert "Give every panel one" in panel["content"]["description"]
    assert "Never left/right, camera, facing or direction words" in props["panel_content"]["description"]


@pytest.mark.asyncio
async def test_default_flow_planner_content_reaches_finals_without_panel_content(run):
    from ComfyArt.api.mcp_tools import canvas
    from test_multi_angle_stages_911 import confirm_quote, DESC
    rows, sent = run
    plan = copy.deepcopy(HEADPHONES_PLAN)
    for panel in plan["panels"]:
        panel["content"] = CONTENT.get(panel["id"], f"panel {panel['id']} visible structures")
    setup(rows)
    confirm_quote(rows)
    relay = canvas._relay("generate_image")
    first = await relay({"composition_plan": plan, "skill": ma.SKILL, "multi_angle_stage": "preview", "prompt": DESC})
    assert len(sent) == 1
    preview_prompt = sent[0][1]["prompt"]
    assert "Panel content" not in preview_prompt and not any(t in preview_prompt for t in CONTENT.values())
    assert ma._root("chat-ma")[1][ma.LEDGER]["composition_plan"]["panels"][1]["content"] == CONTENT["2"]
    ma.record_wait({"results": [{"id": first["ids"][0], "status": "done", "placed": True, "shapes": ["preview"],
                                 "urls": [preview_url()]}]})
    choose(rows, ("1", "2", "3"))
    for panel in ("1", "2", "3"):
        await relay({"multi_angle_stage": "final", "composition_id": panel})  # agent passes no panel_content
    assert len(sent) == 4
    for (_, args), panel in zip(sent[1:], ("1", "2", "3")):
        assert args["prompt"].endswith(f"\nPanel content: {CONTENT[panel]}")
        assert "panel_content" not in args and "ma-cell" in args["refs"][-1]


def test_preview_prompt_with_planner_content_matches_pinned_sha(run):
    rows, _ = run
    setup(rows)
    plan = copy.deepcopy(HEADPHONES_PLAN)
    for panel in plan["panels"]:
        panel["content"] = CONTENT.get(panel["id"], f"panel {panel['id']} visible structures")
    args, blocked = ma.prepare({"composition_plan": plan, "skill": ma.SKILL, "multi_angle_stage": "preview"})
    assert blocked is None
    assert hashlib.sha256(args["prompt"].encode()).hexdigest() == PREVIEW_PROMPT_SHA_F99887E9
