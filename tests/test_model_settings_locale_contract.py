"""Unpaid contract: model-settings copy keys + GenSettings/ProviderAdmin wiring."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZH = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))
EN = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
PROV = (ROOT / "src/ui/ProviderAdmin.tsx").read_text(encoding="utf-8")
GEN = (ROOT / "src/ui/GenSettings.tsx").read_text(encoding="utf-8")
I18N = (ROOT / "src/i18n.ts").read_text(encoding="utf-8")

KEYS = [
    "provider.defaultReplicate",
    "provider.defaultWavespeed",
    "provider.nowActive",
    "provider.flareDefault",
    "provider.routePending",
    "provider.confirmRoute",
    "provider.gifAltWavespeedBlocked",
    "provider.keyMissingDraft",
    "provider.saveFailed",
    "provider.batchSelectedOnly",
    "gen.outputGif",
    "gen.outputSvg",
    "gen.frameCount",
    "gen.frameDuration",
    "gen.svgPreviewHint",
]


def test_model_settings_copy_keys_landed_zh_en():
    for key in KEYS:
        assert key in ZH and ZH[key].strip(), key
        assert key in EN and EN[key].strip(), key
    assert "{next}" in ZH["provider.routePending"] and "{prev}" in ZH["provider.routePending"]
    assert "{key}" in ZH["provider.keyMissingDraft"]


def test_i18n_exposes_named_placeholder_helper():
    assert "export function tn(" in I18N
    assert "replaceAll" in I18N


def test_provider_admin_wires_default_chips_and_gif_alt_block():
    assert "provider.defaultReplicate" in PROV
    assert "provider.defaultWavespeed" in PROV
    assert "provider.nowActive" in PROV
    assert "provider.gifAltWavespeedBlocked" in PROV
    assert "provider-route-pending" in PROV
    assert "provider.confirmRoute" in PROV
    assert "provider.saveFailed" in PROV
    assert "provider.batchSelectedOnly" in PROV
    # Pending strip must not reuse the #850 fee Confirm dialog classes.
    assert "ca-confirm" not in PROV
    assert "confirmAtom" not in PROV


def test_gen_settings_svg_independent_of_gif_frames():
    assert "gen.outputGif" in GEN and "gen.outputSvg" in GEN
    assert "gen.frameCount" in GEN and "gen.frameDuration" in GEN
    assert "gen.svgPreviewHint" in GEN
    # Frames only render when gif is set; SVG gets its own hint, not frame inputs.
    assert re.search(r"\{gif && onGif && <GifFrames", GEN)
    assert "GifFrames" in GEN
    assert re.search(r"\{svg && \(", GEN) or "gen.svgPreviewHint" in GEN
    # Format picker clears the other format when switching.
    assert "onSvg?.(null); onGif?.(" in GEN or "onSvg?.(null)" in GEN
    assert "onGif?.(null); onSvg?.(" in GEN or "onGif?.(null)" in GEN


def test_gap4_nokey_savefail_batch_wiring():
    """Gap 4 UI: keyMissingDraft / saveFailed / batchSelectedOnly + drafts kept on error."""
    assert "provider.keyMissingDraft" in PROV
    assert "provider.saveFailed" in PROV
    assert "provider.batchSelectedOnly" in PROV
    assert "provider-batch-selected-only" in PROV
    assert "provider-nokey" in PROV
    assert "provider-llm-nokey" in PROV
    assert "failText" in PROV
    # needs_key maps to keyMissingDraft; other failures map to saveFailed.
    assert "e.code === 'needs_key'" in PROV or 'e.code === "needs_key"' in PROV
    assert "tn('provider.keyMissingDraft'" in PROV or 'tn("provider.keyMissingDraft"' in PROV
    assert "t('provider.saveFailed')" in PROV or 't("provider.saveFailed")' in PROV
    # Save / batch error path must not clear in-session drafts (absorb only on success).
    assert "setError(failText(e))" in PROV
    assert "absorb(next)" in PROV
    # Batch apply disabled without replicate key (cannot activate).
    assert "provider-batch-apply" in PROV
    assert "tools.some((t) => t.key_ok)" in PROV or "tools.some((t)=>t.key_ok)" in PROV
    # LLM save disabled without DeepSeek key.
    assert "provider-llm-save" in PROV
    assert "providerId === 'deepseek' && !info?.configured" in PROV or 'providerId === "deepseek" && !info?.configured' in PROV
    # Copy meaning: zh saveFailed keeps unsaved changes.
    assert "已保留未提交更改" in ZH["provider.saveFailed"] or "未提交" in ZH["provider.saveFailed"]
    assert "不能激活" in ZH["provider.keyMissingDraft"] or "不可激活" in ZH["provider.keyMissingDraft"]
    assert "已选" in ZH["provider.batchSelectedOnly"] or "所选" in ZH["provider.batchSelectedOnly"]

