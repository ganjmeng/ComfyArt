"""Source contract: Auto still estimate tip shows provider from Live/effective; model stays submit-aligned."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_genpanel_estimate_tip_prefers_provider_model():
    body = (ROOT / "src/ui/GenPanel.tsx").read_text(encoding="utf-8")
    assert "estDetail?.provider && estDetail?.model" in body
    assert re.search(r"\$\{estDetail\.provider\}/\$\{estDetail\.model\}", body)


def test_dispatch_estimate_overlays_provider_not_model():
    body = (ROOT / "api/provider_admin.py").read_text(encoding="utf-8")
    assert "_still_auto_effective_tip" in body
    assert "do not rewrite" in body or "Keep estimate" in body
    # Must not assign Live existing over the quote model in the tip helper return.
    helper = body.split("def _still_auto_effective_tip", 1)[1].split("async def dispatch_estimate", 1)[0]
    assert '"model": eff' not in helper and "'model': eff" not in helper
