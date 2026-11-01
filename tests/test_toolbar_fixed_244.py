"""#244: 快捷编辑 and 对话 are fixed toolbar tools (快捷编辑 first); defaults match product order with no
dividers; fixed tools stay off the customize pin list; legacy default prefs migrate."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
node = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@node
def test_fixed_tools_and_migration(tmp_path):
    out = tmp_path / "tp.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "toolbar_prefs.ts"})
    g = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert g["fixed"] == ["quick", "chat"]
    assert g["defaults"] == ["quick", "chat", "upscale", "cutout", "erase"]
    assert g["fresh"] == g["broken"] == g["defaults"]
    assert g["legacyMigrated"] == g["defaults"]
    assert g["unpinnedChat"]["pinned"] == ["quick", "chat", "upscale", "erase"]
    assert g["unpinnedChat"]["names"] is False
    assert g["unpinnedBoth"] == ["quick", "chat", "erase"]
    assert g["reordered"] == ["quick", "chat", "upscale"]
    assert g["save"] == ["quick", "chat", "inpaint"]


def test_preview_markup():
    src = (ROOT / "src/ui/ImageToolbar.tsx").read_text()
    dlg = src[src.index("export function CustomizeDialog"):]
    # fixed tools first, then removable ones, then ⋯ and download
    assert "{fixedShown.map(btn)}" in dlg
    assert "!isFixed(x.id)).map(btn)" in dlg
    assert dlg.index("{fixedShown.map(btn)}") < dlg.index("!isFixed(x.id)).map(btn)")
    # no sep in the customize preview bar
    preview = dlg[dlg.index("ca-cz__bar"):dlg.index("ca-cz__grid")]
    assert "ca-bar__sep" not in preview
    # main toolbar: #283 version A (supersedes #244) puts the upstream 5231d59 sep back right before download
    main = src[src.index("export function ImageToolbar"):src.index("export function CustomizeDialog")]
    assert 'hint={t(\'common.download\')}' in main or 'hint={t("common.download")}' in main
    # #570: the transform swap bar has its own download; check the normal bar only
    bar = main[main.index("{pinned.map(barTool)}"):]
    assert bar.split("Icons.download")[0].split("Popover")[-1].count("ca-bar__sep") == 1
    # fixed tools get no unpin ×, stay off the pin list, and cannot be toggled off
    assert "{!fixed && <button" in src and "!isFixed(id) && setPinned" in dlg and "withFixed(pinned)" in dlg
    assert "cards.filter((x) => !isFixed(x.id))" in dlg
    css = (ROOT / "src/styles/overlays.css").read_text()
    assert ".ca-cz__tool--rm { background: var(--ca-hover); }" in css
    x = css[css.index(".ca-cz__x {"):]
    x = x[:x.index("}")]
    assert "background: none" in x and "border-radius: 50%" not in x
    tip = (ROOT / "src/styles/base.css").read_text()
    assert ".ca-tip {" in tip and ".ca-tip__key" in tip
    # #261: 对话 shows no Shift Enter (names-on grey hint / names-off tip); 快捷编辑 keeps Tab
    chat = [ln for ln in src.splitlines() if "id: 'chat'" in ln][0]
    quick = [ln for ln in src.splitlines() if "id: 'quick'" in ln][0]
    assert "Shift Enter" not in chat and "hint:" not in chat
    assert "hint: 'Tab'" in quick or 'hint: "Tab"' in quick
    multi = (ROOT / "src/ui/MultiToolbar.tsx").read_text()
    mchat = [ln for ln in multi.splitlines() if "canvasChat.chat" in ln][0]
    assert "Shift Enter" not in mchat


def test_default_order_has_no_inpaint_expand():
    prefs = (ROOT / "src/ui/toolbarPrefs.ts").read_text()
    assert "DEFAULT_PINNED = ['quick', 'chat', 'upscale', 'cutout', 'erase']" in prefs
    assert "FIXED_TOOLS = ['quick', 'chat']" in prefs
    assert "'inpaint'" in prefs and "'expand'" in prefs
    # inpaint/expand live in MENU_MAIN, not defaults
    assert "MENU_MAIN = ['inpaint', 'expand'" in prefs
