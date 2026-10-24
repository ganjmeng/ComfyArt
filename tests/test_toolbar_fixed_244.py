"""#244: 对话 and 快捷编辑 are fixed toolbar tools: always pinned, first, no unpin ×, and restored for users
who unpinned 对话 before the upgrade. The preview bar has one divider, after the fixed tools."""
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
    assert g["fixed"] == ["chat", "quick"]
    assert g["defaults"] == ["chat", "quick", "inpaint", "cutout", "upscale", "expand"]
    assert g["fresh"] == g["broken"] == g["defaults"]
    assert g["unpinnedChat"]["pinned"] == ["chat", "quick", "upscale", "erase"]
    assert g["unpinnedChat"]["names"] is False
    assert g["unpinnedBoth"] == ["chat", "quick", "erase"]
    assert g["reordered"] == ["chat", "quick", "upscale"]
    assert g["save"] == ["chat", "quick", "inpaint"]


def test_preview_markup():
    src = (ROOT / "src/ui/ImageToolbar.tsx").read_text()
    dlg = src[src.index("export function CustomizeDialog"):]
    # fixed tools first, a single divider after them, then the removable ones
    assert dlg.index("{fixedShown.map(btn)}") < dlg.index('<div className="ca-bar__sep" />') < dlg.index("!isFixed(x.id)).map(btn)")
    # fixed tools get no unpin × and cannot be toggled off in the list
    assert "{!fixed && <button" in src and "!isFixed(id) && setPinned" in dlg and "withFixed(pinned)" in dlg
    css = (ROOT / "src/styles/overlays.css").read_text()
    assert ".ca-cz__tool--rm { background: var(--ca-hover); }" in css
    x = css[css.index(".ca-cz__x {"):]
    x = x[:x.index("}")]
    assert "background: none" in x and "border-radius: 50%" not in x
