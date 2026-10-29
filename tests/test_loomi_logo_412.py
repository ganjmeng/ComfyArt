"""#412: the old smiley is gone; Loomi mark is used everywhere Icons.agent was."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMILEY = 'M8.2 15h7.6a4.2 4.2 0 0 1-7.6 0'


def test_icons_agent_is_loomi_mono():
    src = (ROOT / 'src/ui/icons.tsx').read_text()
    assert SMILEY not in src
    assert 'agent: <LoomiMono />' in src
    assert 'useId()' in src and 'viewBox="0 0 24 24" fill="currentColor"' in src


def test_welcome_uses_full_mark():
    src = (ROOT / 'src/ui/AgentPanel.tsx').read_text()
    assert '<span className="ca-chat__hello">{Icons.agent}</span>' not in src
    assert src.count('<span className="ca-chat__hello"><LoomiMono /></span>') == 2
    css = (ROOT / 'src/styles/shell.css').read_text()
    assert 'invert(1)' not in css.split('.ca-chat__hello')[1][:200]  # follows --ca-strong


def test_docs_logos_are_loomi():
    for f in ('logo.svg', 'logo-dark.svg'):
        s = (ROOT / 'docs-site' / f).read_text()
        assert 'Loomi' in s and 'ComfyArt' not in s
    assert '"name": "Loomi"' in (ROOT / 'docs-site/docs.json').read_text()
    assert 'ComfyArt' not in (ROOT / 'docs-site/favicon.svg').read_text()
