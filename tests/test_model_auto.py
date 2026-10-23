"""#95: Auto in the generator's model menu vs a user pick (src/models.ts + src/wavespeed.ts under node, mocked fetch)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("auto") / "auto.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "model_auto.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_auto_hands_choice_to_agent_or_default(result):
    assert result["autoIsCloud"] and result["autoVideo"] and result["autoImageIsImage"]
    assert result["isAuto"] == [True, False]
    assert result["autoNoAgent"] is None  # backend resolve_model -> feature default
    assert result["autoAgent"] == "google/nano-banana-pro/text-to-image"
    assert result["videoAuto"] is None


def test_user_pick_is_used_as_is(result):
    assert result["userPick"] == "openai/gpt-image-2.5-sunburst/text-to-image"
    assert result["videoPick"] == "kwaivgi/kling-v3.0-pro/text-to-video"


def test_per_feature_tabs_and_tiers(result):
    assert list(result["tabs"]) == ["text_to_image", "image_edit", "text_to_video", "image_to_video"]
    assert result["tabs"]["image_edit"] == ["openai/gpt-image-2/edit", "google/nano-banana-pro/edit"]
    assert result["tiers"] == ["low", "medium", "high"]


def test_switching_keeps_supported_and_resets_the_rest(result):
    assert result["adjustKeep"] == {}
    assert result["adjustReset"] == {"ratio": "16:9", "duration": 5, "resolution": "1080p"}
    assert result["adjustTier"] == {"quality": "medium"}
    assert result["adjustAuto"] == {}


def test_extra_refs_capped_to_model_max(result):
    assert result["refCap"] == [3, None, None]


def test_auto_ignores_earlier_manual_pick(result):
    # #95 ruling: panel Auto without an agent -> feature default; never an earlier manual pick
    assert result["autoIgnoresManual"] == {}
    assert result["manualKept"] == {"image_to_video": "x/manual"}


def test_dropdown_follows_backend_picker_order_and_shows_display_name(result):
    assert result["tabs"]["text_to_video"] == ["kwaivgi/kling-v3.0-pro/text-to-video", "bytedance/seedance-2.0/text-to-video"]
    assert result["row"]["label"] == "GPT Image 2" and result["row"]["desc"] in ("English blurb", "中文描述")
