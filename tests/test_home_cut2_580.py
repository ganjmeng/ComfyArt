"""#580 cut 2 — source/data contract: three image slots, special cards constant, tabs, tokens."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "src/home/Home.tsx").read_text()
LAYOUT = (ROOT / "src/home/featuredLayout.ts").read_text()
SKILLS = (ROOT / "src/skills.ts").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()


def test_three_image_slots_with_fallback():
    assert "quickStartCover?: string" in SKILLS and "featured?: string[]" in SKILLS
    assert "QUICK_START_COVERS" in SKILLS and "FEED_COVERS" in SKILLS
    assert "export function skillQuickStartCover" in SKILLS
    assert "skill.featured?.length" in SKILLS  # feed set first, else examples / presets


def test_tabs_and_special_cards_constants():
    assert "export const HOME_TABS = ['explore', 'assets', 'inspiration', 'pinterest']" in LAYOUT
    assert "{ id: 'capture', col: 0, slot: 1 }" in LAYOUT and "{ id: 'connector', col: 1, slot: 4 }" in LAYOUT
    assert "QUICK_START_VIDEO_FIRST" in SKILLS and "HOME_ASSET_CHIPS" in LAYOUT and "--ca-feed-col-w: 298.7px" in CSS
    assert "withSpecialCards(" in HOME and "<Assets />" in HOME and "CHIP_LABEL" in HOME


def test_tokens_and_full_bleed_css():
    for v in ("--ca-tabs-gap", "--ca-tabs-font", "--ca-chip-bg", "--ca-chip-on-bg", "--ca-homechips-top", "--ca-homebox-float-bottom"):
        assert v in CSS
    assert ".ca-homechips { position: sticky" in CSS
    assert "border-radius: var(--ca-featured-radius, 12px); background: none;" in CSS
    assert "Lovart" not in HOME + LAYOUT + SKILLS + CSS
