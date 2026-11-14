"""#974 A-class Full App mock e2e ($0): multi-angle default input → four separate generate_image
calls → four canvas results.

The real built app (dist/), the real ComfyArt routes, the real chat panel, the real LocalLlmProvider
agent loop with a scripted LLM (no LLM call), the real canvas MCP dispatch and the real
generate_image handler. WaveSpeed is the local mock and nothing is submitted to it.

The scripted model names only the skill/prompt/refs, like a model following the skill text; the
server-side #974 lock must fill 1536x2048 / 3:4 and count=1 on every call. The same uploaded
subject shape id must be on all four calls, and the canvas must show four generated images.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (real routes + local mock WaveSpeed)
from test_skill_e2e_portrait_studio import ws_forward  # noqa: F401
from test_a_class_fullapp_e2e_911 import (  # noqa: F401  (shared Full App harness + autouse guards)
    _all_ids, _attached, _calls, _canvas_images, _last_tool_json, _open_skill, _refs, _reply,
    _send_default, _wait, built_dist, local_agent, no_paid_keys,
)

pw = pytest.importorskip("playwright.async_api")

SID = "universal-multi-angle-grid"
UPLOAD = Path(__file__).parent / "fixtures" / "ma_subject_691.png"
ANGLES = ("front view", "three-quarter view", "strict 90° side profile", "detail macro")


def _script(state: dict, lang: str):
    def respond(messages: list, n: int):
        state["messages"] = messages
        attached = _attached(messages)
        if attached:
            state["attached"] = attached
        if n == 0:
            return _calls(("skill", {"action": "read", "name": SID}))
        if n < 5:
            refs = _refs(state.get("attached") or [])
            return _calls(("generate_image", {
                # No width/height/ratio/count: the #974 server lock must fill all four.
                "prompt": f"same uploaded subject, {ANGLES[n - 1]}, 3:4 studio product photograph",
                "skill": SID,
                "refs": refs,
            }))
        if n == 5:
            return _calls(("wait_generation", {"ids": _all_ids(messages)}))
        return _reply("4 张独立角度图已放到画布。" if lang == "zh"
                      else "Done: four separate multi-angle stills are on the canvas.")

    return respond


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_multi_angle_default_is_four_separate_1536x2048_images(
        app_url, mock_ws, local_agent, ws_forward, monkeypatch, lang):  # noqa: F811
    # Auto picks openai/gpt-image-2.6-flare/edit; the local catalog fixture already carries it, so expose
    # it on the mock model list too (otherwise the page rejects the model before any submit).
    import test_e2e_comment_edit as ce
    flare = ce.FIXTURE["openai/gpt-image-2.6-flare/edit"]
    monkeypatch.setattr(ce, "MODELS", [m for m in ce.MODELS if m["model_id"] != flare["model_id"]] + [flare])
    _provider, state = local_agent
    state["respond"] = _script(state, lang)

    async with pw.async_playwright() as p:
        browser, pg = await _open_skill(p, app_url, lang, SID, ws_forward, dialog_ref=UPLOAD)
        try:
            await _send_default(pg)
            # Four separate paid submits (one per angle), never one count=4 grid.
            await _wait(lambda: len(mock_ws["submits"]) >= 4, timeout=150.0)
            assert len(mock_ws["submits"]) == 4, mock_ws["submits"]
            await _wait(lambda: state.get("wait"), timeout=150.0)
            rows = (state.get("wait") or {}).get("results") or []
            assert len(rows) == 4 and all(r.get("status") == "done" and r.get("placed") for r in rows), rows

            gens = [(name, args) for name, args in state["mcp"] if name == "generate_image"]
            assert len(gens) == 4, gens
            # Every call is one 3:4 1536x2048 image, even though the model passed no size.
            assert [(a.get("width"), a.get("height"), a.get("ratio"), a.get("count")) for _n, a in gens] == \
                [(1536, 2048, "3:4", 1)] * 4, [a for _n, a in gens]
            assert all(a.get("size_lock") is True for _n, a in gens)
            assert [a["prompt"] for _n, a in gens] == [
                f"same uploaded subject, {angle}, 3:4 studio product photograph" for angle in ANGLES]
            # Same uploaded subject shape id on every call; no call loses the reference.
            base_refs = [row["id"] for row in state["attached"]]
            assert len(base_refs) == 1, state["attached"]
            assert [[r for r in a.get("refs") or []] for _n, a in gens] == [[base_refs[0]]] * 4, \
                (base_refs, [a.get("refs") for _n, a in gens])
            assert all(a.get("skill") == SID for _n, a in gens)

            # The TS SKILL_OUTPUT row the page returned to the model is the same lock.
            skill_read = _last_tool_json(state["messages"], "output")
            assert skill_read and skill_read["output"] == {
                "width": 1536, "height": 2048, "ratio": "3:4", "images": 4}, skill_read
            # A four-image skill is not a single-image skill: calls 2-4 were not skipped.
            assert not any("[non-retryable]" in json.dumps(m, ensure_ascii=False) for m in state["messages"] if m.get("role") == "tool")

            # What reached the supplier: four submits, each with the one shared reference.
            for _model, body in mock_ws["submits"]:
                assert len(body.get("images") or []) == 1, body
            assert len({body.get("prompt") for _m, body in mock_ws["submits"]}) == 4

            shapes = await _canvas_images(state["chat"])
            generated = {sid for row in rows for sid in (row.get("shapes") or [])}
            assert len(generated) == 4, generated
            assert generated <= {s["id"] for s in shapes}, (generated, shapes)
            assert len([s for s in shapes if s["id"] in generated]) == 4, shapes
        finally:
            await browser.close()
