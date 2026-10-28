"""#192: the cost confirm dialog shows the quoted amount in the same format as the estimate next to Send (≈$0.039,
never the 2-decimal $0.04), via one shared formatter (src/usd.ts)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
node = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@node
def test_usd_format(tmp_path):
    out = tmp_path / "usd.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "usd.ts"})
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert got == ["0.039", "0.0893", "0.04", "0.10", "1.00", "0.0035", "0.069", "0.24", "12.50", "0.00"]


def test_confirm_uses_ui_credits_not_dollars():
    """#397: cloud confirm dialog shows credits; GenPanel estimate next to Send stays USD (#192) for now."""
    comfy = (ROOT / "src/comfy.ts").read_text()
    ask = comfy[comfy.index("export function askCost"):comfy.index("export async function queuePrompt")]
    assert "uiCredits(price ?? 0)" in ask and "usd(price" not in ask
    gen = (ROOT / "src/ui/GenPanel.tsx").read_text()
    assert "≈$${usd(estimate)}" in gen and "estimate.toFixed(2)" not in gen
