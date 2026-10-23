"""#201: negative prompt shown per model schema and sent only to models whose schema has negative_prompt (mocks, no paid calls)."""
import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ComfyArt.api import wavespeed as ws

ROOT = Path(__file__).resolve().parent.parent


def _payload(props, inputs):
    return asyncio.run(ws.build_payload(None, {"properties": props}, inputs))


def test_sent_when_schema_has_negative_prompt():
    p = _payload({"prompt": {}, "negative_prompt": {}}, {"prompt": "cat", "negative_prompt": "  blurry, watermark "})
    assert p == {"prompt": "cat", "negative_prompt": "blurry, watermark"}


def test_dropped_when_schema_lacks_it_or_empty():
    assert "negative_prompt" not in _payload({"prompt": {}}, {"prompt": "cat", "negative_prompt": "blurry"})
    assert "negative_prompt" not in _payload({"prompt": {}, "negative_prompt": {}}, {"prompt": "cat", "negative_prompt": "  "})


def test_catalog_inputs_expose_negative_prompt():
    caps = ws._caps({"properties": {"prompt": {}, "negative_prompt": {}, "enable_sync_mode": {}}})
    assert "negative_prompt" in caps["inputs"]


def test_ui_gates_on_schema_and_request_carries_it():
    adv = (ROOT / "src/ui/GenAdvanced.tsx").read_text()
    assert "hasNegative(model)" in adv and "ca-adv__negative" in adv and "{model.negative &&" not in adv
    gen = (ROOT / "src/generate.ts").read_text()
    assert len(re.findall(r"negative_prompt", gen)) >= 4
    assert "inputs: m.inputs" in (ROOT / "src/models.ts").read_text()


@pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")
def test_has_negative_follows_model_schema(tmp_path):
    out = tmp_path / "neg.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "negative_prompt.ts"})
    r = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert r == {"withNeg": True, "noNeg": False, "video": True, "auto": False, "missing": False}
