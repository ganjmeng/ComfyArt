"""#580 / #581 cut 1: home 「用 Skill 快速开始 ›」 = one row of 6 cover cards (fluid 6-col grid, 4:3 cover + title ›),
精选 waterfall 5 columns, Skills grid column 16 / row 24. Static checks + column math mirror."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "src/home/Home.tsx").read_text()
LAYOUT = (ROOT / "src/home/featuredLayout.ts").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())


def _start_block() -> str:
    return HOME.split('data-testid="home-start-skill"', 1)[1].split('data-testid="home-featured"', 1)[0]


def _rule(sel: str) -> str:
    return CSS.split(sel + " {", 1)[1].split("}", 1)[0]


def test_six_cover_cards_from_real_skills() -> None:
    assert "export const HOME_SKILL_ROW = 6" in LAYOUT
    body = _start_block()
    assert "skills.slice(0, HOME_SKILL_ROW).map" in body  # real skills, no demo data
    assert 'data-testid="home-skill-cover"' in body and "skillCover(s)" in body
    # design 5727385011: › only after the section title, not on each card
    card = body.split("ca-skillcard__name", 1)[1].split("</button>", 1)[0]
    assert "›" not in card and "ca-skillcard__chev" not in body
    # old row card pieces gone: 40×40 icon + 内置/我的 badge
    assert "ca-skillcard__icon" not in body and "home.builtIn" not in body and "ca-model__tag" not in body
    assert "onClick={() => trySkill(s)}" in body  # keeps #533 dialog behaviour


def test_head_chevron_opens_skills_explore() -> None:
    body = _start_block()
    assert 'data-testid="home-start-skill-head"' in body
    assert body.count("openView('skills')") >= 2  # heading › + 查看全部 kept
    assert "t('home.viewAll')" in body
    assert ZH["home.startFromSkill"] == "用 Skill 快速开始" and EN["home.startFromSkill"] == "Start with a Skill"


def test_row_card_css_vars() -> None:
    grid = _rule(".ca-skillgrid")
    for v in ("--ca-skillrow-cols: 6", "--ca-skillrow-gap: 16px", "--ca-skillrow-radius: 12px",
              "--ca-skillrow-title-size: 14px", "--ca-skillrow-title-line: 22px", "--ca-skillrow-title-weight: 500",
              "--ca-skillrow-title-gap"):
        assert v in grid, v
    assert "grid-template-columns: repeat(var(--ca-skillrow-cols), minmax(0, 1fr))" in grid
    assert "overflow-x" not in grid and "px; width" not in grid  # fluid, no hardcoded card width / scroll
    card = _rule(".ca-skillcard")
    assert "border: none" in card and "flex: 0 0" not in card
    cover = _rule(".ca-skillcard__cover")
    assert "aspect-ratio: var(--ca-skillrow-cover-ratio)" in cover and "border-radius: var(--ca-skillrow-radius)" in cover
    assert "var(--ca-skillrow-title-size)/var(--ca-skillrow-title-line)" in _rule(".ca-skillcard__name")
    assert "#" not in _rule(".ca-skillcard__name")  # theme vars only


def _cols(width: float, gap: int = 16) -> int:
    cw = int(re.search(r"FEATURED_COL_W = (\d+)", LAYOUT).group(1))
    return max(1, round((width + gap) / (cw + gap)))


def test_featured_columns_adapt_to_width() -> None:
    assert "Math.round((width + gap) / (colWidth + gap))" in LAYOUT
    assert _cols(928) == 3 and (928 - 2 * 16) / 3 > 297  # 1280 expanded → 3 × ≈299
    assert _cols(1568) == 5  # 1920 → 5
    assert _cols(300) == 1


def test_no_reference_brand_in_src() -> None:
    for f in (HOME, LAYOUT, CSS):
        assert "Lovart" not in f and "lovart" not in f


SKILLS_TS = (ROOT / "src/skills.ts").read_text()


def test_featured_cases_round_robin_both_types() -> None:
    """#580 P0: every skill with real images; examples for example-type, preset images for template-type;
    round-robin, no repeated image, no two adjacent tiles from the same skill."""
    helper = SKILLS_TS.split("export function skillFeaturedCases", 1)[1].split("\nexport ", 1)[0]
    assert "skill.examples" in helper and "preset.image" in helper
    assert "seen.has(c.image)" in helper and "seen.add(c.image)" in helper
    assert "for (let round = 0;" in helper
    assert "out[out.length - 1]!.skill.id === c.skill.id" in helper
    assert "break" not in helper  # no longer one-per-skill
    assert "featured: 'editorial'" in SKILLS_TS  # P2: character leads with the editorial sheet


def test_featured_heading_renamed() -> None:
    # product: section title back to 精选 / Featured; 「Skill 案例」 stays as the per-card caption
    assert ZH["home.featured"] == "精选" and EN["home.featured"] == "Featured"
    assert ZH["home.skillCase"] == "Skill 案例" and EN["home.skillCase"] == "Skill case"
    assert "<h2>{t('home.featured')}</h2>" in HOME


def test_featured_card_icon_tag_hover() -> None:
    block = HOME.split('data-testid="home-featured-card"', 1)[1].split("</button>", 1)[0]
    # item 4: small kind icon bottom-left, not the text pill
    assert 'data-testid="home-featured-kind"' in block and "Icons.imageLine" in block and "Icons.videoLine" in block
    badge = block.split("ca-featured__badge", 1)[1].split("</span></span>", 1)[0]
    assert "home.skillCase" not in badge
    # item 5: grey 「Skill 案例」 after the title
    assert 'className="ca-featured__tag">{t(\'home.skillCase\')}' in block
    assert "color: var(--ca-muted)" in CSS.split(".ca-featured__tag {", 1)[1].split("}", 1)[0]
    # item 6: no dim overlay on hover; white 开始制作 top-right kept
    assert ".ca-featured__cover::after" not in CSS
    assert "skillRun.start" in block and "onClick={() => trySkill(s, p.id)}" in block


def test_row_cover_ratio_4x3() -> None:
    assert "--ca-skillrow-cover-ratio: 4 / 3" in _rule(".ca-skillgrid")


def test_featured_masonry_metrics_are_css_vars():
    css = (ROOT / "src/styles/home.css").read_text(encoding="utf-8")
    for v in ("--ca-featured-col-w: 299px", "--ca-featured-gap: 16px", "gap: var(--ca-featured-gap"):
        assert v in css
    ts = (ROOT / "src/home/featuredLayout.ts").read_text(encoding="utf-8")
    assert "readFeaturedMetrics" in ts and "--ca-featured-col-w" in ts and "FEATURED_MAX_COLUMNS" not in ts
    assert "readFeaturedMetrics(el)" in (ROOT / "src/home/Home.tsx").read_text(encoding="utf-8")
