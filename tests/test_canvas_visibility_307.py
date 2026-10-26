"""#307: canvas visibility — minimap, layers/history, text, gen floor, zoom, abort."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_minimap_default_on():
    src = (ROOT / 'src/ui/CanvasTools.tsx').read_text()
    assert 'useState(true)' in src
    assert 'CanvasMinimap' in src
    assert 'ca-minimap__frame' in src
    css = (ROOT / 'src/styles/shell.css').read_text()
    assert '.ca-minimap__frame' in css


def test_history_and_layers_with_empty_copy():
    src = (ROOT / 'src/ui/SidePanel.tsx').read_text()
    assert 'useState(false)' in src  # history collapsed
    assert "t('sidePanel.noHistoryYet')" in src
    assert "t('sidePanel.noLayersYet')" in src
    assert 'setLayers' in src
    assert 'data-section="layers"' in src
    # layers section before history so empty copy is findable
    assert src.index("t('common.layers')") < src.index("t('sidePanel.history')")
    # must not render LayerTree unconditionally on first paint
    assert 'layers &&' in src


def test_no_layers_i18n():
    assert '"sidePanel.noLayersYet": "No layers yet"' in (ROOT / 'src/locales/en.json').read_text()
    assert '"sidePanel.noLayersYet"' in (ROOT / 'src/locales/zh.json').read_text()
    assert '"sidePanel.noLayersYet": "暂无图层"' in (ROOT / 'src/locales/zh.json').read_text()


def test_text_default_not_near_black():
    src = (ROOT / 'src/shapes/TextShape.tsx').read_text()
    assert 'defaultTextColor' in src
    assert 'readableTextColor' in src
    assert "color: defaultTextColor()" in src
    assert 'color: readableTextColor(p.color)' in src
    # getDefaultProps must not hardcode #000000
    assert "color: '#000000'" not in src.split('getDefaultProps')[1].split('}')[0]
    # TextTool must stamp theme-aware color at create time
    assert 'color: defaultTextColor()' in src.split('class TextTool')[1]


def test_genpanel_clears_dock():
    src = (ROOT / 'src/ui/GenPanel.tsx').read_text()
    assert "querySelector('.ca-dock')" in src
    assert 'dockTop' in src


def test_select_results_zooms_when_idle():
    src = (ROOT / 'src/jobs.ts').read_text()
    assert 'zoomToSelection' in src
    assert "getCameraState() === 'idle'" in src
    assert 'isPanning' in src


def test_abort_clears_empty_poster():
    src = (ROOT / 'src/jobs.ts').read_text()
    assert 'interrupted' in src
    assert 'composePrompt' in src
    assert 'holder.meta.temp || holder.meta.quiet' in src


def test_no_lovart_four_capsule_primary():
    """Product veto: do not ship Lovart four-capsule CTA as primary empty path."""
    for rel in ['src/ui/Composer.tsx', 'src/home/Home.tsx', 'src/App.tsx']:
        text = (ROOT / rel).read_text()
        assert 'What do you want to design' not in text
        assert 'Connect Pinterest' not in text
