"""#494-2: each skill's own input dialog + presets, through the real src/skills.ts (tests/js/skill_dialog_494.ts),
plus wiring greps for the Skills page / dialog / handoff. Harness needs node + npm install; $0, no network."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "src/home/Skills.tsx").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
EDIT = (ROOT / "src/ui/SkillsDialog.tsx").read_text()
HANDOFF = (ROOT / "src/home/handoff.ts").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m4942") / "skill_dialog_494.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_dialog_494.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_every_field_is_bilingual_data(got):
    assert len(got["fields"]) == 11
    for sid, fields in got["fields"].items():
        assert fields, sid
        assert any(req for _, _, req, *_ in fields), sid
        for key, typ, req, zh, en, ph in fields:
            assert typ in {"text", "textarea", "select", "image"} and zh and en, (sid, key)
            if req and typ in {"text", "textarea"}:
                assert ph, (sid, key)
    keys = {sid: [f[0] for f in fs] for sid, fs in got["fields"].items()}
    assert keys["poster"] != keys["custom-workflow"]  # each skill its own dialog


@needs_node
def test_presets_have_prompts(got):
    for sid, ps in got["presets"].items():
        assert len(ps) == (0 if sid == "custom-workflow" else 3), sid
        assert all(en and prompt for _, en, prompt in ps), sid


@needs_node
def test_defaults_and_required(got):
    assert got["posterDefaults"]["ratio"] == "3:4" and got["posterDefaults"]["topic"] == ""
    assert got["cwDefaults"] == {"brief": ""}
    assert got["posterMissing"] == ["topic"] and got["posterFilled"] == []
    assert got["cwMissing"] == ["brief"]  # whitespace is empty
    assert got["dialog"] == [True, True, False]  # old personal skill: no dialog, main's direct start


@needs_node
def test_preset_prompt_appended_after_instructions(got):
    assert got["withPreset"] == got["posterInstr"].rstrip() + "\n\n" + got["secondPrompt"]
    assert got["withUnknown"] and got["withNull"]
    assert got["presetDefault"] != got["presetPick"]
    assert got["presetImg"] == "/comfyart/skills/poster/cover.webp"  # no preset image yet → cover


@needs_node
def test_run_params(got):
    p = got["posterRun"]
    assert p["skill"] == "poster" and p["mode"] == "agent" and p["ref"] == ["/view?f=a.png"]
    assert p["preset"] and p["preset"] != got["presetDefault"]
    assert p["ask"].splitlines()[0].endswith(": Autumn launch") and "3:4" in p["ask"]
    assert got["cwRun"] == {"skill": "custom-workflow", "mode": "agent", "ask": got["cwRun"]["ask"]}
    assert got["cwRun"]["ask"].endswith(": Upscale my photo")
    assert got["emptyRun"]["ask"] == "Old" and "preset" not in got["emptyRun"]


def test_handoff_applies_preset():
    assert "'preset'" in HANDOFF and "withPreset(found, presetId)" in HANDOFF


def test_dialog_is_data_driven():
    assert "skill.inputs" in DLG and "skill.presets" in DLG and "<Modal" in DLG
    for bad in ("'poster'", "'product'", "topic", "headline"):
        assert bad not in DLG, bad
    assert "missing.length > 0" in DLG and "skillRunParams(skill, values, preset)" in DLG


def test_page_wiring():
    assert "hasSkillDialog(s) ? tryCard(s) : newProject({ skill: s.id })" in PAGE
    assert "openSkillDetail(landing.id, true)" in PAGE
    assert "<SkillFileBox instructions={skill.instructions}" in PAGE and "onInstructions" not in PAGE.split("function SkillDetail")[1].split("export function Skills")[0]
    for tid in ("skill-detail-back", "skill-detail-try", "skill-detail-edit-chat", "skill-detail-more", "skill-detail-form-edit",
                "skill-detail-preset", "skill-guide-skip", "skill-guide-next", "skill-detail-author"):
        assert tid in PAGE, tid
    assert "{skill.custom && (" in PAGE  # chat edit / ⋯ only for the user's own skills
    for bad in ("views", "likes", "Icons.eye", "Icons.heart"):
        assert bad not in PAGE, bad
    # one file card, reused (no second SKILL.md box)
    assert EDIT.count('className="ca-skillform__box"') == 1 and "export function SkillFileBox" in EDIT
    assert "<SkillFileBox instructions={draft.instructions}" in EDIT


def test_copy_and_guide_style():
    assert ZH["skillDetail.try"] == "试用该技能" and ZH["skillDetail.guide"] == "Skill 创建成功，先试试效果吧"
    assert EN["skillDetail.guide"] == "Skill created. Give it a try"
    assert (ZH["skillDetail.guideSkip"], ZH["skillDetail.guideNext"]) == ("跳过", "下一步")
    for k in ZH:
        if k.startswith(("skillDetail.", "skillRun.")):
            assert k in EN, k
    guide = CSS.split(".ca-skillguide {")[1].split("}")[0]
    assert "#1f1f1f" in guide and "1px solid rgba(255, 255, 255, .1)" in guide
    arrow = CSS.split(".ca-skillguide::before {")[1].split("}")[0]
    assert "rgba(255, 255, 255, .1)" in arrow
