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
def test_duplicate_name_saves_new_skill_and_keeps_original(lang: str) -> None:
    r = report()[lang]["dup"]
    assert r["ids"] == ["poster-2", "poster-3"]  # 2nd import -> -2, 3rd -> -3
    assert r["names"] == ["Poster", "Poster"]  # display name unchanged
    assert r["skillMds"] == ["comfyart/skills/poster-2/SKILL.md", "comfyart/skills/poster-3/SKILL.md", "comfyart/skills/poster/SKILL.md"]
    assert "NEW" in r["secondMd"]
    assert r["origSame"] is True  # original skill files byte-for-byte unchanged


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_folder_import_unchanged(lang: str) -> None:
    r = report()[lang]["folder"]
    assert r["id"] == "poster" and r["skillMds"] == ["comfyart/skills/poster/SKILL.md"]


def test_dialog_copy_and_error_in_drop_zone() -> None:
    assert ZH["skillsImport.title"] == "导入技能" and EN["skillsImport.title"] == "Import a skill"
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
    # no conflict dialog / prompt: duplicates import silently as a new skill
    assert "onConflict" not in DIALOG and "skill-import-conflict" not in DIALOG and "keepBoth" not in DIALOG
    assert not any(k.startswith("skillsImport.conflict") for d in (ZH, EN) for k in d)
    assert ZH["skillsImport.menu"] == "导入技能" and EN["skillsImport.menu"] == "Import a Skill"
    assert ZH["skillsImport.drop"].endswith("拖到此处") and "拖到这里" not in ZH["skillsImport.drop"]
