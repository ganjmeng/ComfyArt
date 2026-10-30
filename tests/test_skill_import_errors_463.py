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
    # Mutation m1 (freeSkillId dropped -> overwrite) trips the ids / origSame asserts here.
    r = report()[lang]["dup"]
    assert "error" not in r, r
    assert r["ids"] == ["poster-2", "poster-3"]  # 2nd import -> -2, 3rd -> -3
    assert r["names"] == ["Poster", "Poster"]  # display name unchanged
    assert r["skillMds"] == ["comfyart/skills/poster-2/SKILL.md", "comfyart/skills/poster-3/SKILL.md", "comfyart/skills/poster/SKILL.md"]
    assert "NEW" in r["secondMd"]
    assert r["origSame"] is True  # original skill files byte-for-byte unchanged


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_same_zip_three_times_and_old_sha256_unchanged(lang: str) -> None:
    r = report()[lang]["same3"]
    assert "error" not in r, r
    assert r["ids"] == ["poster", "poster-2", "poster-3"]
    assert r["names"] == ["Poster", "Poster", "Poster"]
    assert r["dirs"] == ["poster", "poster-2", "poster-3"]
    assert r["shaBefore"] and r["shaAfter"] == r["shaBefore"]


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_skill_tool_edits_by_id_and_never_overwrites_ambiguous_name(lang: str) -> None:
    r = report()[lang]["tool"]
    assert r.get("list") == ["poster", "poster-2"], r  # list returns ids
    assert r["byId"] == {"saved": "Poster", "id": "poster-2", "description": ""} and r["editedInstr"] == "EDITED"
    assert r["otherSame"] is True  # the other same-name skill is byte-identical
    assert r["byName"] == {"saved": "Poster", "id": "poster-3", "description": ""}  # two match -> new skill
    assert r["bothSame"] is True


GUIDE = {"zh": "Skill 创建成功，先试试效果吧", "en": "Skill created. Give it a try"}
SKIPPED = {"zh": "不支持的文件已跳过：tool.exe", "en": "Unsupported files were skipped: tool.exe"}


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_import_lands_on_new_skill_detail_with_guide(lang: str) -> None:
    r = report()[lang]["landing"]
    assert "error" not in r, r
    # Mutation m8 (land on the old id) trips this ids assertion.
    assert r["ids"] == ["poster", "poster-2", "poster-3"]  # duplicate lands on the new -2/-3 id, never the old one
    assert r["guides"] == [GUIDE[lang]] * 3
    assert r["origSame"] is True  # original byte-identical after the duplicate imports
    assert r["skipped"] == ["tool.exe"] and r["skipId"] == "poster-4"
    assert r["skipGuide"] == GUIDE[lang]  # skipped info is NOT in the guide
    assert r["skipToast"] == SKIPPED[lang]  # second half of main's skillsDialog.importedSkipped, shown once via main's toast
    assert r["noSkipToasts"] == ["", "", ""]  # nothing skipped -> no toast


def test_import_navigation_wiring_and_old_notice_removed() -> None:
    page = (ROOT / "src/home/Skills.tsx").read_text()
    dlg = (ROOT / "src/ui/SkillsDialog.tsx").read_text()
    assert "openImportedSkill(landing)" in page and "if (landing.skipped) showMemoryToast(landing.skipped, 'info')" in page
    assert "skillsImport.skipped" not in EN and "skillsImport.skipped" not in ZH
    assert "<SkillsDialog" not in page  # HomeApp already mounts the dialog
    assert "openSkillEditor(landing.id)" in dlg and "skillImportGuideAtom.set(landing.guide)" in dlg
    assert "skills-import-note" not in page and "skillsImport.done" not in page
    assert "skillsImport.done" not in EN and "skillsImport.done" not in ZH
    assert "setView({ kind: 'edit', skill: s })" in dlg and 'data-testid="skill-import-guide"' in dlg  # #484 skill page (Preview/Code)
    assert EN["skillsImport.created"] == GUIDE["en"] and ZH["skillsImport.created"] == GUIDE["zh"]
    assert EN["skillsImport.release"] == "Release to import" and ZH["skillsImport.release"] == "松开以导入"  # drag-over copy unchanged


def test_progress_copy_upload_then_extract() -> None:
    assert "skillsImport.importing" not in EN and "skillsImport.importing" not in ZH
    assert ZH["skillsImport.uploading"] == "上传中...{0}%" and ZH["skillsImport.extracting"] == "解析中..."
    assert EN["skillsImport.uploading"] == "Uploading...{0}%" and EN["skillsImport.extracting"] == "Extracting..."
    assert "t('skillsImport.uploading', progress.pct)" in DIALOG and "t('skillsImport.extracting')" in DIALOG
    assert "importZip(f, setProgress)" in DIALOG


def test_close_x_writes_nothing() -> None:
    # Only the top-right × closes; it just unmounts the dialog (no import, no write). Behavioural check is Playwright.
    page = (ROOT / "src/home/Skills.tsx").read_text()
    assert "onClose={() => setImporting(false)}" in page
    assert "onClose={onClose}" in DIALOG and "common.cancel" not in DIALOG
    run = DIALOG[DIALOG.index("const run ="):DIALOG.index("const takeZip")]
    assert "onClose" not in run  # closing never goes through the import path


