"""#575: skill template video field + hover muted loop contract (wiring greps + CSS). Separate from #602/#594 dual-fit."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text()
EXAMPLES = (ROOT / "src/ui/SkillExamples.tsx").read_text()
WALL = (ROOT / "src/home/Skills.tsx").read_text()
HOME = (ROOT / "src/home/Home.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()


def test_no_lovart_in_src():
    src_root = ROOT / "src"
    hits = []
    for p in src_root.rglob("*"):
        if p.is_file() and p.suffix in {".ts", ".tsx", ".css", ".json"}:
            text = p.read_text(errors="ignore")
            if "Lovart" in text or "lovart" in text:
                hits.append(str(p.relative_to(ROOT)))
    assert hits == []


def test_video_helpers_and_pending_scaffold():
    assert "export function isSkillMediaVideo" in SKILLS
    assert "export function skillCoverVideoHover" in SKILLS
    assert "export function presetVideo" in SKILLS
    assert "SKILL_VIDEO_PENDING_NEW6" in SKILLS
    assert "TODO(design): motion template mp4s" in SKILLS
    assert "preset.video TODO until design motion-01/02" in SKILLS
    assert "video?: string" in SKILLS  # SkillPreset.video


def test_explore_and_home_use_hover_helper():
    assert "skillCoverVideoHover" in WALL and "skillCoverVideoHover(videoRef.current, 'enter')" in WALL
    assert "skills-card-video" in WALL and "muted" in WALL and "loop" in WALL
    assert "skillCoverVideoHover" in HOME and "home-skill-card-video" in HOME
    assert "ca-skillcard__video" in CSS


def test_skill_examples_plays_mp4():
    assert "isSkillMediaVideo" in EXAMPLES
    assert "skill-run-example-stage-video" in EXAMPLES
    assert "muted" in EXAMPLES and "loop" in EXAMPLES and "playsInline" in EXAMPLES
    assert ".ca-skillrun__stage img, .ca-skillrun__stage video" in CSS
