"""#712 audit: every model id a built-in skill / template / auto-pick path / curated default can route to without the
user naming one is registered in the runtime catalog (api/wavespeed.py load_config), so no live skill hits the
UnregisteredModel error. Explicit fallbacks on auto rows must be registered too."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ComfyArt.api import auto_models, wavespeed

ROOT = Path(__file__).resolve().parent.parent
ID = re.compile(r'''["']([a-z0-9][\w.-]*/[\w.-]+(?:/[\w.-]+)*)["']''')
VENDORS = ("wavespeed-ai/", "minimax/", "recraft-ai/", "google/", "openai/", "bytedance/", "alibaba/", "kwaivgi/",
           "black-forest-labs/", "ideogram-ai/", "midjourney/", "pruna-ai/", "bria/", "tripo3d/", "mirelo-ai/")


def _catalog() -> dict[str, set[str]]:
    return {f: {m["id"] for m in v["models"]} for f, v in wavespeed.load_config()["features"].items()}


def _registered() -> set[str]:
    """Ids a built-in WaveSpeed path may legally route to.

    load_config is the curated dropdown. size_lock may also name a raw
    wavespeed_models.json id (resolve_model). Replicate Admin short ids and
    coverage-audit counterparts are not added here: a typo of those shorts
    in a builtin path must still fail this test (it would hit
    UnregisteredModel in production).
    """
    cat = _catalog()
    every = set().union(*cat.values()) if cat else set()
    with open(wavespeed.CONFIG, encoding="utf-8") as f:
        raw = json.load(f)
    for feat in (raw.get("features") or {}).values():
        for m in feat.get("models") or []:
            if isinstance(m, dict) and m.get("id"):
                every.add(m["id"])
    return every


# Admin UI + provider catalog / route config hold Replicate short ids and
# _EXACT audit counterparts. Those are not WaveSpeed submit paths. Skip the
# sources so the shorts never enter used_ids() — and never enter _registered().
# A typo of the same short id in a real builtin path is still scanned and
# must fail (it would hit UnregisteredModel in production).
_ADMIN_OR_CATALOG = {
    "src/ui/ProviderAdmin.tsx",
    "api/provider_catalog.py",
    "api/provider_admin.py",
    "api/tool_routing.py",
}


def used_ids() -> dict[str, str]:
    """id -> where it is used (first source)."""
    cfg, out = wavespeed.load_config(), {}
    for f, spec in auto_models.load_table().items():
        rows = [(c["id"], c) for c in spec.get("categories", [])] + [(k, spec[k]) for k in ("masked", "multi_reference") if spec.get(k)]
        for rid, r in rows:
            fb = r.get("fallback") or []
            for m in [r["model"], *([fb] if isinstance(fb, str) else fb)]:
                out.setdefault(m, f"auto_models.json {f}/{rid}")
    for f, v in cfg["features"].items():
        if v.get("default"):
            out.setdefault(v["default"], f"curated default {f}")
    files = [*sorted((ROOT / "src").rglob("*.ts")), *sorted((ROOT / "src").rglob("*.tsx")), *sorted((ROOT / "api").rglob("*.py"))]
    for p in files:
        rel = str(p.relative_to(ROOT))
        if "locales" in p.parts or rel in _ADMIN_OR_CATALOG:
            continue
        for m in ID.findall(p.read_text(encoding="utf-8")):
            if m.startswith(VENDORS) and not m.endswith((".png", ".json", ".mp4", ".svg")):
                out.setdefault(m, rel)
    return out


def test_builtin_paths_use_only_registered_models():
    every = _registered()
    missing = {m: where for m, where in used_ids().items() if m not in every}
    assert not missing, f"unregistered model ids used by built-in paths: {missing}"


@pytest.mark.parametrize("feature", ["text_to_image", "image_edit"])
def test_auto_rows_registered_for_their_feature(feature):
    cat = _catalog()[feature]
    spec = auto_models.load_table()[feature]
    for r in [*spec.get("categories", []), *[spec[k] for k in ("masked", "multi_reference") if spec.get(k)]]:
        auto_models.registered(r, cat, feature)  # raises UnregisteredModel when not