def test_skill_tool_wired_with_id() -> None:
    bl = (ROOT / "src/botLayout.ts").read_text()
    assert "skill: async (_editor, args) => skillTool(args)" in bl and "s.name === args.name" not in bl
    canvas = (ROOT / "api/mcp_tools/canvas.py").read_text()
    seg = canvas[canvas.index('"skill": _tool('):canvas.index('"custom_workflow"')]
    assert '"id": {"type": "string"}' in seg


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_folder_import_unchanged(lang: str) -> None:
    r = report()[lang]["folder"]
    assert r["id"] == "poster" and r["skillMds"] == ["comfyart/skills/poster/SKILL.md"]


def test_dialog_copy_and_error_in_drop_zone() -> None:
    assert ZH["skillsImport.title"] == "导入技能" and EN["skillsImport.title"] == "Import a skill"
    assert EN["skillsImport.drop"] == "Drop a Skill folder or ZIP file here" and ZH["skillsImport.drop"] == "将技能文件夹或 ZIP 文件拖到此处"
    assert ZH["skillsImport.note.formats"] == "支持 Claude Code、Codex 及其他标准技能格式"
    assert EN["skillsImport.note.formats"] == "Supports Claude Code, Codex, and other standard skill formats"
    assert ZH["skillsImport.note.skillMd"] == "必须包含 SKILL.md" and EN["skillsImport.note.skillMd"] == "Must include SKILL.md"
    for lang, d in (("zh", ZH), ("en", EN)):
        for code, text in ERR[lang].items():
            assert d[f"skillsImport.error.{code}"] == text
        assert not any("点击" in v or "click to" in v.lower() for k, v in d.items() if k.startswith("skillsImport."))
    drop = DIALOG[DIALOG.index('className="ca-skimport__drop"'):DIALOG.index("</button>", DIALOG.index('data-testid="skill-import-drop"'))]
    assert 'data-testid="skill-import-error"' in drop  # error rendered inside the drop zone
    assert "data-error=" in drop and "zip.current?.click()" in drop
    assert ".ca-skimport__drop[data-error]" in CSS and "#e74c3c" in CSS
    assert "common.cancel" not in DIALOG and "ca-panel__foot" not in DIALOG  # only the top-right ×
    assert "Icons.uploadArrow" in DIALOG
    assert "skillsImport.note.formats" in DIALOG and "skillsImport.note.skillMd" in DIALOG
    # no conflict dialog / prompt: duplicates import silently as a new skill
    assert "onConflict" not in DIALOG and "skill-import-conflict" not in DIALOG and "keepBoth" not in DIALOG
    assert not any(k.startswith("skillsImport.conflict") for d in (ZH, EN) for k in d)
    assert ZH["skillsImport.menu"] == "导入技能" and EN["skillsImport.menu"] == "Import a Skill"
    assert ZH["skillsImport.drop"].endswith("拖到此处") and "拖到这里" not in ZH["skillsImport.drop"]


def test_guide_is_coachmark_on_primary_action() -> None:
    dlg = (ROOT / "src/ui/SkillsDialog.tsx").read_text()
    css = (ROOT / "src/styles/overlays.css").read_text()
    assert 'className="ca-mem-toast" data-kind="guide"' not in dlg and "setTimeout(() => setGuide('')" not in dlg  # not a toast
    prim = dlg[dlg.index('className="ca-panel__foot ca-skillform__foot"'):]
    assert prim.index('data-testid="skill-form-primary"') < prim.index('data-testid="skill-import-guide"')  # bubble anchored on the primary button
    assert "onClick={onCoachDone}>{t('skillsImport.skip')}" in prim and "onClick={onCoachDone}>{t('skillsImport.next')}" in prim  # both only close
    assert (ZH["skillsImport.skip"], ZH["skillsImport.next"], EN["skillsImport.skip"], EN["skillsImport.next"]) == ("跳过", "下一步", "Skip", "Next")
    assert ".ca-coach::after" in css and "border-top-color: #1f1f1f" in css  # arrow points down at the button


def test_progress_real_bytes_monotonic_to_100() -> None:
    # Mutation m9 (hardcoded N) trips this.
    r = report()["progress"]
    p = r.get("pcts")
    assert p and len(p) >= 3, r  # read in several chunks
    assert all(a <= b for a, b in zip(p, p[1:])), p
    assert p[-1] == 100 and len(set(p)) >= 3, p
    assert r["phases"][-1] == "extract" and "extract" not in r["phases"][:-1]


def test_folder_drop_shows_only_extracting() -> None:
    # No real byte progress for a dropped folder: phase goes straight to extract, so only 解析中.../Extracting... shows.
    walk = DIALOG[DIALOG.index("run(async () => { setProgress({ phase: 'extract' })"):]
    assert walk.index("setProgress({ phase: 'extract' })") < walk.index("await walk(entry, out)")
    assert "importEntries(out, entry.name" in walk and "setProgress" not in walk[walk.index("await walk"):walk.index("importEntries(out")]
    assert "progress.phase === 'upload' ? t('skillsImport.uploading', progress.pct) : t('skillsImport.extracting')" in DIALOG
