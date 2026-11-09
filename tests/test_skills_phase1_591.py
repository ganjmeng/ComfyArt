"""#591 Phase1-S1: hot-set data contract — 9 upgrade + 6 new ids in BUILTIN_SKILLS (cut2), website chip lit.
$0 static reads; no network."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())

PHASE1_UPGRADE = ["brand-identity-director", "packaging-design-director", "poster-differentiated-compiler", "product-tvc-advertisement-generator", "character-sheet-design", "rednote-cover-maker", "motion-poster-generator", "banner-design-director", "cover-design-director"]
PHASE1_NEW = ["universal-multi-angle-grid", "logo-material-explorer", "meta-ads-creative-director", "mobile-app-visual-design", "web-product-visual-design", "marketing-campaign-generator"]
PHASE1 = PHASE1_UPGRADE + PHASE1_NEW
UNTOUCHED = ["interior-architectural-visualization"]  # custom-workflow removed (no Lovart card)
TITLE_KEY = {
    "universal-multi-angle-grid": "skills.multiAngleImageGenerator",
    "logo-material-explorer": "skills.logoMaterialExplorer",
    "meta-ads-creative-director": "skills.metaAdsCreative",
    "mobile-app-visual-design": "skills.mobileAppVisualDesign",
    "web-product-visual-design": "skills.webProductVisualDesign",
    "marketing-campaign-generator": "skills.marketingCampaignGenerator",
}
NEW_CATEGORY = {
    "universal-multi-angle-grid": "ecommerce",
    "logo-material-explorer": "branding",
    "meta-ads-creative-director": "ads",
    "mobile-app-visual-design": "website",
    "web-product-visual-design": "website",
    "marketing-campaign-generator": "ads",
}


_COVER687 = {"meta-ads-creative-director", "marketing-campaign-generator"}


def _cover_needle(sid: str) -> str:
    return "cover: cover687(" if sid in _COVER687 else "cover: cover("


def _feat_needle(sid: str) -> str:
    return "featured: feat687(" if sid in _COVER687 else "featured: feedCovers("


def _video_needle(sid: str) -> str:
    return {
        "universal-multi-angle-grid": "video: video594('universal-multi-angle-grid')",
        "logo-material-explorer": "video: pinned('wash-lm/logo-material', WASH_LM, 'hero.mp4')",  # WASH_LM #797
        "meta-ads-creative-director": "video: video687('meta-ads-creative-director')",  # #687
        "mobile-app-visual-design": "video: pinned('wash-mu/mobile-ui', WASH_MU, 'hero.mp4')",  # #792
        "web-product-visual-design": "video: pinned('wash-wp/web-product', WASH_WP, 'hero.mp4')",  # WASH_WP #794
        "marketing-campaign-generator": "video: video687('marketing-campaign-generator')",  # #687
    }[sid]


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def test_phase1_ids_present_and_untouched_kept():
    ids = list(_entries())
    assert set(PHASE1) <= set(ids)
    assert all(u in ids for u in UNTOUCHED)
    assert len(ids) >= 17
    # #634 Phase2 reclaims the deferred .art ids — no longer voided


def test_new_skills_cut2_skeleton_and_website_categories():
    entries = _entries()
    for sid, cat in NEW_CATEGORY.items():
        e = entries[sid]
        assert f"category: '{cat}'" in e, sid
        assert "instructions:" in e and "inputs:" in e, sid
        assert "name: t(" in e, sid
        # Cover / featured / hover follow the signed wash helper, not a single video594() for every new-6 id.
        head = e.split("inputs:", 1)[0]
        assert _cover_needle(sid) in head, sid
        assert _feat_needle(sid) in head, sid
        assert _video_needle(sid) in head, sid
        assert "quickStartCoverFit: 'contain'" in head, sid
        assert "examples: ex594(" not in head and "ex594" not in head, sid  # #751 HOLD: Final examples come from raw + src/data/wash-748.json (1:1, pendingWash), no hand list


def test_locale_titles_and_descriptions_for_new_ids():
    for sid, key in TITLE_KEY.items():
        assert ZH[key].strip() and EN[key].strip()
        assert "demo" not in ZH[key].lower() and "demo" not in EN[key].lower()
        assert ZH[f"skills.desc.{sid}"] and EN[f"skills.desc.{sid}"]
        assert ZH[f"skills.cat.{sid}"] and EN[f"skills.cat.{sid}"]
    assert ZH[TITLE_KEY["universal-multi-angle-grid"]] == "多角度图像生成器"
    assert EN[TITLE_KEY["universal-multi-angle-grid"]] == "Multi-Angle Image Generator"
    assert EN[TITLE_KEY["mobile-app-visual-design"]] == "Mobile APP Visual Design"
    assert EN[TITLE_KEY["web-product-visual-design"]] == "Web Product Visual Design"


def test_no_lovart_string_in_src_skills():
    # Gold UX is lovart.ai in docs/PR only — never the competitor string inside src.
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
