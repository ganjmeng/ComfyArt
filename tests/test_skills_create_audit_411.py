"""#411: Skills-create audit — surfaces inventory, tip harness shots, no product UI change.

Mocks only ($0). Set AUDIT411_SHOTS=docs/design/411/78/after to write PNGs.
Never spends WaveSpeed; real-call reuse quality stays on the EL-approved $5 budget with #410.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUDIT = (ROOT / "docs/design/411/78/AUDIT.md").read_text(encoding="utf-8")
NOTES = (ROOT / "docs/design/411/78/NOTES.md").read_text(encoding="utf-8")
HARNESS = (ROOT / "tests/js/skills411/main.tsx").read_text(encoding="utf-8")
COMPOSER = (ROOT / "src/ui/Composer.tsx").read_text(encoding="utf-8")
DIALOG = (ROOT / "src/ui/SkillsDialog.tsx").read_text(encoding="utf-8")
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
HOME = (ROOT / "src/home/Home.tsx").read_text(encoding="utf-8")
ARTI = (ROOT / "src/home/Arti.tsx").read_text(encoding="utf-8")
PROACTIVE = (ROOT / "src/proactive.ts").read_text(encoding="utf-8")
BOT = (ROOT / "src/botLayout.ts").read_text(encoding="utf-8")

REF_DIR = ROOT / "docs/design/411/78/reference"
REF_FILES = [
    "skills-explore.png",
    "create-dropdown.png",
    "creator-chip.png",
    "creator-prefill.png",
    "personal-list.png",
    "edit-dialog.png",
    "import-dialog.png",
    "publish-dialog.png",
    "slash-picker.png",
]

SCENES = [
    "menu-skills",
    "form-empty",
    "form-filled",
    "dialog-list",
    "dialog-list-empty",
    "dialog-edit",
    "slash-picker",
    "skill-chip",
    "home-grid",
    "arti-skills",
]

SURFACES = [
    ("SkillForm", DIALOG, "function SkillForm"),
    ("SkillsDialog", DIALOG, "function SkillsDialog"),
    ("composer skills menu", COMPOSER, "skillCreator"),
    ("create from chat", COMPOSER, "createSkillFromThisChat"),
    ("slash picker", COMPOSER, "slash"),
    ("skill chip", COMPOSER, "skillAtom"),
    ("home start-from-skill", HOME, "startFromSkill"),
    ("arti skills tab", ARTI, "arti-skills-skeleton"),
    ("evolveSkill", PROACTIVE, "evolveSkill"),
    ("agent skill tool", BOT, "action === 'save'"),
    ("saveSkill storage", SKILLS, "async function saveSkill"),
    ("importFolder", SKILLS, "async function importFolder"),
]

pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


def test_audit_uses_reference_not_brand_name():
    assert "lovart" not in AUDIT.lower()
    assert "lovart" not in NOTES.lower()
    assert "「reference」" in AUDIT


def test_audit_covers_acceptance_rows():
    for needle in (
        "触发",
        "创建",
        "存储",
        "复用",
        "Explore",
        "Slash",
        "Import",
        "Publish",
        "Arti",
        "G1",
        "G2",
        "Ideas",
        "$5",
    ):
        assert needle in AUDIT, f"AUDIT.md missing {needle}"


def test_harness_covers_every_scene():
    for s in SCENES:
        assert f"'{s}'" in HARNESS or f'"{s}"' in HARNESS


def test_reference_crops_present():
    for name in REF_FILES:
        p = REF_DIR / name
        assert p.is_file() and p.stat().st_size > 100, f"missing reference crop {name}"


def test_surface_inventory_locked():
    for label, src, needle in SURFACES:
        assert needle in src, f"{label}: expected {needle!r}"


def test_gaps_point_to_pm_cards_not_inline_fix():
    assert "PM" in AUDIT or "项目经理" in AUDIT
    assert "不改变产品" in AUDIT or "does **not** change product" in AUDIT or "不改" in AUDIT


def test_g2_from_410_called_out():
    assert "#410" in AUDIT and "G2" in AUDIT


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    d = tmp_path_factory.mktemp("skills411")
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/skills411/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(d / "app.js")},
    )
    css = "\n".join(
        (ROOT / "src/styles" / f).read_text()
        for f in ("base.css", "canvas.css", "shell.css", "overlays.css", "home.css")
    )
    (d / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0;background:var(--ca-page,#f5f5f5)}}"
        f"{css}</style><div id=root></div><script src=app.js></script>",
        encoding="utf-8",
    )
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"no chromium: {e}")
        yield b
        b.close()


def _open(browser, bundle, scene, lang, theme):
    page = browser.new_page(viewport={"width": 780, "height": 900}, device_scale_factor=2)
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(bundle) else r.abort())
    page.goto(f"{bundle}/index.html?lang={lang}&theme={theme}&scene={scene}")
    page.wait_for_function("window.__ready")
    page.wait_for_timeout(200)
    return page


def test_harness_renders_form_and_dialog(browser, bundle):
    page = _open(browser, bundle, "form-filled", "zh", "light")
    assert page.locator("[data-testid=form-filled]").count() == 1
    assert "技能创建器" in page.locator(".ca-gen__title").inner_text()
    page.close()
    page = _open(browser, bundle, "dialog-list", "zh", "light")
    assert page.locator("[data-testid=dialog-list]").count() == 1
    page.close()
    page = _open(browser, bundle, "home-grid", "zh", "light")
    assert page.locator("[data-testid=home-grid] .ca-skillcard").count() >= 2
    page.close()


def test_shoot_audit_shots(browser, bundle):
    out = os.environ.get("AUDIT411_SHOTS")
    if not out:
        pytest.skip("set AUDIT411_SHOTS to write PNGs")
    dest = Path(out)
    dest.mkdir(parents=True, exist_ok=True)
    matrix = [("zh", "light"), ("en", "dark")]
    written = []
    for scene in SCENES:
        for lang, theme in matrix:
            page = _open(browser, bundle, scene, lang, theme)
            path = dest / f"{scene}-{lang}-{theme}.png"
            page.locator("#scene").screenshot(path=str(path))
            written.append(path.name)
            page.close()
    manifest = dest / "manifest.json"
    manifest.write_text(json.dumps({"scenes": SCENES, "files": written}, indent=2) + "\n", encoding="utf-8")
    assert len(written) == len(SCENES) * len(matrix)
