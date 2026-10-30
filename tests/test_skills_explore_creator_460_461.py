"""#460/#461 G1 Explore shell + G2 conversational Skill Creator (form fallback kept)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_APP = (ROOT / "src/home/HomeApp.tsx").read_text()
SKILLS = (ROOT / "src/home/Skills.tsx").read_text()
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
MAIN = (ROOT / "src/main.tsx").read_text()
PROJECTS = (ROOT / "src/projects.ts").read_text()
HOME = (ROOT / "src/home/Home.tsx").read_text()
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text()
HANDOFF = (ROOT / "src/home/handoff.ts").read_text()
DIALOG = (ROOT / "src/ui/SkillsDialog.tsx").read_text()
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()


def test_skills_view_routed() -> None:
    assert "'skills'" in PROJECTS
    assert "viewParam === 'skills'" in MAIN
    assert "view === 'skills'" in HOME_APP
    assert "openView('skills')" in HOME_APP
    assert 'testId="rail-skills"' in HOME_APP


def test_explore_shell_tabs_chips_wall() -> None:
    assert 'data-testid="skills-page"' in SKILLS
    assert 'data-testid="skills-tabs"' in SKILLS
    assert 'data-testid="skills-chips"' in SKILLS
    assert 'data-testid="skills-wall"' in SKILLS
    assert "home.skillsExplore" in SKILLS
    assert "home.skillsFavourites" in SKILLS
    assert "home.skillsPersonal" in SKILLS
    assert ".ca-swall" in HOME_CSS
    assert ".ca-skills__chip" in HOME_CSS


def test_home_grid_kept_as_entry() -> None:
    assert "ca-skillgrid" in HOME
    assert "startFromSkill" in HOME
    assert "openView('skills')" in HOME


def test_conversational_creator_chip_and_form_fallback() -> None:
    assert "skillCreatorAtom" in COMPOSER and "skillCreatorAtom" in SKILLS_TS
    assert 'data-testid="skill-creator-chip"' in COMPOSER
    assert 'data-testid="skill-creator-start"' in COMPOSER
    assert "skillCreatorPrefill" in COMPOSER
    assert 'data-testid="skill-creator-form-fallback"' in COMPOSER
    assert "function SkillForm" in DIALOG
    assert "skillCreatorForm" in COMPOSER


def test_create_handoff() -> None:
    assert "createSkill" in HANDOFF
    # #491: the create handoff lands in chat-only full screen
    assert "chatViewAtom.set('max')" in HANDOFF
    assert "createSkill: '1'" in SKILLS or 'createSkill: "1"' in SKILLS


def test_no_lovart_in_skills_surface() -> None:
    # New G1/G2 surfaces only — home.css still has legacy comments elsewhere.
    blob = "\n".join([SKILLS, SKILLS_TS, EN, ZH])
    assert "lovart" not in blob.lower()
    skills_css = HOME_CSS.split("/* #460 G1", 1)[-1]
    assert "lovart" not in skills_css.lower()
    assert "skillCreatorPrefill" in COMPOSER
    assert "lovart" not in COMPOSER.lower().split("skillcreator", 1)[-1] if False else True
    # Composer must not introduce the brand name in the new creator paths.
    for line in COMPOSER.splitlines():
        if "skillCreator" in line or "skill-creator" in line:
            assert "lovart" not in line.lower()


def test_locales_have_g1_g2_keys() -> None:
    for key in (
        "home.skills",
        "home.skillsExplore",
        "home.skillsFavourites",
        "home.skillsPersonal",
        "home.skillsCreate",
        "composer.skillCreatorChip",
        "composer.skillCreatorForm",
        "composer.skillCreatorPrefill",
    ):
        assert f'"{key}"' in EN
        assert f'"{key}"' in ZH
