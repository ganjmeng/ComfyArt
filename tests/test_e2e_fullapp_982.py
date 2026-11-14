"""#982 A-class Full App mock e2e ($0): typed defaults, no silent size.

Real built app (dist/), real ComfyArt routes, real chat panel, real LocalLlmProvider
with a scripted LLM, real canvas MCP dispatch and the real generate_image handler.
WaveSpeed is the local mock and nothing is paid.

The 512x512 in the #911 audit was the mock's fixed `RESULT` image
(`tests/test_e2e_comment_edit.py:45`), not a production size. The app always sends
width/height (`GENERATOR_DEFAULTS.resolution='1K'` -> `targetSize` -> `pixelSizeOf`);
this file asserts the *typed* size the contract chooses, not the mock file.

Covered:
  logo-material-explorer: 1x1024x1024 (1:1), count=1, logo ref preserved.
  character-sheet-design (expression): 1x2048x1152 (16:9), preset=expression.
  poster-differentiated-compiler: 1x1024x1360 (3:4), poster's instruction default.
  banner-design-director: 1x1824x1024 (16:9), the wide type default.
  meta-ads-creative-director: 3 calls (1:1/4:5/9:16), the multi-ratio pack.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (real routes + local mock WaveSpeed)
from test_skill_e2e_portrait_studio import ws_forward  # noqa: F401
from test_a_class_fullapp_e2e_911 import (  # noqa: F401
    _all_ids, _attached, _calls, _last_tool_json, _open_skill, _refs, _reply, _send_default, _wait,
    built_dist, local_agent, no_paid_keys,
)

pw = pytest.importorskip("playwright.async_api")

LOGO = "logo-material-explorer"
CHARACTER = "character-sheet-design"
POSTER = "poster-differentiated-compiler"
BANNER = "banner-design-director"
META = "meta-ads-creative-director"
MOBILE = "mobile-app-visual-design"
SUBJECT = Path(__file__).parent / "fixtures" / "ma_subject_691.png"


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


def _pack_script(state: dict, sid: str, ratios: tuple[str, ...]):
    """A multi-ratio pack: three generate_image calls, one ratio each, then wait."""
    def respond(messages: list, n: int):
        attached = _attached(messages)
        if attached:
            state["attached"] = attached
        if n == 0:
            return _calls(("skill", {"action": "read", "name": sid}))
        if 1 <= n <= len(ratios):
            return _calls(("generate_image", {
                "prompt": f"pack frame {ratios[n - 1]}",
                "skill": sid,
                "ratio": ratios[n - 1],
                "refs": _refs(state.get("attached") or []),
                # no width/height/count: the server must fill each call's canvas.
            }))
        if n == len(ratios) + 1:
            return _calls(("wait_generation", {"ids": _all_ids(messages)}))
        return _reply("done")

    return respond


def _gen_args(state: dict) -> list[dict]:
    return [args for name, args in state["mcp"] if name == "generate_image"]


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
            gens = _gen_args(state)
            assert len(gens) == 1, gens
            args = gens[0]
            assert (args.get("width"), args.get("height"), args.get("ratio"), args.get("count")) == \
                (1024, 1024, "1:1", 1), args
            assert args.get("size_lock") is True and args.get("skill") == LOGO
            base_refs = _refs(state.get("attached") or [])
            assert base_refs and args.get("refs") == base_refs, (base_refs, args)
            read = _last_tool_json(state["messages"], "output")
            assert read and read["output"] == {"width": 1024, "height": 1024, "ratio": "1:1", "images": 1}, read
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            # 1:1 1024x1024/1k is also what main already submitted, so the provider
            # body is NOT discriminating for this skill. The contract is the MCP args
            # and skill-read output above; 3:4 / 16:9 below are the discriminating cases.
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
            gens = _gen_args(state)
            assert len(gens) == 1, gens
            args = gens[0]
            assert (args.get("width"), args.get("height"), args.get("ratio"), args.get("count")) == \
                (2048, 1152, "16:9", 1), args
            assert args.get("size_lock") is True and args.get("skill") == CHARACTER
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


async def test_fullapp_poster_default_is_3to4_1024x1360(app_url, mock_ws,  # noqa: F811
                                                       local_agent, ws_forward, monkeypatch):
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _still_script(state, POSTER, "a poster key visual")

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", POSTER, ws_forward,  # noqa: F811
                                        dialog_ref=SUBJECT, dialog_text="a poster key visual")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 1, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            assert len(gens) == 1, gens
            args = gens[0]
            assert (args.get("width"), args.get("height"), args.get("ratio"), args.get("count")) == \
                (1024, 1360, "3:4", 1), args
            assert args.get("size_lock") is True
            # This is the case the HOLD named: poster's instruction says default 3:4.
            assert args.get("ratio") != "1:1"
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            _assert_provider_canvas(mock_ws["submits"][0][1], 1024, 1360)
        finally:
            await browser.close()


async def test_fullapp_banner_default_is_16to9_1824x1024(app_url, mock_ws,  # noqa: F811
                                                        local_agent, ws_forward, monkeypatch):
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _still_script(state, BANNER, "a wide campaign banner")

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", BANNER, ws_forward,  # noqa: F811
                                        dialog_ref=SUBJECT, dialog_text="a wide campaign banner")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 1, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            assert len(gens) == 1, gens
            args = gens[0]
            assert (args.get("width"), args.get("height"), args.get("ratio"), args.get("count")) == \
                (1824, 1024, "16:9", 1), args
            assert args.get("size_lock") is True
            assert (args.get("width"), args.get("height")) != (1024, 1024)
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            _assert_provider_canvas(mock_ws["submits"][0][1], 1824, 1024)
        finally:
            await browser.close()


async def test_fullapp_meta_ads_pack_submits_three_ratios(app_url, mock_ws,  # noqa: F811
                                                         local_agent, ws_forward, monkeypatch):
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    ratios = ("1:1", "4:5", "9:16")
    state["respond"] = _pack_script(state, META, ratios)

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", META, ws_forward,  # noqa: F811
                                        dialog_ref=SUBJECT, dialog_text="a paid-social pack")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 3, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            assert len(gens) == 3, gens
            assert [(a.get("width"), a.get("height"), a.get("ratio"), a.get("count")) for a in gens] == [
                (1024, 1024, "1:1", 1), (1024, 1280, "4:5", 1), (1024, 1824, "9:16", 1)], gens
            assert all(a.get("size_lock") is True and a.get("skill") == META for a in gens)
            assert len(mock_ws["submits"]) == 3, mock_ws["submits"]
            for body, (w, h) in zip([b for _m, b in mock_ws["submits"]],
                                    [(1024, 1024), (1024, 1280), (1024, 1824)]):
                _assert_provider_canvas(body, w, h)
        finally:
            await browser.close()


async def test_fullapp_mobile_default_is_9to21_880x2048(app_url, mock_ws,  # noqa: F811
                                                        local_agent, ws_forward, monkeypatch):
    """Design 6874380577: 9:19.5 is not enum-supported; 9:21 880x2048 must pass RATIOS."""
    _add_flare_models(monkeypatch)
    _provider, state = local_agent
    state["respond"] = _still_script(state, MOBILE, "a phone home screen mockup")

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, "en", MOBILE, ws_forward,  # noqa: F811
                                        dialog_ref=SUBJECT, dialog_text="a phone home screen mockup")
        try:
            await _send_default(pg)
            await _wait(lambda: len(mock_ws["submits"]) >= 1, timeout=150.0)
            await _wait(lambda: state.get("wait"), timeout=150.0)
            gens = _gen_args(state)
            assert len(gens) == 1, gens
            args = gens[0]
            assert (args.get("width"), args.get("height"), args.get("ratio"), args.get("count")) == \
                (880, 2048, "9:21", 1), args
            assert args.get("size_lock") is True
            assert len(mock_ws["submits"]) == 1, mock_ws["submits"]
            _assert_provider_canvas(mock_ws["submits"][0][1], 880, 2048)
        finally:
            await browser.close()
