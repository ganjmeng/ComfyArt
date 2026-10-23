"""#202 LoRA on WaveSpeed: URL + weight -> the model's `loras` field, quoted with it (quote == charge), gated on the
schema, bad URLs rejected with a localized kind, saved list persisted. Mocks only: no network, no charge."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_wavespeed import MODELS, T2I, uncurated, wavespeed, ws  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parents[1]
HF = "https://huggingface.co/acme/style-lora/resolve/main/ink_style.safetensors"
HF_BLOB = "https://huggingface.co/acme/style-lora/blob/main/ink_style.safetensors"
CIVITAI = "https://civitai.com/api/download/models/123456"
CIVITAI_PAGE = "https://civitai.com/models/9876/some-style?modelVersionId=123456"
LORAS = {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {"path": {}, "scale": {}}}}


def per_lora(inputs: dict) -> float:
    # mock price API: $0.02 base + $0.005 per LoRA it is asked about
    return round(0.02 + 0.005 * len(inputs.get("loras") or []), 4)


@pytest.fixture
def lora_model(ws, monkeypatch):
    schema = next(m for m in MODELS if m["model_id"] == T2I)["api_schema"]["api_schemas"][0]["request_schema"]
    monkeypatch.setitem(schema, "properties", {**schema["properties"], "loras": LORAS})
    ws["prices"][T2I] = per_lora
    return ws


@pytest.mark.parametrize("url,want", [
    (HF, HF), (HF_BLOB, HF), ("https://hf.co/acme/x/resolve/main/a.safetensors", "https://hf.co/acme/x/resolve/main/a.safetensors"),
    (CIVITAI, CIVITAI), (CIVITAI_PAGE, CIVITAI), (f"  {CIVITAI}?type=Model ", f"{CIVITAI}?type=Model"),
    ("http://huggingface.co/acme/x/resolve/main/a.safetensors", None), ("https://huggingface.co/acme/x", None),
    ("https://huggingface.co/acme/x/resolve/main/a.ckpt", None), ("https://evil.example/a.safetensors", None),
    ("https://civitai.com/models/9876", None), ("", None), ("javascript:alert(1)", None),
])
def test_url_validation(url, want):
    assert wavespeed.lora_url(url) == want


def test_payload_shape_and_scale():
    props = {"prompt": {}, "loras": LORAS}
    out = wavespeed.lora_payload(props, {"loras": [{"name": HF, "strength": 100}, {"name": CIVITAI_PAGE, "strength": 35}, {"name": HF_BLOB.replace("ink", "b"), "strength": 900}]})
    assert out == [{"path": HF, "scale": 1.0}, {"path": CIVITAI, "scale": 0.35}, {"path": HF.replace("ink", "b"), "scale": 4.0}]
    assert wavespeed.lora_payload(props, {}) == [] and wavespeed.lora_payload({"prompt": {}}, {"loras": []}) == []


@pytest.mark.parametrize("props,loras,kind", [
    ({"prompt": {}}, [{"name": HF, "strength": 100}], "loraUnsupported"),
    ({"prompt": {}, "loras": LORAS}, [{"name": "https://evil.example/a.safetensors", "strength": 100}], "loraUrl"),
    ({"prompt": {}, "loras": LORAS}, [{"name": HF, "strength": 100}] * 4, "loraTooMany"),
])
def test_never_silently_ignored(props, loras, kind):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        wavespeed.lora_payload(props, {"loras": loras})
    assert e.value.kind == kind and e.value.status == 400


def test_catalog_exposes_loras():
    caps = wavespeed._caps({"properties": {"prompt": {}, "loras": LORAS}})
    assert "loras" in caps["inputs"] and caps["max_loras"] == 3
    assert "max_loras" not in wavespeed._caps({"properties": {"prompt": {}}})


async def test_submit_sends_loras_and_quote_equals_charge(lora_model):
    job = {"feature": "text_to_image", "model": T2I, "prompt": "ink cat", "width": 1024, "height": 1024,
           "loras": [{"name": HF_BLOB, "strength": 80}, {"name": CIVITAI, "strength": 100}]}
    est = await wavespeed.estimate(dict(job))
    assert lora_model["quotes"][-1]["inputs"]["loras"] == [{"path": HF, "scale": 0.8}, {"path": CIVITAI, "scale": 1.0}]
    await wavespeed.submit({**job, "confirmed": True})
    _, payload = lora_model["submits"][-1]
    assert payload["loras"] == [{"path": HF, "scale": 0.8}, {"path": CIVITAI, "scale": 1.0}]
    assert est["price"] == per_lora(payload) == 0.03  # the quote prices exactly what is charged
    plain = await wavespeed.estimate({k: v for k, v in job.items() if k != "loras"})
    assert plain["price"] == 0.02


async def test_unsupported_model_and_bad_url_fail_before_any_submit(ws):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "model": T2I, "prompt": "x", "confirmed": True, "loras": [{"name": HF, "strength": 100}]})
    assert e.value.kind == "loraUnsupported" and not ws["submits"]


async def test_bad_url_fails_before_quote(lora_model):
    with pytest.raises(wavespeed.WaveSpeedError) as e:
        await wavespeed.submit({"feature": "text_to_image", "model": T2I, "prompt": "x", "loras": [{"name": "https://x.test/a.safetensors", "strength": 100}]})
    assert e.value.kind == "loraUrl" and not lora_model["submits"] and not lora_model["quotes"]


def test_ui_wiring():
    adv = (ROOT / "src/ui/GenAdvanced.tsx").read_text()
    # greyed with the hint, never hidden; reuses existing classes only (no popup / new component)
    assert "loraSupported(shape)" in adv and "genAdvanced.loraUnsupported" in adv and "{hasLora && (" not in adv
    assert "disabled={!hasLora" in adv and "ca-landing__error" in adv and "wsErr.loraUrl" in adv
    assert "ca-adv__lora" in adv and 'type="range"' in adv and "ca-adv__pick" in adv and "ca-chat__hint" in adv
    assert "Popover" in adv and adv.count("<Popover") == 1 and "Dialog" not in adv
    gen = (ROOT / "src/generate.ts").read_text()
    assert "applyLoras(b.graph, shape)" in gen and "{ ...inputs, loras }" in gen
    assert "inputs: m.inputs" in (ROOT / "src/models.ts").read_text()
    for lang in ("zh", "en"):
        d = json.loads((ROOT / f"src/locales/{lang}.json").read_text())
        for k in ("genAdvanced.loraUnsupported", "genAdvanced.loraUrlHint", "genAdvanced.savedLoras", "wsErr.loraUrl", "wsErr.loraUnsupported", "wsErr.loraTooMany"):
            assert d[k]
    assert json.loads((ROOT / "src/locales/zh.json").read_text())["genAdvanced.loraUnsupported"] == "当前模型不支持 LoRA"


@pytest.mark.skipif(not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")
def test_frontend_validation_gating_persistence(tmp_path):
    out = tmp_path / "lora.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "lora.ts"})
    r = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    assert r["urls"] == [HF, HF, CIVITAI, CIVITAI, None, None, None]
    # same rule as the backend
    assert [wavespeed.lora_url(u) for u in r["inputs"]] == r["urls"]
    assert r["supports"] == {"withLoras": True, "without": False, "auto": False, "missing": False}
    assert r["saved"] == [{"name": CIVITAI, "strength": 60}, {"name": HF, "strength": 100}]
    assert r["reloaded"] == r["saved"] and r["afterForget"] == [{"name": HF, "strength": 100}]
    assert r["labels"] == ["ink_style", "Civitai #123456"]
    assert r["zh"]["loraUrl"].startswith("LoRA 链接无效") and r["en"]["loraUrl"].startswith("Invalid LoRA link")
    assert r["zh"]["loraUnsupported"].startswith("当前模型不支持 LoRA") and r["en"]["loraUnsupported"].startswith("This model doesn't support LoRA")
