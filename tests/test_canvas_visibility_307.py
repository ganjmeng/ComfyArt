"""#307 trimmed (Ashley): readable text, GenPanel dock floor, abort clears empty frames. No Lovart empty chrome / no zoom-to-fit."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_lovart_minimap_empty_chrome():
    src = (ROOT / 'src/ui/CanvasTools.tsx').read_text()
    assert 'CanvasMinimap' not in src
    assert 'ca-minimap__frame' not in src
    assert 'useState(false)' in src  # minimap default off
    css = (ROOT / 'src/styles/shell.css').read_text()
    assert '.ca-minimap__frame' not in css


def test_no_layers_empty_restructure():
    src = (ROOT / 'src/ui/SidePanel.tsx').read_text()
    assert "t('sidePanel.noLayersYet')" not in src
    assert 'data-section=' not in src
    assert 'setLayers' not in src
    # history default open + LayerTree always (pre-#307)
    assert 'useState(true)' in src
    assert '<LayerTree editor={editor} />' in src
    en = (ROOT / 'src/locales/en.json').read_text()
    zh = (ROOT / 'src/locales/zh.json').read_text()
    assert 'sidePanel.noLayersYet' not in en
    assert 'sidePanel.noLayersYet' not in zh


def test_text_default_not_near_black():
    src = (ROOT / 'src/shapes/TextShape.tsx').read_text()
    assert 'defaultTextColor' in src
    assert 'readableTextColor' in src
    assert "color: defaultTextColor()" in src
    assert 'color: readableTextColor(p.color)' in src
    assert "color: '#000000'" not in src.split('getDefaultProps')[1].split('}')[0]
    assert 'color: defaultTextColor()' in src.split('class TextTool')[1]
    css = (ROOT / 'src/styles/shell.css').read_text()
    assert '.ca-text__rich .ProseMirror' in css and 'color: inherit' in css


def test_genpanel_clears_dock():
    src = (ROOT / 'src/ui/GenPanel.tsx').read_text()
    assert "querySelector('.ca-dock')" in src
    assert 'dockTop' in src


def test_no_select_results_zoom():
    src = (ROOT / 'src/jobs.ts').read_text()
    # #307: manual (non-quiet) selectResults must not zoom; Agent follow lives in followResultViewport (#322)
    sel = src.split('export function selectResults')[1].split('export function followResultViewport')[0]
    assert 'zoomToSelection' not in sel


def test_abort_clears_empty_poster():
    src = (ROOT / 'src/jobs.ts').read_text()
    assert 'interrupted' in src
    assert 'composePrompt' in src
    assert 'holder.meta.temp || holder.meta.quiet' in src


def test_image_toolbar_stamps_default_text_color():
    src = (ROOT / 'src/ui/ImageToolbar.tsx').read_text()
    assert 'defaultTextColor' in src
    assert 'color: defaultTextColor()' in src
