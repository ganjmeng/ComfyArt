"""#491 新建技能流程：技能页「创建」(B) 与首页 + → 技能 → 创建技能 (A) 都落在只有对话的全屏布局。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = (ROOT / "src/home/handoff.ts").read_text()
HOME = (ROOT / "src/home/Home.tsx").read_text()
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
SKILLS_PAGE = (ROOT / "src/home/Skills.tsx").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()


def _create_branch() -> str:
    m = re.search(r"if \(createSkill\) \{(.*?)\n  \}\n", HANDOFF, re.S)
    assert m, "createSkill branch missing in handoff.ts"
    return m.group(1)


def _entry_b() -> str:
    body = _create_branch()
    return body.split("if (text) {", 1)[1].split("\n    }\n", 1)[1]


def _home_create_click() -> str:
    m = re.search(r'data-testid="home-create-skill" onClick=\{\(\) => \{(.*?)\}\}>', HOME, re.S)
    assert m, "home-create-skill item missing"
    return m.group(1)


def test_b_sets_chat_view_max() -> None:
    assert "import { chatViewAtom } from '../ui/AgentPanel'" in HANDOFF
    assert "chatViewAtom.set('max')" in _create_branch()


def test_b_presets_chip_and_focuses() -> None:
    b = _entry_b()
    assert "skillCreatorAtom.set({ on: true, chip: CREATE_ENTRY_CHIP_KEY })" in b
    assert "focusComposer()" in b
    assert ".ca-composer__input')?.focus()" in HANDOFF


def test_b_does_not_send() -> None:
    b = _entry_b()
    assert "sendToAgent" not in b and "generateDirect" not in b
    assert b.strip().endswith("return")


def test_b_entry_still_hands_off_create_skill() -> None:
    assert "newProject({ createSkill: '1' })" in SKILLS_PAGE
    assert 'data-testid="skills-create"' in SKILLS_PAGE


def test_both_entries_share_chip_key() -> None:
    assert "export const HOME_CREATOR_CHIP_KEY = 'composer.skillCreator'" in SKILLS_TS
    assert "export const CREATE_ENTRY_CHIP_KEY = HOME_CREATOR_CHIP_KEY" in SKILLS_TS
    assert '"composer.skillCreator": "技能创建器"' in ZH
    assert '"composer.skillCreator": "Skill Creator"' in EN
    assert "t(skillCreator.chip ?? 'composer.skillCreator')" in COMPOSER


def test_a_home_menu_path() -> None:
    for tid in ("home-plus", "home-plus-skills", "home-skills-more", "home-create-skill"):
        assert f'data-testid="{tid}"' in HOME
    for key in ("home.createSkill", "home.createSkillFromChat", "home.importSkill", "home.skillsMenu"):
        assert key in HOME and f'"{key}"' in EN and f'"{key}"' in ZH
    assert '"home.createSkill": "创建技能"' in ZH
    assert '"home.createSkillFromChat": "从对话创建"' in ZH
    assert '"home.importSkill": "导入技能"' in ZH


def test_a_click_adds_chip_without_navigating() -> None:
    click = _home_create_click()
    assert "setCreator(true)" in click
    for bad in ("newProject", "startProject", "location", "send(", "openView"):
        assert bad not in click, bad
    assert 'data-testid="home-skill-creator-chip"' in HOME
    assert "t(HOME_CREATOR_CHIP_KEY)" in HOME
    assert '"composer.skillCreator": "技能创建器"' in ZH


def test_a_send_opens_project_with_create_skill_and_text() -> None:
    assert "if (creator) await startProject({ createSkill: '1', ask: text.trim(), ref: refs })" in HOME


def test_a_send_lands_full_screen_with_prefill_once() -> None:
    body = _create_branch()
    a = body.split("if (text) {", 1)[1].split("\n    }\n", 1)[0]
    assert "skillCreatorAtom.set({ on: false })" in a
    assert a.count("sendToAgent(") == 1
    assert "t('composer.skillCreatorPrefill', text)" in a
    # max is set before the A/B split, so A also lands in chat-only full screen
    assert body.index("chatViewAtom.set('max')") < body.index("if (text) {")


def test_in_canvas_entry_unchanged() -> None:
    assert ("data-testid=\"skill-creator-start\" onClick={() => { setMenu(null); "
            "skillCreatorAtom.set({ on: true }); agentModeAtom.set('agent') }}") in COMPOSER
    assert "chatViewAtom" not in COMPOSER



ICONS = (ROOT / "src/ui/icons.tsx").read_text()


def _home_skill_row_click() -> str:
    m = re.search(r'data-testid="home-skill-row" onClick=\{\(\) => \{(.*?)\}\}>', HOME, re.S)
    assert m, "home-skill-row missing"
    return m.group(1)


def test_a_skill_click_adds_chip_without_navigating() -> None:
    click = _home_skill_row_click()
    assert "setPlus(null)" in click and "setPicked(s)" in click
    for bad in ("newProject", "startProject", "location", "send(", "openView"):
        assert bad not in click, bad


def test_a_skill_send_opens_project_with_skill_and_text() -> None:
    assert "if (picked) await startProject({ skill: picked.id, ask: text.trim(), mode, ref: refs })" in HOME


def test_a_skill_chip_reuses_484_chip() -> None:
    chip = (ROOT / "src/ui/SkillChip.tsx").read_text()
    shell = (ROOT / "src/styles/shell.css").read_text()
    assert '<SkillChip name={picked.name} testId="home-skill-chip"' in HOME
    assert '<SkillChip key={b.name} name={b.name ?? ""} testId="user-skill-chip" />' in (ROOT / "src/ui/ChatMessage.tsx").read_text()
    assert 'className="ca-chip ca-chip--skill"' in chip and "title={name}" in chip
    assert '<span className="ca-chip__name">{name}</span>' in chip
    assert ".ca-chip--skill { max-width: 160px;" in shell
    assert re.search(r"\.ca-chip__name \{[^}]*text-overflow: ellipsis", shell)
    assert "ca-chip--skill" not in (ROOT / "src/styles/home.css").read_text()


def test_a_skills_panel_icon_is_square_plus() -> None:
    m = re.search(r'data-testid="home-skills-more".*?<span className="ca-icon">\{Icons\.(\w+)\}</span>', HOME, re.S)
    assert m and m.group(1) == "squarePlus"
    assert 'squarePlus: <Svg><rect width="18" height="18" x="3" y="3" rx="2" />' in ICONS


def test_a_import_opens_new_dialog() -> None:
    m = re.search(r'data-testid="home-import-skill" onClick=\{\(\) => \{(.*?)\}\}>', HOME, re.S)
    assert m and "setImporting(true)" in m.group(1)
    assert "skillsOpenAtom" not in HOME
    assert "<SkillImportDialog" in HOME


def test_canvas_plus_entry_chip_uses_same_key() -> None:
    """EL review #502：画布对话框 + 菜单入口不传 chip，回落值必须是同一个 key，中文显示「技能创建器」。"""
    import json
    m = re.search(r"t\(skillCreator\.chip \?\? '([\w.]+)'\)", COMPOSER)
    assert m, "chip fallback missing in Composer.tsx"
    key = m.group(1)
    assert key == "composer.skillCreator"
    assert json.loads(ZH)[key] == "技能创建器"
    assert json.loads(EN)[key] == "Skill Creator"
    # 画布 + 菜单入口本身不带 chip，走的就是这个回落值
    assert "skillCreatorAtom.set({ on: true })" in COMPOSER
    assert "skillCreatorChip" not in COMPOSER
