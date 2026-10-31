"""#495 sidebar — expand/collapse + recent list on existing HomeApp rail (no parallel component)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME_APP = (ROOT / "src/home/HomeApp.tsx").read_text()
HOME_CSS = (ROOT / "src/styles/home.css").read_text()
BASE_CSS = (ROOT / "src/styles/base.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())


def test_modifies_homeapp_rail_in_place() -> None:
    assert 'data-testid="account-rail"' in HOME_APP
    assert "export function HomeApp" in HOME_APP
    # no parallel sidebar component file
    home_dir = ROOT / "src/home"
    assert not (home_dir / "Sidebar.tsx").exists()
    assert not (home_dir / "AppSidebar.tsx").exists()


def test_collapse_persisted() -> None:
    assert "RAIL_COLLAPSE_KEY" in HOME_APP
    assert "comfyart.rail.collapsed" in HOME_APP
    assert "writeLocal(RAIL_COLLAPSE_KEY" in HOME_APP
    assert "readLocal(RAIL_COLLAPSE_KEY)" in HOME_APP
    assert 'data-testid="rail-collapse"' in HOME_APP
    assert 'data-testid="rail-expand"' in HOME_APP


def test_nav_order_and_labels() -> None:
    # order in source: new → home → projects → skills → (assets gated) → schedules → arti
    order = [
        m.start()
        for m in [
            re.search(r'testId="rail-new"', HOME_APP),
            re.search(r'testId="rail-home"', HOME_APP),
            re.search(r'testId="rail-projects"', HOME_APP),
            re.search(r'testId="rail-skills"', HOME_APP),
            re.search(r'testId="rail-schedules"', HOME_APP),
            re.search(r'testId="rail-arti"', HOME_APP),
        ]
    ]
    assert all(x is not None for x in order)
    assert order == sorted(order)
    assert 'label={t(\'home.projects\')}' in HOME_APP or 'label={t("home.projects")}' in HOME_APP
    assert "home.designSchedules" in HOME_APP
    assert ZH["home.designSchedules"] == "设计日程"
    assert EN["home.designSchedules"] == "Schedules"
    assert ZH["home.projects"] == "项目"
    assert EN["home.projects"] == "Projects"


def test_assets_hidden_until_497() -> None:
    assert "SHOW_ASSETS = false" in HOME_APP
    assert 'testId="rail-assets"' not in HOME_APP or "SHOW_ASSETS" in HOME_APP
    # must not render when flag false — gate present
    assert "SHOW_ASSETS ?" in HOME_APP or "SHOW_ASSETS &&" in HOME_APP
    # mutation: Assets must not appear as an unconditional RailBtn
    unconditional = re.findall(r"<RailBtn[^>]*testId=\"rail-assets\"", HOME_APP)
    assert unconditional == []


def test_hidden_items_absent() -> None:
    for forbidden in ("个人主页", "设计委托", "Personal homepage", "Design commission"):
        assert forbidden not in HOME_APP
    # nav label is 设计日程, not 设计委托
    assert ZH["home.designSchedules"] != "设计委托"


def test_wavespeed_and_gear_kept() -> None:
    assert 'testId="rail-ws-history"' in HOME_APP
    assert "WAVESPEED_HISTORY_URL" in HOME_APP
    assert "SettingsMenu" in HOME_APP


def test_recent_max_8_titles_menu() -> None:
    assert "RECENT_LIMIT = 8" in HOME_APP
    assert "slice(0, RECENT_LIMIT)" in HOME_APP
    assert 'data-testid="rail-recent"' in HOME_APP
    assert 'data-testid="rail-recent-menu"' in HOME_APP
    for tid in ("rail-recent-pin", "rail-recent-rename", "rail-recent-duplicate", "rail-recent-delete"):
        assert f'data-testid="{tid}"' in HOME_APP
    assert "setPinned" in HOME_APP and "renameProject" in HOME_APP
    assert "duplicateProject" in HOME_APP and "confirmDelete" in HOME_APP
    assert "ca-menu__item--danger" in HOME_APP
    # collapsed: recent not shown
    assert "expanded && recent" in HOME_APP


def test_expanded_css_and_theme_var() -> None:
    assert ".ca-rail[data-expanded]" in HOME_CSS
    assert "width: 160px" in HOME_CSS
    assert "var(--ca-rail-bg)" in HOME_CSS
    assert "--ca-rail-bg: #f2f2f2" in BASE_CSS
    assert "--ca-rail-bg: #1c1c1c" in BASE_CSS
    assert ".ca-rail__recent-name" in HOME_CSS
    assert "text-overflow: ellipsis" in HOME_CSS


def test_i18n_collapse_keys() -> None:
    assert ZH["home.collapseSidebar"]
    assert EN["home.collapseSidebar"]
    assert ZH["home.expandSidebar"]
    assert EN["home.expandSidebar"]
    assert ZH["home.assets"] == "我的素材"
    assert EN["home.assets"] == "Assets"
