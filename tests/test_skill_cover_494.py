"""#494-1: cover fallback (cover → own images[0] → grey + icon) and data-driven chips through the real src/skills.ts.
Harness: tests/js/skill_cover_494.ts (stubs from tests/js/rolldown.config.mjs, no network, $0)."""
from __future__ import annotations

import json
from tests.skill_ids_748 import asset_dir
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m494") / "skill_cover_494.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skill_cover_494.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_no_image_falls_back_to_icon(got):
    assert got["noImage"] is None and got["customNoCover"] is None  # null → grey background + Lucide icon
    assert got["custom"] == {"src": got["builtinCovers"]["interior-architectural-visualization"], "own": "bundled"}  # #581 real cover


def test_own_image_used(got):
    assert got["ownImage"] == {"src": "input/r.png", "own": "userdata"}


def test_builtin_covers(got):
    """#581 washed covers stay pinned; #594 Phase1 new 6 covers-v4 @ WASH_594."""
    covers = got["builtinCovers"]
    washed = ["poster-differentiated-compiler", "rednote-cover-maker", "brand-identity-director", "packaging-design-director", "banner-design-director", "character-sheet-design", "product-tvc-advertisement-generator", "motion-poster-generator", "interior-architectural-visualization"]
    assert covers["logo-material-explorer"] == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/b72f119af80013b2dc6119e94713b8a2354ac6c4/wash-lm/logo-material.webp"  # VELA rewash
    phase1_new = ["universal-multi-angle-grid", "meta-ads-creative-director", "mobile-app-visual-design", "web-product-visual-design", "marketing-campaign-generator"]
    v3, pin = "3c9b87e7eae72164efdd1fe30e00f576144475f4", {
        "banner-design-director": ("778/wash", "79bf01dc6342363348671c368fa1d467706a0e0f"),  # #778 fintech cover
        "product-tvc-advertisement-generator": ("784/wash", "d17ae7c9a27b84ab0f0781bccee100778a9f1e18"),  # #784 BR lip-tube wash
        "brand-identity-director": ("786/wash", "8ab5aa8044d71e9518ae5f054eb2f8c7e77dd127"),  # #786 SOLENNE
        "character-sheet-design": ("788/wash", "1f66faf48e8dbd625b4acf79505adb320586ad14"),
    }
    v4 = "cc76d743d416c3d9a9a6852d811a7a80caf40319"
    assert len(covers) == 49 and "custom-workflow" not in covers  # #640 Phase3-S1 +19 NEW (null covers)
    expected = {
        "poster-differentiated-compiler": f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{v3}/494/covers-v3/poster.webp",
        "rednote-cover-maker": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/5c954dbcefb8bd50edef69688b303122debb4ffb/687/wash/social/cover.webp",
        "brand-identity-director": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/8ab5aa8044d71e9518ae5f054eb2f8c7e77dd127/786/wash/brand.webp",  # #786 SOLENNE
        "packaging-design-director": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/e270088ea1695f5200669649e6e832057e9c8a6a/777/wash/packaging/cover.webp",
        "banner-design-director": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/79bf01dc6342363348671c368fa1d467706a0e0f/778/wash/banner.webp",
        "character-sheet-design": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/1f66faf48e8dbd625b4acf79505adb320586ad14/788/wash/character.webp",
        "product-tvc-advertisement-generator": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/d17ae7c9a27b84ab0f0781bccee100778a9f1e18/784/wash/product.webp",
        "motion-poster-generator": f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{v3}/494/covers-v3/motion.webp",
        "interior-architectural-visualization": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/5c954dbcefb8bd50edef69688b303122debb4ffb/687/wash/interior/cover.webp",
    }
    assert {k: covers[k] for k in washed} == expected
    # #643 (#659) thumbnail true wash re-pinned cover to WASH_643
    assert covers["cover-design-director"] == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/15e9bdad271dc2cb0ac1a1c8621927c161ca9299/643/wash/thumbnail/cover.webp"
    assert {k: covers[k] for k in phase1_new} == {
        k: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{v4}/494/covers-v4/{k}.webp"
        for k in phase1_new
    }


