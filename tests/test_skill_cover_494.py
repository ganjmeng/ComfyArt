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
    assert covers["logo-material-explorer"] == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/58f1e3e9ebe225e61363f0e7688149c0c6a49813/wash-lm/logo-material.webp"  # WASH_LM r2 (#797; was b72f119a #790)
    assert covers["mobile-app-visual-design"] == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/4ef9ce65c6aef5afa6490c3835b80a6f925382c6/wash-mu/mobile-ui.webp"  # SAELIN rewash
    assert covers["web-product-visual-design"] == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/2438e1d8245b720d560d72a3b659551af0e95db9/wash-wp/web-product.webp"  # WASH_WP (#794/#795; was ca326aed)
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
        "motion-poster-generator": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/ff874a61fa77c9f6e25fe0c6a6a4e116d0378d26/806/wash/motion.webp",  # #806 triptych wash
        "interior-architectural-visualization": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/5c954dbcefb8bd50edef69688b303122debb4ffb/687/wash/interior/cover.webp",
    }
    assert {k: covers[k] for k in washed} == expected
    # #643 (#659) thumbnail true wash re-pinned cover to WASH_643
    assert covers["cover-design-director"] == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/15e9bdad271dc2cb0ac1a1c8621927c161ca9299/643/wash/thumbnail/cover.webp"
    # #812 D-group wash covers
    import re as _re
    _w812 = _re.search(r"const WASH_812 = '([0-9a-f]{40})'", (ROOT / "src/skills.ts").read_text())
    assert _w812, "WASH_812 pin missing"
    w812 = _w812.group(1)
    for sid in ("yingzao", "crt-interface", "crayon-sketch", "fabric-collage"):
        assert covers[sid] == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{w812}/812/wash/{sid}/cover.webp", sid
    # multi-angle re-washed @ 959b1f75 (#975/#984; was covers-v4 @ WASH_594). meta/marketing covers are cover687 (#687).
    w687 = "5c954dbcefb8bd50edef69688b303122debb4ffb"
    phase1_new = {
        "universal-multi-angle-grid": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/959b1f75b5c9b46eece733592302df939869530a/975/wash/multi-angle/multi-angle.webp",  # #975 wash cover (#984)
        "meta-ads-creative-director": f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{w687}/687/wash/meta-ads/cover.webp",
        "marketing-campaign-generator": f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{w687}/687/wash/marketing-campaign/cover.webp",
    }
    assert {k: covers[k] for k in phase1_new} == phase1_new


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
    assert vids.pop("logo-material-explorer") == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/58f1e3e9ebe225e61363f0e7688149c0c6a49813/wash-lm/logo-material/hero.mp4"  # WASH_LM hero (#797)
    assert vids.pop("mobile-app-visual-design") == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/4ef9ce65c6aef5afa6490c3835b80a6f925382c6/wash-mu/mobile-ui/hero.mp4"  # SAELIN hero
    assert vids.pop("web-product-visual-design") == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/2438e1d8245b720d560d72a3b659551af0e95db9/wash-wp/web-product/hero.mp4"  # WASH_WP hero (#794)
    w687 = "5c954dbcefb8bd50edef69688b303122debb4ffb"
    assert vids.pop("universal-multi-angle-grid") == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin623}/594/wash/videos/{asset_dir('universal-multi-angle-grid')}.mp4"  # video594
    assert vids.pop("meta-ads-creative-director") == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{w687}/687/wash/meta-ads/cover.mp4"  # video687 (#687; was video594)
    assert vids.pop("marketing-campaign-generator") == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{w687}/687/wash/marketing-campaign/cover.mp4"  # video687 (#687; was video594)
    assert vids.pop("motion-poster-generator") == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/ff874a61fa77c9f6e25fe0c6a6a4e116d0378d26/806/wash/motion.mp4"  # #806 triptych hover
    assert vids.pop("rednote-cover-maker") == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{w687}/687/wash/social/cover.mp4"  # video687 (#687)
    assert vids.pop("interior-architectural-visualization") == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{w687}/687/wash/interior/cover.mp4"  # video687 (#687)
    assert vids.pop("banner-design-director") == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/e9c0f21959787a9c7401fa95927db3e3e6931bcd/778/wash/banner/examples/01.mp4"  # #778 hover
    pin637 = "2109c085aa74c617cd34517f99626f357062c81c"
    # #637: flash-cut + commerce get single-video example.mp4 as skill.video; other phase2 still null
    for sid in ("flash-cut-video", "commerce-strategist"):
        assert vids.pop(sid) == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin637}/637/wash/{sid}/example.mp4"
    phase2_null = ("style-transfer", "person-swap", "lifestyle-scene",
              "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
              "yingzao", "crt-interface", "crayon-sketch", "fabric-collage")
    for sid in phase2_null:
        assert vids.pop(sid) is None  # C/D + still-only B remain null
    # #805: studio-model + animated-poster hovers are wash-first-frame remakes pinned to their media commits.
    assert vids.pop("studio-model") == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/44a5caa051ad8c4bd51152afba8ef853e9c77fd8/805/reuse/studio-model/cover.mp4"
    assert vids.pop("animated-poster") == "https://raw.githubusercontent.com/ganjmeng/ComfyArt/359b05ded3e5649acb69cf8aab33b13db454546b/805/reuse/animated-poster/cover.mp4"
    hover805 = "b2ec2a5c7aeb294257087216057de4bb4105d944"
    hover_slots = (
        "before-after", "taobao-product", "creator-identity", "youtube-channel-banner",
        "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website",
    )
    for sid in hover_slots:
        assert vids.pop(sid) == f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{hover805}/805/reuse/{sid}/cover.mp4"  # #805 hover
    phase3_null = (
        "anim-2d", "product-website", "ai-model", "product-to-packaging",
        "game-art", "portrait-studio", "premium-website", "pose-fission",
        "clothing-swap",
    )
    for sid in phase3_null:
        assert vids.pop(sid) is None
    assert len(vids) == 6  # shared 494 clip; motion #806, banner #778, social/interior #687 left it
    assert vids == {
        k: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{tip}/494/wash/videos/{asset_dir(k)}.mp4"
        for k in vids
    }
    assert len(set(vids.values())) == 6


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
    pin569 = "bd043d4cff5019fc4117b5b2f3a33ae437015a28"
    # #806: each template plays its own clip (poster ~4:3, first-to-last 9:16). Drop either URL → red.
    assert got["motionPresetVideos"] == [
        f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin569}/569/wash/motion/templates/01-poster-animation.mp4",
        f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{pin569}/569/wash/motion/templates/02-first-to-last-frame-animation.mp4",
    ]
    assert all(u.endswith(".mp4") for u in got["motionPresetVideos"])
    assert got["hoverCalls"] == ["play", "pause"] and got["hoverSeek"] == 0
