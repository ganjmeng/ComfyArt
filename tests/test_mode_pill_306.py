"""#306: Home + canvas mode pill shows mode name, never agent product shortLabel."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_mode_options_labels():
    src = (ROOT / 'src/ui/modeOptions.ts').read_text()
    assert "t('composer.agent')" in src
    assert "t('composer.image')" in src
    assert "t('common.video')" in src
    assert 'MODE_OPTIONS' in src
    assert 'modeOf' in src


def test_composer_pill_uses_mode_name_not_shortLabel():
    src = (ROOT / 'src/ui/Composer.tsx').read_text()
    assert 'modeOf(mode)' in src
    assert 'MODE_OPTIONS' in src
    assert "from './modeOptions'" in src
    assert 'modeInfo[1]' in src
    assert 'shortLabel(agent)' not in src
    assert 'shortLabel(current)' not in src
    assert "from './AgentPicker'" in src
    assert all('shortLabel' not in line for line in src.splitlines() if 'AgentPicker' in line and 'from' in line)


def test_home_pill_uses_mode_name_not_shortLabel():
    src = (ROOT / 'src/home/Home.tsx').read_text()
    assert 'modeOf(mode)' in src
    assert 'MODE_OPTIONS' in src
    assert "from '../ui/modeOptions'" in src
    assert 'shortLabel(current)' not in src
    assert 'shortLabel(agent)' not in src
    assert all('shortLabel' not in line for line in src.splitlines() if 'from' in line and 'AgentPicker' in line)


def test_composer_agent_i18n():
    en = (ROOT / 'src/locales/en.json').read_text()
    zh = (ROOT / 'src/locales/zh.json').read_text()
    assert '"composer.agent": "Agent"' in en
    assert '"composer.agent": "Agent"' in zh


def test_error_wrap_still_present_from_305():
    """#306 acceptance: errors not clipped — #305 already shipped wrap; keep as regression."""
    css = (ROOT / 'src/styles/overlays.css').read_text()
    block_start = css.index('.ca-chat__notice[data-level="error"]')
    block = css[block_start:block_start + 220]
    assert 'white-space: normal' in block
    assert 'overflow-wrap: anywhere' in block
