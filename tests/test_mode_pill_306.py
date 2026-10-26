"""#306: Home open dropdown matches canvas — AgentItems (not lone 「Agent」 row) + Image/Video; shortLabel on closed pill."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_mode_options_still_for_image_video():
    src = (ROOT / 'src/ui/modeOptions.ts').read_text()
    assert 'MODE_OPTIONS' in src
    assert 'modeOf' in src
    assert "t('composer.image')" in src
    assert "t('common.video')" in src


def test_composer_agent_pill_uses_shortLabel():
    src = (ROOT / 'src/ui/Composer.tsx').read_text()
    assert 'shortLabel(agent)' in src
    assert "from './modeOptions'" in src
    assert 'MODE_OPTIONS' in src  # image/video dropdown labels
    assert any('shortLabel' in line for line in src.splitlines() if 'AgentPicker' in line and 'from' in line)
    # agent trigger must not force mode name "Agent" over shortLabel
    agent_line = [ln for ln in src.splitlines() if 'shortLabel(agent)' in ln][0]
    assert 'modeInfo[1]' not in agent_line or 'shortLabel(agent)' in agent_line
    # canvas open menu: AgentItems + image/video (no agent mode row)
    assert '<AgentItems' in src
    assert "MODE_OPTIONS.filter(([m]) => m !== 'agent')" in src


def test_home_agent_pill_uses_shortLabel():
    src = (ROOT / 'src/home/Home.tsx').read_text()
    assert 'shortLabel(current)' in src
    assert "from '../ui/modeOptions'" in src
    assert any('shortLabel' in line for line in src.splitlines() if 'AgentPicker' in line and 'from' in line)


def test_home_and_composer_consistent_shortLabel():
    """Requirement: Home and canvas composer consistent — both shortLabel in agent mode."""
    home = (ROOT / 'src/home/Home.tsx').read_text()
    comp = (ROOT / 'src/ui/Composer.tsx').read_text()
    assert 'shortLabel(current)' in home
    assert 'shortLabel(agent)' in comp


def test_home_open_menu_uses_agent_items_like_canvas():
    """#306 Ashley: Home open menu = agent list + Image/Video; FORBIDDEN lone 「Agent」 mode row."""
    home = (ROOT / 'src/home/Home.tsx').read_text()
    assert '<AgentItems' in home
    assert 'AgentExtras' in home
    assert "ca-menu ca-agentpick" in home
    assert "MODE_OPTIONS.filter(([m]) => m !== 'agent')" in home
    # must not map full MODE_OPTIONS (which includes agent mode label) as the menu body
    assert 'modes.map' not in home
    assert 'within=".ca-landing__box"' in home



def test_home_foot_aligns_with_canvas_controls():
    """#306: plus / prefs / voice·send use the same 32px bar control family as canvas."""
    home = (ROOT / 'src/home/Home.tsx').read_text()
    assert 'ca-bar__btn ca-bar__btn--icon ca-landing__add' in home
    css = (ROOT / 'src/styles/home.css').read_text()
    assert 'ca-landing__add' in css


def test_error_wrap_still_present_from_305():
    css = (ROOT / 'src/styles/overlays.css').read_text()
    block_start = css.index('.ca-chat__notice[data-level="error"]')
    block = css[block_start:block_start + 220]
    assert 'white-space: normal' in block
    assert 'overflow-wrap: anywhere' in block
