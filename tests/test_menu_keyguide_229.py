"""#229: More menu fits a 1280x800 window; first-open no-Key notice on Home."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
node = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
                          reason="needs node + npm install")


@node
def test_popover_placement_stays_in_viewport(tmp_path):
    out = tmp_path / "p.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "popover_place.ts"})
    fits, flips, below, above, pinned = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert fits == {"left": 772, "top": 80} and flips["top"] == 700 - 8 - 300 and "maxHeight" not in flips
    assert below["top"] == 80 and below["maxHeight"] == 800 - 8 - 80
    assert above["maxHeight"] == 740 - 16 and above["top"] == 8
    assert pinned == {"left": 772, "top": 8, "maxHeight": 184}
    for p in (below, above):  # whole panel, so the last item (Fill Artboard) can be scrolled to
        assert p["top"] >= 8 and p["top"] + p["maxHeight"] <= 792


def test_popover_scrolls_when_capped():
    src = (ROOT / "src/ui/Popover.tsx").read_text()
    assert "placePopover(" in src and "overflowY: 'auto'" in src and "scrollHeight" in src


def test_home_shows_existing_no_key_notice_on_open():
    home = (ROOT / "src/home/Home.tsx").read_text()
    notice = (ROOT / "src/ui/NoKeyNotice.tsx").read_text()
    assert "refreshKeyStatus()" in home and "<NoKeyNotice" in home
    assert home.index("<NoKeyNotice") < home.index('className="ca-landing__box"')  # above the input bar
    # same style and copy as the Agent panel notice; gone once a Key is configured
    assert 'className={`ca-chat__notice' in notice and 'data-level="error"' in notice
    assert "t('agentPanel.noWavespeedKey')" in notice and "t('agentPanel.setWavespeedKey')" in notice
    assert "status.configured) return null" in notice and "keySettingsOpenAtom.set(true)" in notice
    assert "<KeySettings />" in (ROOT / "src/home/HomeApp.tsx").read_text()
    assert "!keyStatus?.configured" in (ROOT / "src/ui/AgentPanel.tsx").read_text()


def test_notice_copy_unchanged():
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    assert zh["agentPanel.noWavespeedKey"] == "还没有设置 WaveSpeed Key，ComfyArt Agent 暂时不能用。"
    assert zh["agentPanel.setWavespeedKey"] == "去设置 Key" and en["agentPanel.setWavespeedKey"] == "Set key"


@node
def test_threshold_shows_two_decimals(tmp_path):
    out = tmp_path / "u.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "threshold_usd.ts"})
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert got == ["0.50", "0.00", "1.00", "2.25", "10.00", "0.13", "0.00"]
    ks = (ROOT / "src/ui/KeySettings.tsx").read_text()
    assert "setUsd(thresholdUsd(v))" in ks and "setUsd(thresholdUsd(x))" in ks and "String(v)" not in ks
    assert "t('wsKey.confirmUsd', usd.trim() && Number.isFinite(Number(usd)) ? thresholdUsd(Number(usd)) : 'X')" in ks  # label reads $0.50
