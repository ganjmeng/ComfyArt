"""#978 — the template the user picked must reach the agent with this run's values.

Chain under test (message-body delivery, chosen in the PR):
  skill dialog (`skillRunParams`) → `withPreset` marks the attachment (`activePreset`)
  → `sendToAgent` puts `{id, prompt}` (already interpolated) in the send body
  → `api/bot_send.compose_provider_text` writes it into the provider start text.

The JS half is the real `src/skills.ts` + `src/agent.ts` `sendToAgent` with only the bot boundary stubbed
(`tests/js/preset978/`); the Python half is the real compose/router. $0, no network, no paid call.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from conftest import wait_bot_done, write_settings

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)
PRIORITY = "where they conflict with the skill's base instructions, follow the template"


@lru_cache(maxsize=2)
def report(lang: str) -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"preset978-{lang}-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/preset978/rolldown.config.mjs"],
                   cwd=ROOT, check=True, capture_output=True,
                   env={**os.environ, "OUT": str(out), "PRESET_LANG": lang})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60,
                                     env={**os.environ, "PRESET_LANG": lang}).stdout)


def compose(**kw):
    from ComfyArt.api.bot_send import compose_provider_text
    return compose_provider_text(**kw)


def delivered_turn(case: dict) -> dict:
    """What the agent actually receives for one send case: body preset + real provider start text."""
    payload = case["payload"]
    assert "preset" in payload, case
    return {
        "payload": payload,
        "preset": payload["preset"],
        "context": compose(text=payload["text"], skill_name=payload["skill"], preset_prompt=payload["preset"]["prompt"]),
    }


CASES = {
    # case key: (template phrase zh, en, value that must appear)
    "brandFood": ("3 张标志方向提案", "3 logo direction boards", "Wildpeak Coffee"),
    "packagingMulti": ("共 4 张", "4 images total", "AURELIA 30ml serum"),
}


@pytest.mark.parametrize("lang", ["zh", "en"])
@needs_node
def test_two_template_skills_deliver_prompt_with_values(lang):
    r = report(lang)
    for key, (zh_word, en_word, value) in CASES.items():
        case = r[key]
        turn = delivered_turn(case)
        assert turn["payload"]["skill"] == case["skillName"]
        assert turn["preset"]["id"] == case["presetParam"] and case["presetParam"]
        prompt, context = turn["preset"]["prompt"], turn["context"]
        # the template body + this run's input value, in the body the agent reads
        assert (zh_word if lang == "zh" else en_word) in prompt
        assert value in prompt
        # no raw placeholder, no undefined, no double space
        assert "{{" not in prompt and "undefined" not in prompt and "  " not in prompt
        # the provider start text carries it once, before the user text, with template priority stated
        assert prompt in context
        assert PRIORITY in context
        assert context.index("then follow those instructions.") < context.index("Selected template instructions")
        assert context.index("Selected template instructions") < context.index(case["ask"])
        assert context.count(prompt) == 1
        assert "{{" not in context


SUPPORTED_VARS = {"brand_info", "brief", "character_info", "motion_brief", "product_info", "visual_direction"}
PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")


@needs_node
def test_every_builtin_preset_is_delivered_and_every_variable_is_defined():
    r = report("en")
    rows = r["allPresets"]
    assert len(rows) >= 100  # every preset of every skill with presets, not the 2 skills asserted above
    assert r["unresolved"] == []  # every {{x}} belongs to that template's own text inputs
    seen: set[str] = set()
    for row in rows:
        assert row["delivered"] is True, row
        assert row["prompt"] is not None and "{{" not in row["prompt"] and "undefined" not in row["prompt"], row
        seen.update(PLACEHOLDER.findall(row["raw"] or ""))
    # the supported variable list is exactly the template input keys used by OUR copy (5 long prompts)
    assert seen == SUPPORTED_VARS


@needs_node
def test_short_style_preset_is_delivered_verbatim():
    r = report("en")
    case = r["clothingFormal"]
    turn = delivered_turn(case)
    assert turn["preset"]["id"] == "formal"
    assert turn["preset"]["prompt"] == r["presets"]["clothingPrompt"] == r["presets"]["clothingPrompt"].strip()
    assert "Style: AI clothing swap formal look" in turn["context"]


@needs_node
@pytest.mark.parametrize("key", ["brandUnknown", "brandNoPreset", "posterNoPresets"])
def test_no_template_send_is_unchanged(key):
    r = report("en")
    case = r[key]
    assert case["activePreset"] is None and case["presetParam"] is None
    # no preset selected / unknown preset / skill without presets: byte-identical behavior, no payload key
    assert "preset" not in case["payload"]
    assert set(case["payload"]) == {"text", "refs", "docs", "kits", "skill", "memory"}
    assert case["instructionsUnchanged"] is True
    ctx = compose(text=case["payload"]["text"], skill_name=case["payload"]["skill"])
    assert ctx == compose(text=case["payload"]["text"], skill_name=case["payload"]["skill"], preset_prompt="")
    assert "Selected template instructions" not in ctx and "{{" not in ctx


@needs_node
def test_interpolation_replaces_variables_and_drops_missing_ones():
    unit = report("en")["interpolate"]
    assert unit["both"] == "Logo for Wildpeak — warm. End."
    assert unit["missing"] == "Logo for Wildpeak —. End."      # missing {{visual_direction}} + unknown are gone
    assert unit["blank"] == "A B two C"                        # blank value is dropped, never left as {{a}}
    assert unit["none"] == "No variables here."
    for value in unit.values():
        if isinstance(value, str):
            assert "{{" not in value and "}}" not in value and "undefined" not in value
    # multiline textarea value survives (label: value … next label)
    assert unit["values"] == {"brand_info": "line one\nline two", "visual_direction": "warm light"}


def test_compose_adds_template_block_only_when_given():
    text, name = "make it", "Logo System"
    base = compose(text=text, skill_name=name)
    with_template = compose(text=text, skill_name=name, preset_prompt="TEMPLATE BODY {{x}}")
    assert with_template != base
    assert "TEMPLATE BODY" in with_template and PRIORITY in with_template
    # #978 does not touch the rest of the turn: skill read line, user text, no-template path
    assert "action='read'" in with_template and with_template.endswith("\n\n" + text)
    assert base.endswith("\n\n" + text)
    assert "Selected template instructions" not in base


def test_parse_preset_rejects_malformed_and_caps_length():
    from ComfyArt.api.bot_send import PRESET_PROMPT_MAX, parse_preset
    assert parse_preset({"id": "t1", "prompt": "  hi  "}) == "hi"
    assert parse_preset({"id": "t1", "prompt": None}) == ""
    assert parse_preset("prompt") == "" and parse_preset(None) == ""
    assert parse_preset({"prompt": "x" * (PRESET_PROMPT_MAX + 100)}) == "x" * PRESET_PROMPT_MAX


async def test_router_puts_the_template_into_the_agents_start_text(bot_client, fake_provider):
    write_settings(**{"enable-mcp": True, "enable-bot": True})
    r = report("en")
    case = r["brandFood"]
    payload = case["payload"]
    chat = (await (await bot_client.post("/comfyart/bot/chats", json={"project": "p978", "provider": "fake-test"})).json())["chat"]
    resp = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                                 json={"text": payload["text"], "skill": payload["skill"], "preset": payload["preset"]})
    assert resp.status == 200
    data = await wait_bot_done(bot_client, chat["id"])
    user_text = fake_provider.last_turn.user_text
    assert payload["preset"]["prompt"] in user_text and "Wildpeak Coffee" in user_text
    assert "Selected template instructions" in user_text and "{{" not in user_text
    # UI unchanged: the bubble still shows only the skill chip + the user's text (template is not a new block)
    assert [b["type"] for b in data["messages"][0]["blocks"]] == ["skill", "text"]
    # same chat, no preset: the start text is the pre-#978 one (no template block)
    resp = await bot_client.post(f"/comfyart/bot/chats/{chat['id']}/send",
                                 json={"text": "make it", "skill": payload["skill"]})
    assert resp.status == 200
    await wait_bot_done(bot_client, chat["id"])
    assert "Selected template instructions" not in fake_provider.last_turn.user_text
