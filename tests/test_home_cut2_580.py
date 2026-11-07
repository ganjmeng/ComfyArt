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


def test_featured_v1_and_collages_pinned_590():
    c = "0e92302302de2102ab6f66aa7633a40945a381c7"
    assert f"const FEED_V1 = '{c}'" in SKILLS
    feed = {
        "poster-differentiated-compiler": "['580/featured-v1/poster', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']]",
        "rednote-cover-maker": "['580/featured-v1/social', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']]",
        "brand-identity-director": "['786/wash/brand/featured', WASH_786, ['01.webp', '02.webp', '03.webp', '04.webp']]",  # #786
        "packaging-design-director": "['777/wash/packaging/featured', 'e270088ea1695f5200669649e6e832057e9c8a6a', ['01.webp', '02.webp', '03.webp', '04.webp']]",  # WASH_777 #777
        "cover-design-director": "['580/featured-v1/thumbnail', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']]",
        "banner-design-director": "['580/featured-v1/banner', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']]",
        "character-sheet-design": "['788/wash/character/featured', WASH_788, ['01.webp', '02.webp', '03.webp', '04.webp']]",  # #788
        "product-tvc-advertisement-generator": "['779/wash/product/featured', WASH_779, ['01.webp', '02.webp', '03.webp', '04.webp']]",  # #779
        "interior-architectural-visualization": "['580/featured-v1/interior', FEED_V1, ['01.webp', '02.webp', '03.webp', '04.webp']]",
    }
    for sid, needle in feed.items():
        assert f"'{sid}': {needle}" in SKILLS, sid
    # #806: motion featured is the two 动态海报 template stills, not the 580 remake-era feed.
    assert "'motion-poster-generator': ['569/wash/motion/templates', 'bd043d4cff5019fc4117b5b2f3a33ae437015a28', ['01-poster-animation.webp', '02-first-to-last-frame-animation.webp']]" in SKILLS
    assert "inspiration@thumb.webp" in SKILLS and "connector@thumb.webp" in SKILLS


def test_tab_and_chip_token_values_design_table_583():
    for v in ("--ca-tabs-gap: 24px", "400 14px/22px", "--ca-tabs-on-weight: 600", "--ca-tabs-indicator-h: 0px",
              "--ca-skilltabs-gap: 20px", "400 13px/20px", "--ca-skilltabs-indicator-h: 1px",
              "--ca-chip-gap: 8px", "--ca-chip-h: 30px", "--ca-chip-py: 5px", "--ca-chip-px: 12px", "--ca-chip-on-bg: rgba(0, 0, 0, .08)"):
        assert v in CSS, v
