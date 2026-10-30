"""#463 G4 — Import a Skill: ZIP drag & drop dialog; folder import kept."""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/home/Skills.tsx").read_text()
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
DIALOG = (ROOT / "src/ui/SkillsDialog.tsx").read_text()
IMPORT = (ROOT / "src/ui/SkillImportDialog.tsx").read_text()
CSS = (ROOT / "src/styles/overlays.css").read_text()
EN = json.loads((ROOT / "src/locales/en.json").read_text())
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())


def test_create_menu_has_import_entry() -> None:
    assert 'data-testid="skills-create"' in SKILLS  # conversational create kept
    assert 'data-testid="skills-create-menu"' in SKILLS
    assert 'data-testid="skills-import"' in SKILLS
    assert "SkillImportDialog" in SKILLS


def test_drop_dialog_zip_and_folder() -> None:
    assert "onDrop" in IMPORT and "onDragOver" in IMPORT
    assert 'accept=".zip,application/zip"' in IMPORT
    assert "importZip" in IMPORT and "importEntries" in IMPORT
    assert "webkitGetAsEntry" in IMPORT  # folder drop
    assert "zip.current?.click()" in IMPORT  # click still opens a picker
    assert "skillsImport.hint" not in IMPORT and "folderInstead" not in IMPORT
    assert ".ca-skimport__drop" in CSS


def test_folder_import_kept_in_manage_dialog() -> None:
    assert "skillsDialog.importFolder" in DIALOG and "webkitdirectory" in DIALOG
    assert "SkillImportDialog" not in DIALOG and "skillsImport.zip" not in DIALOG


def test_product_copy() -> None:
    assert "t('skillsImport.menu')" in SKILLS
    assert EN["skillsImport.menu"] == "Import a Skill" and ZH["skillsImport.menu"] == "导入技能"
    assert EN["skillsImport.drop"] == "Drop a Skill folder or ZIP file here"
    assert ZH["skillsImport.drop"] == "将技能文件夹或 ZIP 文件拖到此处"
    assert "skillsImport.hint" not in EN and "skillsImport.hint" not in ZH
    assert EN["skills.noSkillMdInFolder"]  # folder import error kept


def test_shared_import_path() -> None:
    assert "export async function importEntries" in SKILLS_TS
    assert "export async function importZip" in SKILLS_TS
    assert "unzipSync" in SKILLS_TS and "__MACOSX" in SKILLS_TS


def test_i18n_parity() -> None:
    keys = [k for k in EN if k.startswith("skillsImport.")]
    assert len(keys) >= 7
    for k in keys:
        assert ZH.get(k) and ZH[k] != EN[k]


def test_no_brand_word() -> None:
    for src in (SKILLS, SKILLS_TS, IMPORT, CSS):
        assert "trav" + "ol" not in src.lower()[::-1]


@pytest.mark.skipif(not shutil.which("node") or not (ROOT / "node_modules/fflate").exists(), reason="node/fflate missing")
def test_fflate_reads_nested_skill_zip() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("poster/SKILL.md", "---\nname: Poster\n---\nDo posters")
        z.writestr("poster/files/ref.md", "hello")
        z.writestr("__MACOSX/poster/._SKILL.md", "x")
    script = (
        "const {unzipSync}=require('fflate');const fs=require('fs');"
        "const o=unzipSync(new Uint8Array(fs.readFileSync(0)));"
        "console.log(JSON.stringify(Object.keys(o).sort()))"
    )
    out = subprocess.run(["node", "-e", script], input=buf.getvalue(), capture_output=True, cwd=ROOT, check=True)
    names = json.loads(out.stdout)
    assert "poster/SKILL.md" in names and "poster/files/ref.md" in names
