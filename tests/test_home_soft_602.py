"""#602 soft FU — landing section mt 24, composer pill shrink/expand, skillcard dual fit."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src/styles/home.css").read_text(encoding="utf-8")
HOME = (ROOT / "src/home/Home.tsx").read_text(encoding="utf-8")
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")


def test_landing_section_mt_token_24():
    assert re.search(r"--ca-landing-section-mt:\s*24px\b", CSS)
    assert "margin-top: var(--ca-landing-section-mt)" in CSS
    # must not keep the pre-#602 hard 64px on .ca-landing__section
    assert not re.search(r"\.ca-landing__section\s*\{[^}]*margin-top:\s*64px", CSS)


def test_homebox_radius_24_and_compact_pill_tokens():
    assert re.search(r"--ca-homebox-radius:\s*24px\b", CSS)
    assert re.search(r"--ca-homebox-compact-h:\s*52px\b", CSS)
    assert "border-radius: var(--ca-homebox-radius)" in CSS
    # compact float hides toolbar, keeps send slot
    assert ".ca-landing__box[data-floating][data-compact]" in CSS
    assert ".ca-landing__box[data-floating][data-compact] .ca-landing__foot > :not(.ca-composer__slotwrap) { display: none; }" in CSS
    # interaction wired in Home
    assert "data-compact={(floating && !boxExpanded) || undefined}" in HOME
    assert "setBoxExpanded" in HOME


def test_skillcard_dual_fit_api_and_css():
    assert '.ca-skillcard__cover[data-fit="contain"] img' in CSS
    assert "object-fit: contain" in CSS
    assert "quickStartCoverFit?: 'cover' | 'contain'" in SKILLS
    assert "export function skillQuickStartCoverFit" in SKILLS
    assert "skillQuickStartCoverFit(s)" in HOME
    assert 'data-fit={skillQuickStartCoverFit(s)}' in HOME
    # default path remains cover (helper returns cover unless marked contain)
    assert "skill.quickStartCoverFit === 'contain' ? 'contain' : 'cover'" in SKILLS


def test_no_competitor_brand_string_in_touched_src():
    blob = HOME + SKILLS + CSS
    assert "Lovart" not in blob
    assert "lovart" not in blob
