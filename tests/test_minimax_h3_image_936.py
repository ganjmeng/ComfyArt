"""#936: upstream 1167e454 MiniMax H3 Image, as WaveSpeed picker rows. No provider calls."""
from __future__ import annotations

import json
from pathlib import Path

from ComfyArt.api import wavespeed

T2I = "minimax/h3-image/text-to-image"
EDIT = "minimax/h3-image/edit"
OPEN_WEIGHTS = (
    "wavespeed-ai/minimax-h3-image/text-to-image",
    "wavespeed-ai/minimax-h3-image/edit",
    "wavespeed-ai/minimax-h3-image/text-to-image-lora",
    "wavespeed-ai/minimax-h3-image/edit-lora",
    "wavespeed-ai/minimax-h3/text-to-image",
    "wavespeed-ai/minimax-h3/image-edit",
)
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "wavespeed_catalog_subset.json").read_text())
RATIOS = ["1:1", "1:2", "2:1", "1:3", "3:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "9:21", "21:9"]


def _props(mid: str) -> dict:
    return FIXTURE[mid]["api_schema"]["api_schemas"][0]["request_schema"]["properties"]


def test_h3_image_is_curated_more_not_default():
    cfg = wavespeed.load_config()["features"]
    for feature, mid in (("text_to_image", T2I), ("image_edit", EDIT)):
        curated = wavespeed.load_curated()[feature]
        ids = [m["id"] for m in cfg[feature]["models"]]
        assert mid in curated["more"]
        assert mid not in curated["models"]
        assert mid in ids
        assert curated["default"] != mid
        assert cfg[feature]["default"] != mid
        assert mid not in cfg[feature]["recommended"]
        entry = next(m for m in cfg[feature]["models"] if m["id"] == mid)
        assert entry.get("local") == "MiniMax H3 Image"
    for other in OPEN_WEIGHTS:
        assert other not in [m["id"] for m in cfg["text_to_image"]["models"]]
        assert other not in [m["id"] for m in cfg["image_edit"]["models"]]


def test_h3_image_display_does_not_steal_the_video_row():
    d = wavespeed.display_of(T2I)
    assert d is not None and d["name"] == "MiniMax H3 Image"
    assert d["blurb"]["zh"] == "6 步出图，2K 下细节丰富，可带多张参考图"
    assert d["blurb"]["en"] == "6-step generation with dense detail at 2K, takes several reference images"
    assert wavespeed.display_of(EDIT)["name"] == "MiniMax H3 Image"
    assert wavespeed.vendor_of(T2I) == "MiniMax"
    video = wavespeed.display_of("wavespeed-ai/minimax-h3/text-to-video")
    assert video is not None and video["name"] == "MiniMax-H3"


def test_h3_image_fixture_matches_public_schema():
    t2i, edit = _props(T2I), _props(EDIT)
    assert t2i["prompt"] == {}
    assert t2i["resolution"]["enum"] == ["1k", "2k", "4k"]
    assert t2i["resolution"]["default"] == "1k"
    assert t2i["aspect_ratio"]["enum"] == RATIOS
    assert t2i["aspect_ratio"]["default"] == "1:1"
    assert t2i["output_format"]["enum"] == ["png", "jpeg", "webp"]
    assert "images" not in t2i and "seed" not in t2i and "loras" not in t2i
    assert edit["images"]["maxItems"] == 16
    assert "seed" not in edit and "loras" not in edit
    assert FIXTURE[T2I]["base_price"] == 0.03
    assert FIXTURE[EDIT]["base_price"] == 0.038
    caps = wavespeed._caps(wavespeed._schema(FIXTURE[EDIT]))
    assert caps["max_images"] == 16
    assert wavespeed._caps(wavespeed._schema(FIXTURE[T2I])).get("max_images") is None


async def test_h3_image_payload_is_one_image_and_keeps_sixteen_refs():
    t2i_schema = wavespeed._schema(FIXTURE[T2I])
    payload = await wavespeed.build_payload(None, t2i_schema, {
        "prompt": "a red fox",
        "width": 2048,
        "height": 2048,
        "resolution": "2K",
    }, T2I)
    assert payload["prompt"] == "a red fox"
    assert payload["resolution"] == "2k"
    assert payload["aspect_ratio"] == "1:1"
    assert "num_images" not in payload and "images" not in payload and "seed" not in payload

    images = [f"https://example.test/{i}.png" for i in range(17)]
    edit = await wavespeed.build_payload(None, wavespeed._schema(FIXTURE[EDIT]), {
        "prompt": "keep the face",
        "images": images,
        "width": 1024,
        "height": 1024,
        "resolution": "1K",
    }, EDIT)
    assert edit["resolution"] == "1k"
    assert edit["images"] == images[:16]


def test_no_local_h3_image_workflow_or_weights():
    assert not (ROOT / "workflows/minimax-h3-image-t2i.api.json").exists()
    blob = "\n".join((ROOT / p).read_text(errors="ignore") for p in (
        "api/wavespeed_models.json",
        "api/curated_models.json",
        "src/models.ts",
        "src/generate.ts",
    ))
    for needle in (
        "minimax_h3_image_pruned_int8_convrot",
        "qwen3vl_32b_minimax_h3",
        "minimax_h3_image_vae_fp16",
        "minimax-h3-image-t2i.api.json",
        "MiniMaxH3ImageConditioning",
    ):
        assert needle not in blob


def test_h3_image_dropdown_only_not_auto_or_skill_pin():
    auto_text = (ROOT / "api/auto_models.json").read_text(encoding="utf-8")
    skills_text = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
    for needle in (T2I, EDIT, "h3-image", "MiniMax H3 Image"):
        assert needle not in auto_text
        assert needle not in skills_text
    pkg = json.loads((ROOT / "package.json").read_text())
    py = (ROOT / "pyproject.toml").read_text()
    assert pkg["version"] == "1.0.1"
    assert 'version = "1.0.1"' in py


def test_picker_copy_is_in_locales_and_docs():
    en = json.loads((ROOT / "src/locales/en.json").read_text())
    zh = json.loads((ROOT / "src/locales/zh.json").read_text())
    assert en["models.minimaxH3Image"].startswith("6-step generation")
    assert zh["models.minimaxH3Image"].startswith("6 步出图")
    for path in ("docs-site/guides/generate.mdx", "README.md"):
        text = (ROOT / path).read_text()
        assert T2I in text and EDIT in text and "16" in text
    for path in ("docs-site/zh/guides/generate.mdx", "README.zh.md"):
        text = (ROOT / path).read_text()
        assert T2I in text and "16" in text
