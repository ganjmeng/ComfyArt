"""#491 新建技能流程：技能页「创建」(B) 与首页 + → 技能 → 创建技能 (A) 都落在只有对话的全屏布局。"""
from __future__ import annotations

import json
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
    assert 'testId="home-skill-creator-chip"' in HOME  # #502 D3: rendered via SkillChip
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
    assert "import { SkillImportDialog } from '../ui/SkillImportDialog'" in HOME


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


# ---- #502 review round: design D1–D3, product D4, QA Q1/Q2 ----
CHIP = (ROOT / "src/ui/SkillChip.tsx").read_text()


def _skills_panel() -> str:
    m = re.search(r'data-testid="home-skills-menu">(.*?)\{skills\.map', HOME, re.S)
    assert m, "skills panel missing"
    return m.group(1)


def test_d1_dropdown_anchors_on_square_plus_and_panel_stays_open() -> None:
    head = _skills_panel()
    # the dropdown is its own Popover inside the panel head, triggered by home-skills-more
    assert "<Popover" in head and 'data-testid="home-skills-more"' in head
    assert 'data-testid="home-skills-more-menu"' in head
    assert 'align="end"' in head
    # the panel is not swapped out: no 'skillsMore' state of the outer popover
    assert "setPlus('skillsMore')" not in HOME and "plus === 'skillsMore'" not in HOME
    assert "useState<null | 'plus' | 'skills'>(null)" in HOME


def test_d2_dropdown_icons() -> None:
    menu = HOME.split('data-testid="home-skills-more-menu"', 1)[1].split("</Popover>", 1)[0]
    icons = re.findall(r"\{Icons\.(\w+)\}</span><span className=\"ca-menu__grow\">\{t\('home\.(\w+)'\)\}", menu)
    assert icons == [("circlePlus", "createSkill"), ("messageSquare", "createSkillFromChat"), ("uploadArrow", "importSkill")]
    assert re.search(r'<button type="button" className="ca-menu__item" disabled>\s*<span className="ca-icon">\{Icons\.messageSquare\}', menu)
    assert 'circlePlus: <Svg strokeWidth={2}><circle cx="12" cy="12" r="10" />' in ICONS
    assert "messageSquare: <Svg strokeWidth={2}>" in ICONS


def test_d3_creator_chip_is_skill_chip_everywhere() -> None:
    assert '<SkillChip name={t(HOME_CREATOR_CHIP_KEY)} testId="home-skill-creator-chip" />' in HOME
    assert "<SkillChip name={t(skillCreator.chip ?? 'composer.skillCreator')} testId=\"skill-creator-chip\" />" in COMPOSER
    for src in (HOME, COMPOSER):
        assert "ca-chip--creator" not in src
        assert "Icons.sparkles}</span>{t(" not in src
    assert "{Icons.scrollText}" in CHIP


def test_d4_chips_have_no_remove_button() -> None:
    assert "Icons.close" not in CHIP and "<button" not in CHIP and "onRemove" not in CHIP
    assert "onRemove" not in HOME.split("<textarea", 1)[0].split("ca-landing__refs", 1)[1].split("refs.map", 1)[0]
    assert '<SkillChip name={skill.name} testId="composer-skill-chip" />' in COMPOSER
    assert "onClick={() => skillAtom.set(null)}" not in COMPOSER


def test_d4_backspace_rule() -> None:
    assert "el.value === '' || (el.selectionStart === 0 && el.selectionEnd === 0)" in CHIP
    assert "if ((picked || creator) && chipBackspace(e)) { e.preventDefault(); setPicked(null); setCreator(false); return }" in HOME
    assert "if ((skillCreator.on || skill) && chipBackspace(e)) {" in COMPOSER


def test_q1_skill_row_click_opens_no_dialog() -> None:
    click = _home_skill_row_click()
    assert "setPicked(s)" in click
    for bad in ("setImporting", "openSkillEditor", "skillsOpenAtom", "Modal", "Dialog", "setMore(true)", "setPlus('"):
        assert bad not in click, bad


def test_q2_import_dialog_module() -> None:
    assert "import { SkillImportDialog } from '../ui/SkillImportDialog'" in HOME


# ---- #502 review round 2: design HOLD (panel head / one-line rows / A3 bubble) + product title ruling ----
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
AGENT = (ROOT / "src/agent.ts").read_text()
BOT_TS = (ROOT / "src/bot.ts").read_text()
BOT_PY = (ROOT / "api/bot.py").read_text()
BUBBLE = (ROOT / "src/ui/ChatMessage.tsx").read_text()


def _home_skill_row() -> str:
    m = re.search(r'\{skills\.map\(\(s\) => \((.*?)\)\)\}', HOME, re.S)
    assert m, "skill rows missing"
    return m.group(1)


def test_r2_row_title_is_full_name() -> None:
    row = _home_skill_row()
    assert 'title={s.name} data-testid="home-skill-row"' in row
    assert "title={s.instructions}" not in row
    assert '<span className="ca-menu__grow ca-skills__name">{s.name}</span>' in row


