"""#463 v2 — ZIP/folder import errors, atomic no-write, no silent overwrite (real src/skills.ts + fflate, in-memory store)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")
DIALOG = (ROOT / "src/ui/SkillImportDialog.tsx").read_text()
CSS = (ROOT / "src/styles/overlays.css").read_text()
EN = json.loads((ROOT / "src/locales/en.json").read_text())
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())

ERR = {
    "zh": {"noSkillMd": "未找到 SKILL.md", "unreadable": "无法读取这个文件", "tooLarge": "文件超过 20MB"},
    "en": {"noSkillMd": "No SKILL.md found", "unreadable": "Couldn't read this file", "tooLarge": "File is larger than 20 MB"},
}


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"import463-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/import463/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("case,code", [
    ("noSkillMd", "noSkillMd"),
    ("corrupt", "unreadable"),
    ("notZip", "unreadable"),
    ("slipDots", "unreadable"),
    ("slipAbs", "unreadable"),
    ("tooLarge", "tooLarge"),
    ("tooLargeUnzipped", "tooLarge"),
])
def test_each_error_message_and_writes_nothing(lang: str, case: str, code: str) -> None:
    r = report()[lang][case]
    assert r["ok"] is False
    assert r["message"] == ERR[lang][code]
    assert r["writes"] == 0  # atomic: no file, no upload


def test_limit_is_20mb() -> None:
    assert report()["maxBytes"] == 20 * 1024 * 1024


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_valid_zip_imports(lang: str) -> None:
    r = report()[lang]
    assert r["ok"]["ok"] is True
    assert "comfyart/skills/poster/SKILL.md" in r["okFiles"]


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_name_conflict_never_silently_overwrites(lang: str) -> None:
    r = report()[lang]
    assert r["asked"] == ["poster", "poster", "poster"]  # always asks
    assert r["conflictCancel"] == {"error": "SkillImportCancelled", "writes": 0, "oldKept": True, "keys": []}
    assert r["conflictKeep"]["oldKept"] is True and "comfyart/skills/poster-2/SKILL.md" in r["conflictKeep"]["keys"]
    assert r["conflictReplace"]["oldKept"] is False
    assert any("/poster/versions/" in k for k in r["conflictReplace"]["keys"])  # replace keeps the old one as a version
    assert r["noPromptSilent"] == {"answered": False, "writes": 0}  # nothing written until the user answers


def test_dialog_copy_and_error_in_drop_zone() -> None:
    assert ZH["skillsImport.title"] == "导入技能" and EN["skillsImport.title"] == "Import a skill"
    assert ZH["skillsImport.menu"] == "导入" and EN["skillsImport.menu"] == "Import"
    assert ZH["skillsImport.note.formats"] == "支持 Claude Code、Codex 及其他标准 Skill 格式"
    assert EN["skillsImport.note.formats"] == "Supports Claude Code, Codex, and other standard Skill formats"
    assert ZH["skillsImport.note.skillMd"] == "必须包含 SKILL.md" and EN["skillsImport.note.skillMd"] == "Must include SKILL.md"
    for lang, d in (("zh", ZH), ("en", EN)):
        for code, text in ERR[lang].items():
            assert d[f"skillsImport.error.{code}"] == text
        assert not any("点击" in v or "click to" in v.lower() for k, v in d.items() if k.startswith("skillsImport."))
    drop = DIALOG[DIALOG.index('className="ca-skimport__drop"'):DIALOG.index("</button>", DIALOG.index('data-testid="skill-import-drop"'))]
    assert 'data-testid="skill-import-error"' in drop  # error rendered inside the drop zone
    assert "data-error=" in drop and "zip.current?.click()" in drop
    assert ".ca-skimport__drop[data-error]" in CSS and "#e74c3c" in CSS
    assert "skillsImport.note.formats" in DIALOG and "skillsImport.note.skillMd" in DIALOG
    assert "onConflict" in DIALOG and 'data-testid="skill-import-conflict"' in DIALOG
