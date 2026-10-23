"""#110 design blocker: no user-facing string may mention the reference app (case-insensitive)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _strings(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "_comment" or k == "lovart_order":  # internal metadata, never shown
                continue
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)
    elif isinstance(o, str):
        yield o


def test_curated_models_json_has_no_lovart():
    assert "lovart" not in (ROOT / "api/curated_models.json").read_text(encoding="utf-8").lower()


def test_locale_files_have_no_lovart():
    files = [f for f in (ROOT / "src/locales").rglob("*") if f.is_file()]
    assert files
    for f in files:
        assert "lovart" not in f.read_text(encoding="utf-8").lower(), f


def test_model_blurbs_have_no_lovart():
    data = json.loads((ROOT / "api/model_display.json").read_text(encoding="utf-8"))
    bad = [s for s in _strings(data) if "lovart" in s.lower()]
    assert not bad, bad
