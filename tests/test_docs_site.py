"""#35: docs site (VitePress) and the settings-menu entry that opens it."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs-site"
PAGES = sorted(p.name for p in (DOCS / "guides").glob("*.md"))
TOC = ["getting-started", "home", "models", "wavespeed-key", "canvas", "design", "generate", "image-tools",
       "elements-mockups", "video", "audio-3d", "assets", "agent", "mcp", "custom-workflows"]


def _all_md():
    return [p for p in DOCS.rglob("*.md") if "node_modules" not in p.parts]


def test_zh_en_pages_match_and_cover_toc():
    assert PAGES == sorted(p.name for p in (DOCS / "zh/guides").glob("*.md"))
    assert sorted(f"{n}.md" for n in TOC) == PAGES
    cfg = (DOCS / ".vitepress/config.mts").read_text()
    for n in TOC:
        assert f"${{p}}{n}`" in cfg
    assert "provider: 'local'" in cfg and "/ComfyArt/" in cfg


def test_no_real_key_no_lovart_no_rapidocr():
    key = re.compile(r"\b[0-9a-f]{32,}\b")
    for p in _all_md() + [ROOT / "README.md", ROOT / "README.zh.md"]:
        s = p.read_text()
        assert "lovart" not in s.lower(), p
        assert "rapidocr" not in s.lower(), p
        assert not key.search(s), p


def test_model_pages_mention_key_and_cost():
    for d, words in (("guides", ("WaveSpeed Key", "cost")), ("zh/guides", ("WaveSpeed Key", "费用"))):
        for n in ("generate", "image-tools", "elements-mockups", "video", "audio-3d", "agent", "models"):
            s = (DOCS / d / f"{n}.md").read_text()
            for w in words:
                assert w in s, (d, n, w)


def test_settings_menu_user_guide():
    src = (ROOT / "src/ui/SettingsMenu.tsx").read_text()
    assert "https://ganjmeng.github.io/ComfyArt/" in src and "zh/" in src
    assert 'data-testid="settings-guide"' in src and 'className="ca-menu__item"' in src
    assert json.loads((ROOT / "src/locales/en.json").read_text())["settings.userGuide"] == "User Guide"
    assert json.loads((ROOT / "src/locales/zh.json").read_text())["settings.userGuide"] == "使用指南"


def test_pages_workflow_is_path_filtered():
    wf = (ROOT / ".github/workflows/docs-site.yml").read_text()
    assert "docs-site/**" in wf and "deploy-pages" in wf and "branches: [main]" in wf
