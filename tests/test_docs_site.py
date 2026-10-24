"""#35: docs site (Mintlify, docs-site/) and the settings-menu entry that opens it."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs-site"
PAGES = sorted(p.name for p in (DOCS / "guides").glob("*.mdx"))
TOC = ["getting-started", "home", "models", "wavespeed-key", "canvas", "design", "generate", "image-tools",
       "elements-mockups", "video", "audio-3d", "assets", "agent", "mcp", "custom-workflows"]


def _all_md():
    return [p for p in DOCS.rglob("*.md*") if "node_modules" not in p.parts]


def test_zh_en_pages_match_and_cover_toc():
    assert PAGES == sorted(p.name for p in (DOCS / "zh/guides").glob("*.mdx"))
    assert sorted(f"{n}.mdx" for n in TOC) == PAGES
    nav = json.loads((DOCS / "docs.json").read_text())["navigation"]["languages"]
    pages = {l["language"]: [p for t in l["tabs"] for g in t["groups"] for p in g["pages"]] for l in nav}
    assert pages["en"] == ["index"] + [f"guides/{n}" for n in TOC]
    assert pages["zh"] == ["zh/index"] + [f"zh/guides/{n}" for n in TOC]


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
            s = (DOCS / d / f"{n}.mdx").read_text()
            for w in words:
                assert w in s, (d, n, w)


def test_settings_menu_user_guide():
    src = (ROOT / "src/ui/SettingsMenu.tsx").read_text()
    assert "DOCS_SITE = 'https://ghhsdob.mintlify.site'" in (ROOT / "src/docsConfig.ts").read_text()
    assert "from '../docsConfig'" in src and "/zh`" in src and "http" not in src.split("docsUrl", 1)[1].split("}", 1)[0]
    assert 'data-testid="settings-guide"' in src and 'className="ca-menu__item"' in src
    assert json.loads((ROOT / "src/locales/en.json").read_text())["settings.userGuide"] == "User Guide"
    assert json.loads((ROOT / "src/locales/zh.json").read_text())["settings.userGuide"] == "使用指南"


def test_no_pages_workflow():
    assert not (ROOT / ".github/workflows/docs-site.yml").exists()


ORIGINAL_IMAGES = ["adjust-panel", "agent-result", "agent-settings", "assets", "audio-cards", "audio-dialog",
    "boolean-menu", "brand-kit-editor", "composer-video", "crop-bar", "edit-elements", "fill-editor", "font-picker",
    "frame-toolbar", "generator", "home", "image-settings", "image-to-3d", "image-toolbar", "layers-panel",
    "mockup-panel", "multi-select", "pen-nodes", "project-menu", "projects", "rich-text", "size-presets",
    "video-editor", "video-toolbar", "preview-en", "preview-zh", "canvas", "models", "run-on", "instances-dialog",
    "settings-menu"]


def test_no_original_site_images():
    """Every screenshot is our own (docs-site/images/ours/<lang>/), never the original guide's images."""
    imgs = DOCS / "images"
    assert {p.parent.name for p in imgs.rglob("*") if p.is_file()} <= {"en", "zh"}
    assert all(p.relative_to(imgs).parts[0] == "ours" for p in imgs.rglob("*") if p.is_file())
    pat = re.compile(r"/images/(" + "|".join(ORIGINAL_IMAGES) + r")\.(webp|gif|png)|jtydhr88\.github|mintcdn")
    for p in _all_md():
        s = p.read_text()
        assert not pat.search(s), p
        for lang, name in re.findall(r'src="/images/ours/(en|zh)/([a-z0-9-]+)\.webp"', s):
            assert lang == ("zh" if p.relative_to(DOCS).parts[0] == "zh" else "en"), (p, name)
            assert (imgs / "ours" / lang / f"{name}.webp").is_file(), (p, name)


def test_docs_site_url_not_placeholder():
    # #211: the hosted site is live; the old placeholder must not ship in src or dist.
    for p in list((ROOT / "src").rglob("*.ts*")) + list((ROOT / "dist").rglob("*.js")):
        assert "comfyart.mintlify.app" not in p.read_text(errors="ignore"), p
    assert any("ghhsdob.mintlify.site" in p.read_text(errors="ignore") for p in (ROOT / "dist").rglob("*.js"))
