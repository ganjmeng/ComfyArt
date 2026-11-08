"""Dialog left: cover main-preview when examples/presetTiles empty; NEW19 examples stay []."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
SKILLS = (ROOT / "src/skills.ts").read_text()

NEW19 = [
    "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website",
    "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging",
    "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
    "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
]

NEW19_WASHED_643 = {"taobao-product": [1, 2, 3, 4, 5, 6, 7, 8], "before-after": [1, 2, 3, 4, 5, 6, 7, 8],
                    "product-website": [1, 2, 3], "linkedin-banner": [1], "clothing-swap": [1, 2],
                    # #677/#682/#674 per-skill wash (pin sha as 3rd arg)
                    "anim-2d": [1, 2, 3], "creator-identity": [1], "portrait-studio": [1, 2, 3, 4, 5, 6],
                    "youtube-channel-banner": [1, 2, 3, 4, 5, 6, 7, 8, 9],  # #678
                    "animated-poster": [1, 2],  # #643 per-slot PR
                    "premium-website": [1, 2, 3, 4, 5, 6, 7],  # #643 per-slot PR
                    "studio-model": [1, 2],  # #643 per-slot PR
                    "restaurant-website": [1, 2, 3, 4, 5, 6, 7],  # #643 per-slot PR
                    "product-to-packaging": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],  # #643 per-slot PR
                    "game-art": list(range(1, 21)),  # #643 per-slot PR
                    "logo-animation": [1, 2, 3, 4],  # #643 per-slot PR
                    "live-promo-decor": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],  # #643 per-slot PR
                    "ai-model": [1, 2, 3, 4, 5, 6],  # #643 per-slot PR
                    "pose-fission": [1, 2, 3, 4]}  # #643 per-slot PR


def test_cover_main_preview_hooks():
    assert "skillCover" in DLG
    assert 'data-testid="skill-run-cover-preview"' in DLG
    assert 'data-testid="skill-run-cover-stage"' in DLG
    assert 'data-testid="skill-run-cover-img"' in DLG
    assert 'data-left="cover"' in DLG
    # Dedicated hero — not SkillExamples with a fake single item
    assert "SkillExamples examples={[coverSrc" not in DLG
    assert "examples={[coverSrc" not in DLG
    # Still null when neither cover nor examples/tiles
    assert "if (!coverSrc) return null" in DLG


def test_new19_examples_still_empty_covers_pinned():
    a = SKILLS.index("export const BUILTIN_SKILLS")
    block = SKILLS[a:next(i for i in (SKILLS.find("\n])\n", a), SKILLS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    entries = {p.split("'", 1)[0]: p for p in parts}
    for sid in NEW19:
        e = entries[sid]
        if sid in NEW19_WASHED_643:  # #643 batch1 (#667) true-wash examples landed
            assert re.search(rf"examples: ex643\('{sid}', {re.escape(str(NEW19_WASHED_643[sid]))}(, '[0-9a-f]{{40}}')?\)", e), sid
        else:
            assert "examples: []" in e, sid
        reuse_featured = {
            "clothing-swap": "featured: [pinned('643/wash/clothing-swap/examples', WASH_643, '02.webp')]",
            "product-website": "featured: [pinned('643/wash/product-website/examples', WASH_643, '02.webp')]",
            "premium-website": "featured: [pinned('643/wash/premium-website/examples', '4ccecac30c1cdf3e79826de5614edc5514e150a4', '07.webp')]",
            "restaurant-website": "featured: [pinned('643/wash/restaurant-website/examples', '9ca6d4ee7eb6488bb2c430affa86cfae75613485', '07.webp')]",
            "product-to-packaging": "featured: [pinned('643/wash/product-to-packaging/examples', '6b1cfa37e4eafc72841e70a26909750c2ff44399', '02.webp')]",
            "live-promo-decor": "featured: [pinned('805/reuse/live-promo-decor', 'e1eb48ba0d2d6511264725c29bd2beebd61816aa', 'featured.webp')]",
            "linkedin-banner": "featured: [pinned('805/reuse/linkedin-banner', 'b6e408ace4835f14282a32d4e19c79e143cb4f53', 'featured.png')]",
        }
        if sid in reuse_featured:
            assert reuse_featured[sid] in e, sid
        else:
            assert "featured: []" in e, sid
        head = e.split("inputs:", 1)[0]
        if sid == "animated-poster":
            assert "cover: pinned('805/reuse/animated-poster', 'a6beae7242511404f6f295265f64d6b7ef00f49b', 'cover.webp')" in head, sid
        else:
            assert f"cover: cover643('{sid}')" in head, sid
