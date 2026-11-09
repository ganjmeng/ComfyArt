"""#704/#707 tip L/R SoT pins. Static paths only. No provider, no image generation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "docs/qa/704/tip-lr/MANIFEST.json").read_text())

VOID_QWEN = {
    "704-lr/pose-fission/fixed-input-v1/RIGHT.png",
    "704-lr/before-after/fixed-input-v1/RIGHT.png",
    "704-lr/game-art/fixed-input-v1/RIGHT.png",
}
POSTERS = {
    "docs/design/640/78/gold/game-art/cover.webp",
    "643/wash/game-art/cover.webp",
}


def test_four_skills_map_to_locked_sot_and_voids_stay_discarded():
    skills = MANIFEST["skills"]
    assert set(skills) == {"pose-fission", "before-after", "game-art", "linkedin-banner"}
    discarded = {item["path"] for item in MANIFEST["discarded"]}
    assert VOID_QWEN <= discarded
    assert POSTERS <= discarded
    assert "643/wash/before-after/cover.webp" in discarded
    assert "docs/design/643/lr/new19/before-after-lr.webp" in discarded

    pose = skills["pose-fission"]["tip_right"]
    assert pose[:5] == [
        "docs/qa/posepro/pro_01.jpg",
        "docs/qa/posepro/pro_02.jpg",
        "docs/qa/posepro/pro_03.jpg",
        "docs/qa/posepro/pro_04.jpg",
        "docs/qa/posepro/compare_posepro.jpg",
    ]
    assert "docs/design/640/78/gold/pose-fission/cover.webp" in pose
    assert [p for p in pose if p.startswith("643/wash/pose-fission/examples/")] == [
        "643/wash/pose-fission/examples/01.webp",
        "643/wash/pose-fission/examples/02.webp",
        "643/wash/pose-fission/examples/03.webp",
        "643/wash/pose-fission/examples/04.webp",
    ]
    assert skills["before-after"]["tip_right"] == [
        "docs/design/640/78/gold/before-after/cover.webp"
    ]
    assert skills["game-art"]["tip_right"] == ["643/wash/game-art/examples/01.webp"]
    assert skills["linkedin-banner"]["tip_right"] == [
        "704-lr/linkedin-banner/fixed-input-v1/RIGHT.png",
        "704-lr/linkedin-banner/fixed-input-v1/design-LR.png",
    ]
    assert "805/reuse/linkedin-banner/featured.png" not in skills["linkedin-banner"]["tip_right"]

    for skill, spec in skills.items():
        assert not (set(spec["tip_right"]) & discarded), skill
        for path in spec["tip_right"]:
            file = ROOT / path
            assert file.is_file(), path
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            assert spec["sha256"][path] == digest
