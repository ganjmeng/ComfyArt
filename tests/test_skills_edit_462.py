"""#462 G3 Edit Skill: description, Preview/Code tabs, Edit in Chat (all prior features kept)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIALOG = (ROOT / "src/ui/SkillsDialog.tsx").read_text()
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()
BOT = (ROOT / "src/botLayout.ts").read_text()
TOOLS = (ROOT / "api/mcp_tools/canvas.py").read_text()
SKILLS = (ROOT / "src/skills.ts").read_text()
EN = json.loads((ROOT / "src/locales/en.json").read_text())
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
KEYS = ["skillsDialog.name", "skillsDialog.description", "skillsDialog.instructions", "skillsDialog.preview",
        "skillsDialog.code", "skillsDialog.editInChat", "skillEdit.projectTitle", "skillEdit.ask"]


def test_description_field_and_listing_fallback() -> None:
    # behavior of the round trip lives in test_skill_desc_462.py (real saveSkill → loadSkills)
    assert "description?: string" in SKILLS_TS
    assert "if (skill.description?.trim()) return skill.description.trim()" in SKILLS_TS


def test_main_attachment_sections_kept_and_footer_outside_scroll() -> None:
    assert "t('skillsDialog.attachedFiles')" in DIALOG and "t('common.image')" in DIALOG
    assert 'className="ca-lib__new" onClick={() => file.current?.click()}' in DIALOG
    scroll = DIALOG.index('data-testid="skill-form-scroll"')
    foot = DIALOG.index('ca-skillform__foot')
    assert DIALOG.rindex("</div>", scroll, foot) > DIALOG.index("skillsDialog.addImage", scroll)


def test_form_order_and_tabs() -> None:
    i = [DIALOG.index(k) for k in ("skillsDialog.name'", "skillsDialog.description'", "skillsDialog.instructions'")]
    assert i == sorted(i)
    for tid in ("skill-description", "skill-instructions", "skill-tabs", "skill-edit-in-chat"):
        assert f'data-testid="{tid}"' in DIALOG
    assert "<Markdown text={body} />" in DIALOG
    assert "Icons.code" in DIALOG and "Icons.eyeView" in DIALOG


def test_kept_features() -> None:
    for k in ("skillsDialog.addFile", "skillsDialog.addImage", "uploadSkillImage", "versionHistory", "importFolder", "rollBack"):
        assert k in DIALOG


def test_edit_in_chat_opens_new_project_and_leaves_composer_plain() -> None:
    # behavior lives in test_skill_edit_chat_462.py; here: wiring + no leftover edit-mode composer
    assert "editSkillInChat(view.skill)" in DIALOG
    for gone in ("skillCreator.edit", "skillEditPrefill", "skillEditHint", "skillEditChip"):
        assert gone not in COMPOSER and gone not in EN and gone not in ZH


def test_agent_skill_tool_left_as_on_main() -> None:
    # #462 does not touch the agent skill tool (#463 owns it); an agent save keeps the stored description via ...existing.
    # #463 (PR #487: 4b33ed5 moved the tool body to skills.ts skillTool; 99f2d9f added an optional `description`
    # arg). Intent kept: a save that leaves description out keeps the stored one, via the existing object.
    assert "args.description" not in BOT  # botLayout only wires the tool
    assert "skill: async (_editor, args) => skillTool(args)" in BOT
    tool = SKILLS[SKILLS.index("export async function skillTool"):]
    tool = tool[:tool.index("\n}\n")]
    assert "const description = args.description != null ? String(args.description).replace(/\\s+/g, ' ').trim() : existing?.description" in tool
    assert "const skill: Skill = { ...existing, id: existing?.id ?? await freeSkillId(slug(name))" in tool
    assert "if (description) skill.description = description; else delete skill.description" in tool
    assert "await saveSkill(skill)" in tool
    schema = TOOLS[TOOLS.index('"skill": _tool('):TOOLS.index('"custom_workflow"')]
    assert '"description": {"type": "string"}' in schema  # optional (#463), never required
    assert '["action"]),' in schema
    assert "instructions and description you leave out are kept" in schema


def test_locales() -> None:
    for k in KEYS:
        assert k in EN and k in ZH


def test_no_brand() -> None:
    for text in (DIALOG, SKILLS_TS, COMPOSER):
        assert "lovart" not in text.lower()


def test_open_editor_by_id_and_home_mount() -> None:
    assert "export function openSkillEditor(id: string)" in DIALOG
    assert "skillEditIdAtom" in DIALOG
    home = (ROOT / "src/home/HomeApp.tsx").read_text()
    assert "<SkillsDialog home" in home
    handoff = (ROOT / "src/home/handoff.ts").read_text()
    assert "EDIT_SKILL_PARAM" in handoff and "startSkillEdit(editor, skill" in handoff


def test_screenshots_not_in_code_branch() -> None:
    assert not list((ROOT / "docs/design/462").glob("**/*.png"))
