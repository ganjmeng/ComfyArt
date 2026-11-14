"""#982 A-class Full App mock e2e ($0): no skill run submits an undeclared canvas.

Real built app (dist/), real ComfyArt routes, real chat panel, real LocalLlmProvider
with a scripted LLM, real canvas MCP dispatch and the real generate_image handler.
WaveSpeed is the local mock and nothing is paid. The scripted model deliberately
omits width/height/ratio/count, like the $0 audit did: the server-side contract must
fill them, and the provider request must carry a size signal instead of letting the
schema default decide the pixels.

Covered:
  logo-material-explorer: upload + required notes -> 1x1024x1024 (1:1), count=1,
    the uploaded logo ref preserved.
  character-sheet-design (expression template): 1x2048x1152 (16:9), count=1,
    preset=expression, the uploaded character ref preserved.
  poster-differentiated-compiler (no OUTPUTS, no pin): the #982 1024x1024 floor,
    so the old "no size -> 512x512" path is gone even for unruled skills.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (real routes + local mock WaveSpeed)
from test_skill_e2e_portrait_studio import ws_forward  # noqa: F401
from test_a_class_fullapp_e2e_911 import (  # noqa: F401
    _attached, _calls, _last_tool_json, _open_skill, _refs, _reply, _send_default, _wait,
    built_dist, local_agent, no_paid_keys,
)

pw = pytest.importorskip("playwright.async_api")

LOGO = "logo-material-explorer"
CHARACTER = "character-sheet-design"
POSTER = "poster-differentiated-compiler"


def _still_script(state: dict, sid: str, prompt: str):
    """The default path: read the skill, generate once with NO size/count, wait, finish."""
    def respond(messages: list, n: int):
        attached = _attached(messages)
        if attached:
            state["attached"] = attached
        if n == 0:
            return _calls(("skill", {"action": "read", "name": sid}))
        if n == 1:
            return _calls(("generate_image", {
                "prompt": prompt,
                "skill": sid,
                "refs": _refs(state.get("attached") or []),
                # width/height/ratio/count deliberately omitted.
            }))
        if n == 2:
            ids = (_last_tool_json(messages, "ids") or {}).get("ids") or []
            return _calls(("wait_generation", {"ids": ids}))
        return _reply("done")

    return respond


def _gen_args(state: dict) -> tuple[str, dict]:
    gens = [(name, args) for name, args in state["mcp"] if name == "generate_image"]
    assert len(gens) == 1, gens
    return gens[0]


def _ratio(text: str) -> float:
    a, b = text.replace("x", ":").replace("*", ":").split(":")[:2]
    return float(a) / float(b)


def _assert_provider_canvas(body: dict, width: int, height: int) -> None:
    """The WaveSpeed request must carry the locked canvas, not omit size."""
    size = body.get("size")
    if size:
        assert abs(_ratio(str(size)) - width / height) < 0.02, body
        return
    ar = body.get("aspect_ratio")
    assert ar, f"provider request has no size or aspect_ratio: {body}"
    assert abs(_ratio(str(ar)) - width / height) < 0.02, body
    res = body.get("resolution")
    if res:
        assert res == ("1k" if max(width, height) <= 1024 else "2k"), body


def _add_flare_models(monkeypatch) -> None:
    """Expose the Auto defaults on the mock model list (the 911 e2e pattern)."""
    import test_e2e_comment_edit as ce
    need = ("openai/gpt-image-2.6-flare/text-to-image", "openai/gpt-image-2.6-flare/edit")
    current = list(ce.MODELS)
    for mid in need:
        if not any(m["model_id"] == mid for m in current):
            current.append(ce.FIXTURE[mid])
    monkeypatch.setattr(ce, "MODELS", current)


async def test_fullapp_logo_default_is_one_1024_square(app_url, mock_ws, local_agent,  # noqa: F811
                                                       ws_forward, monkeypatch, tmp_path):
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _still_script(state, LOGO, "brushed metal logo material study")
    logo = tmp_path / "logo-982.png"
    img = Image.new("RGB", (1024, 1024), (246, 246, 246))
    d = ImageDraw.Draw(img)
    d.ellipse((280, 280, 744, 744), outline=(24, 24, 24), width=42)
    d.rectangle((478, 372, 546, 636), fill=(24, 24, 24))
    img.save(logo)

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", LOGO, ws_forward,  # noqa: F811
                                        dialog_ref=logo, dialog_text="brushed metal, neutral studio")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 1, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            name, args = _gen_args(state)
            assert name == "generate_image"
            assert (args.get("width"), args.get("height"), args.get("ratio"), args.get("count")) == \
                (1024, 1024, "1:1", 1), args
            assert args.get("size_lock") is True
            assert args.get("skill") == LOGO
            base_refs = _refs(state.get("attached") or [])
            assert base_refs and args.get("refs") == base_refs, (base_refs, args)
            # The skill read returned the same contract to the model (not a UI string).
            read = _last_tool_json(state["messages"], "output")
            assert read and read["output"] == {"width": 1024, "height": 1024, "ratio": "1:1", "images": 1}, read
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            _assert_provider_canvas(mock_ws["submits"][0][1], 1024, 1024)
        finally:
            await browser.close()


async def test_fullapp_character_expression_template_is_2048x1152(app_url, mock_ws,  # noqa: F811
                                                                 local_agent, ws_forward, monkeypatch):
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _still_script(state, CHARACTER, "expression and pose character sheet")
    ref = Path(__file__).parent / "fixtures" / "person_911_3x4.jpg"

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", CHARACTER, ws_forward,  # noqa: F811
                                        dialog_ref=ref, preset_id="expression",
                                        composer_name="Realistic Human Character Design & Reference Sheets")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 1, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            _name, args = _gen_args(state)
            assert (args.get("width"), args.get("height"), args.get("ratio"), args.get("count")) == \
                (2048, 1152, "16:9", 1), args
            assert args.get("size_lock") is True
            assert args.get("skill") == CHARACTER
            assert args.get("preset") == "expression" and args.get("stage") == 1, args
            base_refs = _refs(state.get("attached") or [])
            assert base_refs and args.get("refs") == base_refs, (base_refs, args)
            read = _last_tool_json(state["messages"], "output")
            assert read and read["output"]["presets"]["expression"] == {
                "width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
                "name": "Expression & Pose Sheet"}, read
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            _assert_provider_canvas(mock_ws["submits"][0][1], 2048, 1152)
        finally:
            await browser.close()


async def test_fullapp_unruled_skill_gets_the_1024_floor_not_512(app_url, mock_ws,  # noqa: F811
                                                                local_agent, ws_forward, monkeypatch):
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _still_script(state, POSTER, "a poster key visual")

    ref = Path(__file__).parent / "fixtures" / "ma_subject_691.png"
    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", POSTER, ws_forward,  # noqa: F811
                                        dialog_ref=ref, dialog_text="a poster key visual")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 1, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            _name, args = _gen_args(state)
            assert (args.get("width"), args.get("height"), args.get("ratio")) == (1024, 1024, "1:1"), args
            assert args.get("size_lock") is True
            assert args.get("width") != 512 and args.get("height") != 512
            # The server floor is what reaches WaveSpeed; no silent schema default.
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            body = mock_ws["submits"][0][1]
            _assert_provider_canvas(body, 1024, 1024)
            assert body.get("size") != "512*512"
        finally:
            await browser.close()
