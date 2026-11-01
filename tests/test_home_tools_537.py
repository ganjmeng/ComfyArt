"""#537 / #496: home 「实用工具」5 cards + 更多工具 + 精选 waterfall (Loomic column math; no scraped Lovart feed)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "src/home/Home.tsx").read_text()
HANDOFF = (ROOT / "src/home/handoff.ts").read_text()
LAYOUT = (ROOT / "src/home/featuredLayout.ts").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
IMG_TB = (ROOT / "src/ui/ImageToolbar.tsx").read_text()
VID_TB = (ROOT / "src/ui/VideoToolbar.tsx").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())

MAIN = ["cutout", "extend", "upscale", "inpaint", "mockup"]
MORE = ["quick", "erase", "crop", "expand", "adjust", "text", "angles", "vectorize", "move", "transform", "to3d", "lipsync", "motion", "audio"]


def test_tools_section_five_cards_and_more() -> None:
    assert 'data-testid="home-tools"' in HOME
    assert 'data-testid="home-tool-grid"' in HOME
    assert 'data-testid="home-more-tools"' in HOME
    assert 'data-testid="home-more-tools-menu"' in HOME
    for tid in MAIN:
        assert f'data-testid={{`home-tool-card-${{tool.id}}`}}' in HOME or f'home-tool-card-{tid}' in HOME
        assert f"id: '{tid}'" in HOME
    for tid in MORE:
        assert f"id: '{tid}'" in HOME
        assert f"home-more-tool-${{tool.id}}" in HOME or f"home-more-tool-{tid}" in HOME
    # layout order: tools before skill quick-start before featured
    i_tools = HOME.index('data-testid="home-tools"')
    i_skill = HOME.index('data-testid="home-start-skill"')
    i_feat = HOME.index('data-testid="home-featured"')
    assert i_tools < i_skill < i_feat


def test_no_home_recent_section() -> None:
    assert "home-recent" not in HOME
    assert "ca-landing__recent" not in HOME
    assert "recentProjects" not in HOME


def test_pick_file_then_new_project_no_autorun() -> None:
    assert "const pickTool" in HOME and "const launchTool" in HOME
    assert "toolFile.current" in HOME
    assert "newProject({ ref: viewUrl(await uploadImage(f, f.name)), tool })" in HOME
    # cancel = clear pending without project
    assert "if (!f || !tool) return" in HOME
    # handoff never auto-runs generate for home tools
    assert "homeToolAtom.set(tool)" in HANDOFF
    assert "enterMode(tool as" in HANDOFF or "enterMode('inpaint')" in HANDOFF
    assert "MODE_HOME_TOOLS" in HANDOFF
    assert "Never auto-runs" in HOME or "never auto-run" in HANDOFF.lower() or "no auto-run" in HANDOFF.lower()
    open_fn = HANDOFF.split("async function openHomeTool", 1)[1].split("\nexport ", 1)[0]
    for bad in ("generateDirect", "sendToAgent", "actions.cutout", "generate("):
        assert bad not in open_fn, bad


def test_handoff_home_tools_and_toolbars() -> None:
    assert "export type HomeToolId" in HANDOFF
    assert "export const homeToolAtom" in HANDOFF
    for tid in MAIN + MORE:
        assert f"'{tid}'" in HANDOFF
    assert "import { HOME_LANDING, homeToolAtom } from '../home/handoff'" in IMG_TB  # #570
    assert "import { homeToolAtom } from '../home/handoff'" in VID_TB
    # #570 (supersedes #545): landing per tool is data (HOME_LANDING), read by the image toolbar
    assert "HOME_LANDING[pendingHome]" in IMG_TB
    assert "upscale: 'panel'" in HANDOFF and "to3d: 'panel'" in HANDOFF and "transform: 'bar'" in HANDOFF
    assert "setMenu('more'); setInMore(pendingHome)" not in IMG_TB
    assert "pendingHome !== 'extend'" in VID_TB
    # hooks before early return
    assert IMG_TB.index("const pendingHome") < IMG_TB.index("if (!shape || !rect || mode) return null")
    assert VID_TB.index("const pendingHome") < VID_TB.index("if (!shape || !rect) return null")


def test_waterfall_layout_logic_no_scraped_feed() -> None:
    assert "featuredColumnCount" in LAYOUT and "packFeaturedColumns" in LAYOUT
    assert "featuredAspect" in LAYOUT
    assert "packFeaturedColumns(featuredItems, featuredWidth, featuredMetrics.gap" in HOME
    assert "ca-featured--waterfall" in HOME
    assert 'data-testid="home-featured-col"' in HOME
    assert "style={{ aspectRatio: aspect }}" in HOME
    assert ".ca-featured--waterfall" in CSS and ".ca-featured__col" in CSS
    # no third-party CDN / feed urls in home featured path
    low = (HOME + LAYOUT).lower()
    for bad in ("a.lovart.ai", "lovartcdn", "cdn.lovart", "http://", "https://"):
        assert bad not in low, bad
    # data remains skillFeaturedCases (our presets)
    assert "skillFeaturedCases(skills)" in HOME


def test_tool_covers_are_wash_commit_pinned() -> None:
    # #540: design wash PASS covers via toolCovers.ts (review-assets commit-pin; no WaveSpeed)
    covers = (ROOT / "src/home/toolCovers.ts").read_text()
    assert "TOOL_WASH_COMMIT" in covers and "8eb46909" in covers
    assert "TOOL_MAIN5_COMMIT = '1ecb47a'" in covers and "/540/wash-v2/main-5" in covers
    assert "540/wash" in covers and "toolCover" in covers
    assert "toolCover(" in HOME and "tool.cover" in HOME
    assert 'src={tool.cover}' in HOME
    assert ".ca-toolcard__cover" in CSS and ".ca-toolcard__cover img" in CSS
    assert ".ca-toolgrid { display: flex; gap: 16px; }" in CSS and "flex: 1 0 0" in CSS
    assert "wavespeed.com" not in (HOME + covers).lower() and "api.wavespeed" not in (HOME + covers).lower()
    # all 19 ids resolve through toolCover groups
    for tid in MAIN:
        assert f"toolCover('main-5', '{tid}')" in HOME
    for tid in MORE[:10]:
        assert f"toolCover('more-10', '{tid}')" in HOME
    for tid in MORE[10:]:
        assert f"toolCover('unique-4', '{tid}')" in HOME


def test_i18n_tools() -> None:
    assert ZH["home.tools"] == "实用工具"
    assert EN["home.tools"] == "Tools"
    assert ZH["home.moreTools"] == "更多工具"
    assert EN["home.moreTools"] == "More tools"
    assert ZH["home.toolPreciseEdit"] == "精准编辑"
    assert EN["home.toolPreciseEdit"] == "Precise edit"
    assert "home.toolPreciseEdit" in HOME


def test_featured_layout_column_math() -> None:
    """#580: 精选 masonry — fixed ≈299 column width, adaptive count (was Loomic 280–320)."""
    # smoke: file exports match expected signatures
    assert "export function featuredColumnCount(width: number, gap = FEATURED_GAP" in LAYOUT
    assert "export function packFeaturedColumns" in LAYOUT
    assert "FEATURED_COL_W = 299" in LAYOUT
    assert "Math.min(...heights)" in LAYOUT or "indexOf(Math.min" in LAYOUT


