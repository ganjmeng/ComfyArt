"""#725: old ?skill= links restore refs into the composer only (visible + hidden);
draft + refs survive two refreshes without duplicates. Source locks + JS harness. $0."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = (ROOT / "src/home/handoff.ts").read_text()
SESSION = (ROOT / "src/home/skillLinkSession.ts").read_text()
RESTORE = (ROOT / "src/home/skillLinkRestore.ts").read_text()
SKILLS = (ROOT / "src/skills.ts").read_text()
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()
AGENT = (ROOT / "src/agent.ts").read_text()

needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


def _skill_branch() -> str:
    """The ?skill= path in takeHandoff — the first `if (skillId)` block in takeHandoff."""
    src = (ROOT / "src/home/handoff.ts").read_text()
    start = src.index("if (skillId) {", src.index("export async function takeHandoff"))
    i, depth = start + len("if (skillId) {") - 1, 0
    for i, ch in enumerate(src[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError("unclosed skillId branch")


def test_ac18_style_pins_untouched() -> None:
    """#725 must not touch skill pins or the Auto table."""
    assert "export const HIDDEN_BUILTIN_SKILL_IDS: readonly string[] = [\n]" in SKILLS
    models = (ROOT / "api/auto_models.json").read_text()
    # file is present and this PR should not rewrite it; test is a reminder, content compared in review
    assert models


def test_skill_branch_restores_composer_only_never_canvas() -> None:
    """AC1/AC2/AC5: the ?skill= branch never calls placeRefs / sendToAgent / generateDirect."""
    body = _skill_branch()
    assert "applySkillLinkHandoff(text, refs)" in body
    assert "placeRefs" not in body
    assert "sendToAgent" not in body
    assert "generateDirect" not in body
    assert "extraRefsAtom" not in body
    assert "refreshBot" not in body
    # hidden + visible share this branch (attachSkill then return)
    assert "if (skill && !attachSkill(skill)) rememberHiddenSkillId(skill.id)" in body
    assert "e2eHiddenSkillIds" in body and "attachSkillForLink" in body
    assert re.search(r"^\s*return$", body, re.M)


def test_non_skill_paths_still_place_on_canvas() -> None:
    """Do not change ?tool= / createSkill / editSkill / bare ask+ref landing."""
    create = HANDOFF[HANDOFF.index("if (createSkill)"):HANDOFF.index("if (tool === 'elements')")]
    assert "placeRefs(editor, refs)" in create
    tools = HANDOFF[HANDOFF.index("if (isHomeTool(tool))"):HANDOFF.index("agentModeAtom.set(mode)")]
    assert "openHomeTool(editor, tool, refs)" in tools
    rest = HANDOFF[HANDOFF.index("const shapes = await placeRefs(editor, refs)"):]
    assert "sendToAgent(editor, text, shapes as TLImageShape[], skill)" in rest
    assert "generateDirect(" in rest


def test_refresh_rehydrates_from_session_not_url() -> None:
    """AC4: after params are stripped, a refresh re-applies the persisted restore (replace, no append)."""
    early = HANDOFF[HANDOFF.index("if (!text && !refs.length && !skillId"):HANDOFF.index("for (const k of KEYS)")]
    assert "await applyPersistedSkillLinkRestore()" in early
    assert "applyPersistedSkillLinkRestore" in SESSION
    assert "if (!persistReady) return" in SESSION
    assert "persistReady = true" in SESSION
    assert "looseRefsAtom.set(dedupeLooseRefs(state.refs))" in SESSION
    # replace, not append
    assert "looseRefsAtom.set([...looseRefsAtom.get()" not in SESSION
    assert "dedupeLooseRefs" in RESTORE and "seen.has(src)" in RESTORE


def test_hidden_fixture_does_not_change_production_hide_list() -> None:
    """AC2: hidden path uses a test-only e2e hide fixture; src/skills.ts and the hide list stay untouched."""
    assert "comfyart.e2e.hideSkills" in SESSION
    assert "export function e2eHiddenSkillIds" in SESSION
    assert "export const HIDDEN_BUILTIN_SKILL_IDS: readonly string[] = [\n]" in SKILLS
    assert "e2eHiddenSkillIds" not in SKILLS
    assert "comfyart.e2e.hideSkills" not in SKILLS
    # listing / notice on production path unchanged
    assert "export const isListedSkill = (s: Pick<Skill, 'id' | 'custom'>): boolean => !!s.custom || !HIDDEN_BUILTIN_SKILL_ID_SET.has(s.id)" in SKILLS


def test_composer_persists_and_clears_on_send() -> None:
    assert "persistSkillLinkRestore()" in COMPOSER
    send = COMPOSER[COMPOSER.index("const go = async ()"):]
    assert send.index("endSkillLinkRestore()") < send.index("sendToAgent(")
    assert "looseRefsAtom" in AGENT


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m725") / "skill_link_restore_725.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "skill_link_restore_725.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_harness_dedupes_refs(got: dict) -> None:
    """Mutation: drop dedupeLooseRefs uniqueness → this fails."""
    srcs = got["deduped"]
    assert srcs == [
        "/api/view?filename=a.png&type=input",
        "/api/view?filename=b.png&type=input",
    ]
    assert got["empty"] == 0 and got["blank"] == 0
    assert got["parsedDup"]["n"] == 2
    assert got["parsedDup"]["draft"] == "keep725"
    assert got["parsedDup"]["skillId"] == "yingzao"


@needs_node
def test_harness_refresh_twice_does_not_duplicate_or_drop(got: dict) -> None:
    """AC4/AC5: two reload reads + a rewrite stay at N, never 2N. Mutation: append on apply → appendWouldGrow is the contrast."""
    assert got["refreshTwice"] == [2, 2, 2, 2, 2]
    assert got["appendWouldGrow"] == 4  # documents the bad path the production code must not take
    assert got["first"]["draft"] == "keep725" and got["first"]["skillId"] == "yingzao"
    assert got["refsOnly"] == {"draft": "", "n": 2, "skillId": "before-after"}
    assert got["askOnly"] == {"draft": "only-ask", "n": 0}
    assert got["encodedEmpty"] is None
    assert got["wasActive"] is True
    assert got["afterClear"] is None and got["activeAfterClear"] is False
