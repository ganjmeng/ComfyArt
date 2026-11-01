"""#305: WaveSpeed Key / billing state machine & honest save status."""
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_key_missing_helper_is_the_ui_truth():
    ks = (ROOT / "src/wavespeedKey.ts").read_text()
    assert "export const keyMissing = (s: KeyStatus | null) => !!s && !s.configured" in ks
    settings = (ROOT / "src/ui/KeySettings.tsx").read_text()
    assert "if (s === null) return t('wsKey.checking')" in settings
    assert "if (!s.configured) return t('wsKey.notSet')" in settings
    panel = (ROOT / "src/ui/AgentPanel.tsx").read_text()
    assert "keyMissing(keyStatus)" in panel
    assert "!keyStatus?.configured" not in panel
    notice = (ROOT / "src/ui/NoKeyNotice.tsx").read_text()
    assert "if (!status || status.configured) return null" in notice


def test_need_key_is_soft_like_cost_declined():
    comfy = (ROOT / "src/comfy.ts").read_text()
    assert "export class NeedKeyError extends Error" in comfy
    assert "throw new NeedKeyError()" in comfy
    jobs = (ROOT / "src/jobs.ts").read_text()
    assert "e instanceof NeedKeyError" in jobs
    assert "soft" in jobs


def test_error_notice_cta_wraps():
    css = (ROOT / "src/styles/overlays.css").read_text()
    line = [l for l in css.splitlines() if '.ca-chat__notice[data-level="error"]' in l][0]
    assert "white-space: nowrap" not in line
    assert "white-space: normal" in line


def test_save_project_rejects_null_404():
    projects = (ROOT / "src/projects.ts").read_text()
    assert "if (!entry) throw new Error(t('err.requestFailed', 404))" in projects
    header = (ROOT / "src/ui/ProjectHeader.tsx").read_text()
    # #568: header shows no Saved label at all; only the failed-save retry renders
    assert "if (state !== 'error') return null" in header
    auto = (ROOT / "src/autosave.ts").read_text()
    assert "{ state: 'pending' }" in auto  # never green before a real persist


def test_composer_keeps_draft_when_key_missing():
    composer = (ROOT / "src/ui/Composer.tsx").read_text()
    assert "if (keyMissing(key))" in composer
    assert "keySettingsOpenAtom.set(true)" in composer
    # inside send(): key check comes before clearing the draft for this send
    send = composer[composer.index("const send = ()"):]
    assert send.index("if (keyMissing(key))") < send.index("draftAtom.set('')")
    home = (ROOT / "src/home/Home.tsx").read_text()
    assert "if (keyMissing(key))" in home


def test_models_respect_enabled():
    ws = (ROOT / "src/wavespeed.ts").read_text()
    assert "cloudEnabledAtom" in ws
    assert "body.enabled !== false" in ws
    assert "features = enabled ?" in ws


def test_needs_confirm_rounds_like_plan_quote():
    import sys
    sys.path.insert(0, str(ROOT / "api"))
    # import without full server: load just the function via exec of snippet
    src = (ROOT / "api/wavespeed.py").read_text()
    assert "round(float(price), 4) >= round(float(limit), 4)" in src
    # unit-level: replicate the policy
    def needs_confirm(price, limit):
        if limit == 0:
            return True
        return round(float(price), 4) >= round(float(limit), 4)
    assert round(0.49994, 4) == 0.4999
    assert needs_confirm(0.4999, 0.5) is False
    assert needs_confirm(0.5, 0.5) is True
    assert needs_confirm(0.50004, 0.5) is True
    assert needs_confirm(0.01, 0) is True


def test_save_key_refreshes_bot_without_open_chat_null():
    ks = (ROOT / "src/wavespeedKey.ts").read_text()
    assert "m.refreshBot({ refresh: true })" in ks
    assert "m.loadCloudModels()" in ks
    assert "openChat(null)" not in ks
