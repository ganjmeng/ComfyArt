"""#642 Phase3-S3: NEW19 full copy + dialog contract (scaffold).
Media wash stays #643. Skill Creator stays #650. $0 static reads; no network."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
DIALOG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
NOTES = (ROOT / "docs/design/642/78/NOTES.md").read_text()

PHASE3_NEW = [
    "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website",
    "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging",
    "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
    "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
]
DROPPED_MUST_ABSENT = [
    "app-listing-kit", "ip-logo", "magazine-postcard", "talking-collage",
    "anime-official-site", "cinematic-snapshot", "zhixian-poster", "cartoon-ip-extend",
    "culture-creative", "new-chinese-mobile", "portfolio-site",
]


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _instructions(entry: str) -> str:
    m = re.search(r"instructions: ((?:'([^']*)')|(?:`([^`]*)`))", entry)
    assert m, entry[:80]
    return m.group(2) if m.group(2) is not None else m.group(3)


def test_notes_and_s3_marker():
    assert "#642" in NOTES and "Phase3-S3" in NOTES
    assert "#643" in NOTES and "#650" in NOTES
    assert "#642" in SKILLS_TS and "Phase3-S3" in SKILLS_TS


def test_new19_present_production_copy_dialog_inputs():
    entries = _entries()
    for sid in PHASE3_NEW:
        e = entries[sid]
        instr = _instructions(e)
        low = instr.lower()
        assert "you are a production" in low, sid
        assert "lovart" not in low, sid
        assert "demo" not in low, sid
        assert "inputs:" in e, sid
        # #642 field parity: gold dialogs are Upload Files + Additional Details only
        assert "inputs: NEARMISS_INPUTS" in e, sid
        assert "presetChips" not in e, sid
        assert "presets:" in e, sid
        assert len(re.findall(r"\bP\('", e)) >= 2, sid
        # #643 cover pins; batch1 examples wired, featured stays empty; no video
        BATCH1_EX = {
            "taobao-product", "before-after", "product-website", "linkedin-banner", "clothing-swap",
        }
        # #643 per-slot PRs: any slot wired via ex643 (own pin) is held to the batch1 rules
        if f"examples: ex643('{sid}'" in e:
            BATCH1_EX = BATCH1_EX | {sid}
        head = e.split("inputs:", 1)[0]
        if sid == "animated-poster":
            assert "cover: pinned('805/reuse/animated-poster', 'a6beae7242511404f6f295265f64d6b7ef00f49b', 'cover.webp')" in head, sid
        else:
            assert f"cover: cover643('{sid}')" in head, sid
        if sid == "studio-model":
            # #805: hover mp4 is pinned to the media commit. Cover, examples, and featured stay.
            assert "video: pinned('805/reuse/studio-model', '44a5caa051ad8c4bd51152afba8ef853e9c77fd8', 'cover.mp4')" in head, sid
        else:
            assert "video:" not in head, sid
        reuse_featured = {
            "clothing-swap": "featured: [pinned('643/wash/clothing-swap/examples', WASH_643, '02.webp')]",
            "product-website": "featured: [pinned('643/wash/product-website/examples', WASH_643, '02.webp')]",
            "premium-website": "featured: [pinned('643/wash/premium-website/examples', '4ccecac30c1cdf3e79826de5614edc5514e150a4', '07.webp')]",
            "restaurant-website": "featured: [pinned('643/wash/restaurant-website/examples', '9ca6d4ee7eb6488bb2c430affa86cfae75613485', '07.webp')]",
            "product-to-packaging": "featured: [pinned('643/wash/product-to-packaging/examples', '6b1cfa37e4eafc72841e70a26909750c2ff44399', '02.webp')]",
            "live-promo-decor": "featured: [pinned('805/reuse/live-promo-decor', 'e1eb48ba0d2d6511264725c29bd2beebd61816aa', 'featured.webp')]",
            "linkedin-banner": "featured: [pinned('805/reuse/linkedin-banner', 'b6e408ace4835f14282a32d4e19c79e143cb4f53', 'featured.png')]",
            "ai-model": "featured: [pinned('805/reuse/ai-model', '7fbb71bdce30a57f35c367bc949981c00fb2fc10', 'featured.png')]",
            "portrait-studio": "featured: [pinned('805/reuse/portrait-studio', '9af921cda0daa221b75250e5d4c96e39c261a481', 'featured.png')]",
            "youtube-channel-banner": "featured: [pinned('805/reuse/youtube-channel-banner', '9af921cda0daa221b75250e5d4c96e39c261a481', 'featured.png')]",
            "creator-identity": "featured: [pinned('805/reuse/creator-identity', 'a9865d28d584068861020b7eda74ddd6e4daab75', 'featured.png')]",
            "logo-animation": "featured: [pinned('805/reuse/logo-animation', 'a9865d28d584068861020b7eda74ddd6e4daab75', 'featured.png')]",
        }
        if sid in reuse_featured:
            assert reuse_featured[sid] in e, sid
        else:
            assert "featured: []" in e, sid
        if sid in BATCH1_EX:
            assert f"examples: ex643('{sid}'" in e, sid
            assert "examples: []" not in e, sid
        else:
            assert "examples: []" in e, sid


def test_no_dropped_ids_no_skill_creator_slot():
    ids = set(_entries())
    for d in DROPPED_MUST_ABSENT:
        assert d not in ids, d
    assert "skill-creator" not in ids
    assert "custom-workflow" not in ids  # removed: no Lovart card


def test_dialog_shell_hooks_shared():
    for tid in (
        'data-testid="skill-run-modal"',
        'data-testid="skill-run-dialog"',
        'data-testid="skill-run-head"',
        'data-testid="skill-run-go"',
        'data-testid="skill-run-field-error"',
    ):
        assert tid in DIALOG
    assert "missingInputs" in DIALOG and "skillRunParams" in DIALOG


def test_no_lovart_string_under_src_skills_dialog():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
    assert "Lovart" not in DIALOG and "lovart" not in DIALOG


def test_gold_status_stubs_exist():
    for sid in PHASE3_NEW:
        p = ROOT / f"docs/design/642/78/gold/{sid}/STATUS.txt"
        assert p.is_file(), sid
        assert f"id={sid}" in p.read_text()
