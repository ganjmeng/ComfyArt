"""Source contract: Auto still estimate tip shows provider/model from estimate (Live/effective)."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_genpanel_estimate_tip_prefers_provider_model():
    body = (ROOT / "src/ui/GenPanel.tsx").read_text(encoding="utf-8")
    assert "estDetail?.provider && estDetail?.model" in body
    assert re.search(r"\$\{estDetail\.provider\}/\$\{estDetail\.model\}", body)


def test_dispatch_estimate_overlays_effective_for_auto_still():
    body = (ROOT / "api/provider_admin.py").read_text(encoding="utf-8")
    assert "_still_auto_effective_tip" in body
    assert "generate_image.effective" in body or "never gif_default" in body
