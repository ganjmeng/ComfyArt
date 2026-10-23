"""A custom workflow that fails the check is never saved, so it never shows in the feature's dropdown (#75)."""
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
    out = tmp_path_factory.mktemp("wf") / "wf.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True, capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_failed_workflow_is_never_listed(result):
    assert result["bad"]["installed"] is False
    assert result["listAfterBad"] == [] and result["files"] == [] and result["configAfterBad"] == {}
    assert result["good"]["installed"] is True and result["listAfterGood"] == ["my-edit.json"]


def test_check_errors_are_localized(result):
    assert result["zh"] == "broken.json 安装失败：模型 acme/my-edit 缺少 @image、@prompt 的对应字段，还需要填写 input_image、instruction、strength"
    assert result["en"].startswith("broken.json failed to install: model acme/my-edit has no field for @image, @prompt")
