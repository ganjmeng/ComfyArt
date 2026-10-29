"""#367 Arti P0-1 entry shell — sidebar siblings + /arti home (mock)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_APP = (ROOT / "src/home/HomeApp.tsx").read_text()
ARTI = (ROOT / "src/home/Arti.tsx").read_text()
SCHEDULES = (ROOT / "src/home/Schedules.tsx").read_text()
MAIN = (ROOT / "src/main.tsx").read_text()
PROJECTS = (ROOT / "src/projects.ts").read_text()
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
APP = (ROOT / "src/App.tsx").read_text()
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()


def test_routes_schedules_and_arti() -> None:
    assert "HomeView" in PROJECTS
    assert "'schedules'" in PROJECTS and "'arti'" in PROJECTS
    assert "viewParam === 'schedules'" in MAIN
    assert "viewParam === 'arti'" in MAIN
    assert "view === 'schedules'" in HOME_APP
    assert "view === 'arti'" in HOME_APP
    assert "openView('schedules')" in HOME_APP
    assert "openView('arti')" in HOME_APP


def test_sidebar_two_siblings_with_beta() -> None:
    """Account-level peers beside home/projects — not under canvas Agent."""
    assert 'testId="rail-schedules"' in HOME_APP
    assert 'testId="rail-arti"' in HOME_APP
    assert 'data-testid="rail-arti-beta"' in HOME_APP
    assert "home.designSchedules" in HOME_APP
    assert "home.arti" in HOME_APP
    assert "home.artiBeta" in HOME_APP
    assert "account-rail" in HOME_APP
    assert "AgentPanel" not in HOME_APP
    assert "CanvasChat" not in HOME_APP


def test_arti_not_only_inside_canvas_agent() -> None:
    """Forbidden: Arti as canvas Agent chat alias / sole entry."""
    assert "openView('arti')" in HOME_APP
    assert "view === 'arti'" in HOME_APP
    assert "Arti" in HOME_APP
    for surface in (APP, COMPOSER):
        assert "openView('arti')" not in surface


def test_arti_avatar_box_matches_reference() -> None:
    """Level-card avatar: reference 75×89 mint box; sprite uses square contain, not 100% stretch."""
    block = HOME_CSS.split('.ca-arti__avatar {', 1)[1].split('.ca-arti__avatar .ca-icon', 1)[0]
    assert 'width: 75px; height: 89px;' in block
    assert 'border-radius: 8px;' in block
    assert '#D9F7EF' in block
    mascot = HOME_CSS.split('.ca-arti__avatar .arti-mascot--avatar {', 1)[1].split('}', 1)[0]
    assert 'width: 75px;' in mascot and 'height: 75px;' in mascot
    assert 'width: 100%' not in mascot and 'height: 100%' not in mascot


def test_arti_home_shell_three_sections() -> None:
    assert 'data-testid="arti-page"' in ARTI
    assert 'data-testid="arti-level-card"' in ARTI
    assert 'data-testid="arti-avatar"' in ARTI
    assert 'data-testid="arti-capabilities"' in ARTI
    assert 'data-testid="arti-learned"' in ARTI
    assert "arti.levelStatus" in ARTI
    assert "arti.level" in ARTI
    assert "arti.levelHint" in ARTI
    assert "arti.canDoTitle" in ARTI
    assert "arti.learnedTitle" in ARTI


def test_capabilities_five_cards_honest_grey() -> None:
    assert "arti-cap-${cap.id}" in ARTI
    for cap in ("review", "research", "memory", "skills", "feedback"):
        assert f"id: '{cap}'" in ARTI
    # disabled caps: honest 「即将开放」 caption (#381 product), never fake-enabled
    assert "arti-cap-${cap.id}-soon" in ARTI
    assert "arti.cap.soon" in ARTI
    assert "disabled: true" in ARTI  # review / research / feedback stay grey
    # #385: memory + skills are switchable (disabled: false) and write settings
    assert "id: 'memory'" in ARTI and "disabled: false" in ARTI
    assert "id: 'skills'" in ARTI
    assert "saveSettings" in ARTI
    assert "ARTI_CAP_SETTINGS" in ARTI
    # feedback has no switch (CN)
    assert "noSwitch" in ARTI
    # switches for grey caps are disabled (no fake interactivity)
    assert "disabled={cap.disabled}" in ARTI


def test_learned_tabs_shell() -> None:
    assert "arti-tab-${id}" in ARTI
    assert 'id="memory"' in ARTI or "id: 'memory'" in ARTI or 'id="memory"' in ARTI.replace("'", '"')
    assert 'TabBtn id="memory"' in ARTI
    assert 'TabBtn id="skills"' in ARTI
    assert 'TabBtn id="evolution"' in ARTI
    assert "arti.tabMemory" in ARTI
    assert "arti.tabSkills" in ARTI
    assert "arti.tabEvolution" in ARTI
    # memory = #368 memory center (was P0-2 placeholder)
    assert "ArtiMemory" in ARTI
    assert "arti-memory-placeholder" not in ARTI
    # skills skeleton / empty
    assert 'data-testid="arti-skills-skeleton"' in ARTI
    # #385: evolution log replaces the thin placeholder
    assert 'data-testid="arti-evolution-placeholder"' not in ARTI
    assert 'data-testid="arti-evolution-log"' in ARTI or 'arti-evolution-log' in ARTI
    assert 'data-testid="arti-evolution-empty"' in ARTI or 'arti-evolution-empty' in ARTI
    assert 'memoryLogAtom' in ARTI


def test_schedules_entry_only_no_crud() -> None:
    assert 'data-testid="schedules-page"' in SCHEDULES
    assert "schedules.pageTitle" in SCHEDULES
    assert "schedules.pagePlaceholder" in SCHEDULES
    # no create/edit form in this slice
    assert "ScheduleDialog" not in SCHEDULES
    assert "saveSchedules" not in SCHEDULES
    assert "创建设计委托" not in SCHEDULES
    assert "积分消耗上限" not in SCHEDULES
    assert "试运行" not in SCHEDULES


def test_i18n_keys_zh_en() -> None:
    for blob in (ZH, EN):
        assert '"home.designSchedules"' in blob
        assert '"home.arti"' in blob
        assert '"home.artiBeta"' in blob
        assert '"arti.canDoTitle"' in blob
        assert '"arti.learnedTitle"' in blob
        assert '"arti.cap.review.title"' in blob
        assert '"arti.cap.research.title"' in blob
        assert '"arti.cap.comingSoon"' not in blob  # unused since the #381 product COMMENT
        assert '"arti.memoryPlaceholder"' in blob
    assert '"设计委托"' in ZH
    assert '"Arti"' in ZH
    assert '"Beta"' in ZH
    assert '"我能主动做的"' in ZH
    assert '"我学会的"' in ZH
    assert '"画布巡检"' in ZH
    assert '"设计调研"' in ZH


def test_css_rail_badge_and_arti_shell() -> None:
    assert ".ca-rail__badge" in HOME_CSS
    assert ".ca-arti__level" in HOME_CSS
    assert ".ca-arti__cap" in HOME_CSS
    assert ".ca-arti__tab" in HOME_CSS
    assert ".ca-switch:disabled" in HOME_CSS


def test_out_of_scope_untouched() -> None:
    """P0-2 memory CRUD, P1 schedules CRUD, #362/@, #364 review — not this tip's job."""
    assert "更正记忆" not in ARTI
    assert "通过对话修改记忆" not in ARTI
    assert "基础信息" not in ARTI
    assert "创建设计委托" not in SCHEDULES
    assert "积分消耗上限" not in SCHEDULES