def test_r2_rows_single_line_ellipsis() -> None:
    m = re.search(r"\.ca-skills \.ca-skills__name \{([^}]*)\}", HOME_CSS)
    assert m, "row name rule missing"
    for decl in ("white-space: nowrap", "overflow: hidden", "text-overflow: ellipsis", "min-width: 0"):
        assert decl in m.group(1), decl
    assert re.search(r"\.ca-skills \.ca-menu__item \{[^}]*min-width: 0", HOME_CSS)


def test_r2_head_square_plus_top_right() -> None:
    # the panel is portaled to <body>: the head rule must not hang off .ca-landing__box (it never matched)
    assert ".ca-landing__box .ca-menu__head" not in HOME_CSS
    m = re.search(r"\.ca-skills \.ca-menu__head \{([^}]*)\}", HOME_CSS)
    assert m and "display: flex" in m.group(1) and "justify-content: space-between" in m.group(1)
    assert "padding: 4px 4px 4px 10px" in m.group(1)  # same left padding as rows (.ca-menu__item 0 10px)
    assert re.search(r"\.ca-skills \.ca-menu__head > \.ca-pop-anchor \{[^}]*margin-left: auto", HOME_CSS)
    head = _skills_panel()
    # title first, icon last
    assert head.index("home.skillsMenu") < head.index('data-testid="home-skills-more"')


def test_r2_dropdown_right_aligned_and_clamped_to_panel() -> None:
    head = _skills_panel()
    assert 'align="end"' in head and 'within=".ca-skills"' in head
    assert 'className="ca-menu ca-skills" data-testid="home-skills-menu"' in HOME


def test_r2_a3_home_send_shows_chip_and_own_text_only() -> None:
    body = _create_branch()
    a = body.split("if (text) {", 1)[1].split("\n    }\n", 1)[0]
    # bubble text = user's words; instruction = hidden context; chip = 技能创建器
    assert ("sendToAgent(editor, text, shapes, null, [], [], t('composer.skillCreatorPrefill', text), "
            "{ chip: t(CREATE_ENTRY_CHIP_KEY) })") in a
    assert "sendToAgent(editor, t('composer.skillCreatorPrefill'" not in HANDOFF


def test_r2_a3_composer_send_shows_chip_and_own_text_only() -> None:
    assert "agentText" not in COMPOSER
    assert "const creatorContext = creating && text ? t('composer.skillCreatorPrefill', text) : ''" in COMPOSER
    assert "await sendToAgent(editor, text, keptRefs," in COMPOSER
    assert "creatorChip ? { chip: creatorChip } : undefined" in COMPOSER


def test_r2_a3_chip_is_display_only_server_side() -> None:
    assert "chip?: string" in BOT_TS
    assert "...(opts?.chip ? { chip: opts.chip } : {})" in AGENT
    seg = BOT_PY.split('chip_name = str(body.get("chip") or "")', 1)[1].split("provider_text = send_core.compose_provider_text(", 1)
    assert 'display_blocks.append({"type": "skill", "name": chip_name})' in seg[0]
    # provider text gets the user text + context (instruction), never the chip as a skill to read
    assert "chip_name" not in seg[1].split("lang = ", 1)[0]
    # stored display blocks are what history renders after reload: chip + text, no instruction
    assert "display_blocks.append({\"type\": \"text\", \"text\": text})" in BOT_PY
    assert 'testId="user-skill-chip"' in BUBBLE


def test_r2_a3_provider_still_gets_instruction() -> None:
    m = re.search(r"^def compose_provider_text\(.*?(?=^def )", (ROOT / "api/bot_send.py").read_text(), re.M | re.S)
    ns: dict = {}
    exec(m.group(0), ns)  # noqa: S102
    instr = json.loads(ZH)["composer.skillCreatorPrefill"].replace("{0}", "做一个咖啡店早安海报技能")
    out = ns["compose_provider_text"]("做一个咖啡店早安海报技能", lines=[instr])
    assert 'action="save"' in out and "做一个咖啡店早安海报技能" in out
    assert "Use the ComfyArt skill" not in out


def test_r2_a3_bubble_text_is_exactly_user_text() -> None:
    """Product: bubble text (chip excluded) must equal the typed text exactly — no prefix/suffix, not even a space."""
    user = BUBBLE.split("export function UserMessage", 1)[1].split("\nexport function", 1)[0]
    assert "const text = textOf(m)" in user
    assert '<span className="ca-chat__text" data-testid="user-bubble-text">{text}</span>' in user
    # server stores the typed text verbatim as the only text block; the instruction stays in context
    seg = BOT_PY.split('chip_name = str(body.get("chip") or "")', 1)[1].split("context = str(body.get", 1)[0]
    assert re.findall(r'display_blocks\.append\(\{"type": "text", "text": [^}]*\}\)', seg) == ['display_blocks.append({"type": "text", "text": text})']
    # both client entries send exactly the typed text as `text`
    assert "sendToAgent(editor, text, shapes, null, [], [], t('composer.skillCreatorPrefill', text)," in HANDOFF
    assert "await sendToAgent(editor, text, keptRefs," in COMPOSER