def test_chips_from_data(got):
    assert got["chips"] == ["forYou", "ecommerce", "branding", "social", "website", "ads"]  # #591 website lit
    by = got["byChip"]
    assert len(by["forYou"]) == 49  # #640 Phase3-S1
    # #595: within-chip order follows PHASE1 hot mount (orderBuiltins)
    assert by == {"forYou": by["forYou"],
                  "ecommerce": ["product-tvc-advertisement-generator", "universal-multi-angle-grid", "packaging-design-director", "person-swap", "commerce-strategist", "lifestyle-scene", "promo-ecommerce", "taobao-product", "studio-model", "ai-model", "product-to-packaging", "pose-fission", "live-promo-decor", "clothing-swap"],
                  "branding": ["brand-identity-director", "logo-material-explorer", "style-transfer", "logo-abstract", "creator-identity", "logo-animation"],
                  "social": ["cover-design-director", "rednote-cover-maker", "naive-illustration", "yingzao", "crt-interface", "crayon-sketch", "fabric-collage", "youtube-channel-banner", "portrait-studio", "linkedin-banner"],
                  "website": ["mobile-app-visual-design", "web-product-visual-design", "ppt-visual", "product-website", "premium-website", "restaurant-website"],
                  "ads": ["motion-poster-generator", "meta-ads-creative-director", "poster-differentiated-compiler", "marketing-campaign-generator", "banner-design-director", "flash-cut-video", "photo-split-poster", "before-after", "anim-2d", "game-art", "animated-poster"]}
    assert by["forYou"][:15] == [
        "product-tvc-advertisement-generator", "universal-multi-angle-grid", "brand-identity-director", "character-sheet-design", "logo-material-explorer", "packaging-design-director",
        "motion-poster-generator", "meta-ads-creative-director", "poster-differentiated-compiler", "cover-design-director", "mobile-app-visual-design", "rednote-cover-maker",
        "marketing-campaign-generator", "web-product-visual-design", "banner-design-director",
    ]
    for sid in ("character-sheet-design", "interior-architectural-visualization"):
        assert all(sid not in v for k, v in by.items() if k != "forYou")


def test_builtin_videos_unique(got):
    """#529/#623 — 10 upgrade9 @ WASH_VIDEO + 6 new6 @ WASH_623; custom-workflow card removed."""
    vids = got["builtinVideos"]
    assert "custom-workflow" not in vids
    tip = "1bbb3f208f18b26ef95c8d9f16efeea111c43ac7"
    pin623 = "d03ea7938877d084c201a94ef51f943dd0e061b9"
    assert vids.pop("logo-material-explorer") == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/b72f119af80013b2dc6119e94713b8a2354ac6c4/wash-lm/logo-material/hero.mp4"  # VELA hero
    new6 = ("universal-multi-angle-grid", "meta-ads-creative-director", "mobile-app-visual-design", "web-product-visual-design", "marketing-campaign-generator")
    for sid in new6:
        assert vids.pop(sid) == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin623}/594/wash/videos/{asset_dir(sid)}.mp4"
    pin637 = "2109c085aa74c617cd34517f99626f357062c81c"
    # #637: flash-cut + commerce get single-video example.mp4 as skill.video; other phase2 still null
    for sid in ("flash-cut-video", "commerce-strategist"):
        assert vids.pop(sid) == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin637}/637/wash/{sid}/example.mp4"
    phase2_null = ("style-transfer", "person-swap", "lifestyle-scene",
              "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
              "yingzao", "crt-interface", "crayon-sketch", "fabric-collage")
    for sid in phase2_null:
        assert vids.pop(sid) is None  # C/D + still-only B remain null
    phase3_null = (
        "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website",
        "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging",
        "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
        "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
    )
    for sid in phase3_null:
        assert vids.pop(sid) is None  # #640 Phase3-S1 empty video until S4
    assert len(vids) == 10
    assert vids == {
        k: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/{asset_dir(k)}.mp4"
        for k in vids
    }
    assert len(set(vids.values())) == 10


def test_video_field_data_driven(got):
    """#529 mutation: drop/omit video → skillVideo null (badge must not invent video)."""
    assert got["noVideo"] is None and got["customVideo"] is None
    assert got["videoMutated"] is None


def test_575_video_contract(got):
    """#575/#623/#622 — detector, hover play/pause+seek0, new6 pending empty (wired), thumbnail/banner lead mp4, motion preset.video wash-v1."""
    assert got["isVideo"] == {"mp4": True, "webm": True, "mov": True, "webp": False, "empty": False, "undef": False}
    assert got["pendingNew6"] == []  # #623 wired → empty pending
    tip = "1bbb3f208f18b26ef95c8d9f16efeea111c43ac7"
    assert got["thumbEx"][0] == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/thumbnail.mp4"
    assert got["bannerEx"][0] == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/e9c0f21959787a9c7401fa95927db3e3e6931bcd/778/wash/banner/examples/01.mp4"  # #778 ex01 fintech wash
    assert len(got["thumbEx"]) == 1 and len(got["bannerEx"]) == 1  # #748 raw highlights: 1 video each (convert)
    motion_tip = "5a8d22ed88f732d38f8709a2c0740f074a400a89"
    assert got["motionPresetVideos"] == [None, None]  # #751 HOLD: skill-level video no longer shared onto template cards (each card keeps its OWN cover)  # #748 raw: 2 templates; our wash video is the placeholder (WASH-TODO)
    # mutation: drop preset.video → null (red if wired URLs vanish)
    assert not any(got["motionPresetVideos"])  # #751 HOLD: template cards carry no shared video
    assert got["hoverCalls"] == ["play", "pause"] and got["hoverSeek"] == 0
