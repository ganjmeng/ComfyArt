"""#974 Full App legacy bypass regression, superseded by actual #911 stages.

The old scripted model tries four direct final calls with no answered cards.
Those attempts must now produce ZERO supplier submissions. Positive staged
mock relay coverage is in test_multi_angle_stages_911.py. This is NOT visual
or paid acceptance. Keep the old Full App harness to prevent regressions.
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
        state["finished"] = True
        return _reply("等待问询回答。" if lang == "zh" else "Waiting for stage answers.")

    return respond


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_fullapp_multi_angle_legacy_four_direct_calls_are_blocked(
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
            await _wait(lambda: state.get("finished"), timeout=150.0)
            assert mock_ws["submits"] == []
            gens = [(name, args) for name, args in state["mcp"] if name == "generate_image"]
            assert len(gens) == 4  # attempted legacy plan; none is authorized by stage state
            results = []
            for message in state["messages"]:
                if message.get("role") == "tool":
                    try:
                        results.append(json.loads(message.get("content") or "{}"))
                    except ValueError:
                        pass
            blocked = [r for r in results if isinstance(r, dict) and r.get("kind") == "multiAngleStage"]
            assert len(blocked) == 4 and all(r.get("submitted") is False for r in blocked)
            assert _all_ids(state["messages"]) == []
        finally:
            await browser.close()