def test_more_tools_lovart_order_540() -> None:
    """#540: Lovart 10 then unique 4, exact order in MORE_HOME_TOOLS."""
    block = HOME.split("MORE_HOME_TOOLS", 1)[1].split("export function Home", 1)[0]
    ids = re.findall(r"id: '([a-z0-9]+)'", block)
    assert ids == MORE, ids
    assert "enterMode(tool" in HANDOFF or "enterMode(tool as" in HANDOFF
    assert "setCroppingShape" in HANDOFF
    assert "transform: 'bar'" in HANDOFF and "HOME_LANDING[pendingHome]" in IMG_TB  # #570: data-driven landing


def test_tool_cards_16x9_and_more_menu_icon_rows() -> None:
    # #540 ratio-fix: Lovart main cards 16:9; 更多 = icon rows only (no covers); cover kept as pin backup
    assert "aspect-ratio: 235 / 132" in CSS and "16 / 10" not in CSS
    assert "ca-menu__thumb" not in HOME and "ca-menu__thumb" not in CSS
    assert '<span className="ca-icon" aria-hidden>{MORE_TOOL_ICON[tool.id as keyof typeof MORE_TOOL_ICON]}</span>' in HOME
    assert HOME.count("toolCover('more-10'") == 10 and HOME.count("toolCover('unique-4'") == 4


def test_lovart_measured_values_540() -> None:
    """#540: Lovart DevTools @1280 — card, title, heading, trigger, dropdown rows, filled icons via one map."""
    for v in ("border-radius: 12px", "transition: transform 300ms ease", "transform: scale(1.08)",
              "height: 20px; padding: 0 6px", "font: 400 13px/20px", "font: 500 14px/22px",
              "border-radius: 6px; padding: 3px 0 3px 6px", "height: 28px; min-width: 50px; padding: 0 8px; border-radius: 8px",
              "font: 400 12px/18px", ".ca-menu--tools { width: 200px", "height: 32px; padding: 0 8px; gap: 8px; border-radius: 8px",
              "150ms cubic-bezier(.4,0,.2,1)", "width: 18px; height: 18px", "opacity: .9", "--ca-tools-row-hover: rgba(0,0,0,.03)",
              ':root[data-theme="dark"] { --ca-tools-row-hover'):
        assert v in CSS, v
    assert "box-shadow" not in CSS.split(".ca-toolcard {", 1)[1].split(".ca-menu--tools", 1)[0]
    assert "const MORE_TOOL_ICON = {" in HOME and HOME.count("rx('") == 15  # 14 tools + caret
    assert "Apache License 2.0" in HOME and "Remix" in HOME
    assert "{MORE_TOOL_ICON[tool.id as keyof typeof MORE_TOOL_ICON]}" in HOME and "{MORE_TOOLS_CARET}" in HOME
    for name in ("magic-fill", "eraser-fill", "crop-fill", "expand-diagonal-fill", "equalizer-fill", "ri-t-box-fill", "camera-switch-fill",
                 "pen-nib-fill", "drag-move-2-fill", "anticlockwise-2-fill", "box-3-fill", "chat-voice-fill", "run-fill", "music-2-fill"):
        assert name in HOME, name
