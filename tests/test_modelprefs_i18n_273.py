"""#273: ModelPrefs Image/Video tabs must use i18n, not hardcoded English."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "ui" / "ModelPrefs.tsx"


def _locale(name):
    return json.loads((ROOT / "src" / "locales" / f"{name}.json").read_text(encoding="utf-8"))


def test_no_hardcoded_tab_labels():
    src = SRC.read_text(encoding="utf-8")
    assert not re.search(r">\s*(Image|Video)\s*<", src)
    assert "t('modelPrefs.image')" in src
    assert "t('modelPrefs.video')" in src


def test_locale_keys():
    zh, en = _locale("zh"), _locale("en")
    assert zh["modelPrefs.image"] == "图像"
    assert zh["modelPrefs.video"] == "视频"
    assert en["modelPrefs.image"] == "Image"
    assert en["modelPrefs.video"] == "Video"
