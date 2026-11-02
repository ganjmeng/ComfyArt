"""#641 Phase3-S2: deepen upgrade `thumbnail` for YouTube 16:9 CTR covers.
PRODUCT-LOCK-PHASE3 thumbnail row. No new skill id. $0 static reads; no network."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
EN = (ROOT / "src/locales/en.json").read_text()


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _instructions(entry: str) -> str:
    m = re.search(r"instructions: ((?:'([^']*)')|(?:`([^`]*)`))", entry)
    assert m, entry[:80]
    return m.group(2) if m.group(2) is not None else m.group(3)


def test_no_youtube_thumbnail_id_and_thumbnail_present():
    ids = list(_entries())
    assert "thumbnail" in ids
    assert "youtube-thumbnail" not in ids
    assert "youtube_thumbnail" not in ids
    assert "#641" in SKILLS_TS and "WASH_641" in SKILLS_TS and "cover641" in SKILLS_TS


def test_thumbnail_yt_presets_at_least_two():
    e = _entries()["thumbnail"]
    presets = re.findall(r"\bP\('([^']+)',\s*'([^']*)',\s*'([^']*)'", e)
    assert len(presets) >= 2, presets
    ids = {p[0] for p in presets}
    ens = {p[2] for p in presets}
    blob = " ".join(ids | ens).lower()
    assert "yt" in blob or "youtube" in blob or "face" in blob or "type" in blob or "contrast" in blob, blob
    assert any("16:9" in p or "youtube" in p.lower() or "thumb" in p.lower() for p in re.findall(r"Style: ([^']*)", e)), e
    body = e.split("presets:", 1)[1].split("inputs:", 1)[0]
    assert len(re.findall(r"Style: ", body)) >= 2
    assert "16:9" in body


def test_thumbnail_instructions_yt_ctr_triad():
    instr = _instructions(_entries()["thumbnail"])
    low = instr.lower()
    assert "you are a production" in low
    assert "youtube" in low and "16:9" in low
    assert ("expressive" in low) or ("face" in low) or ("reaction" in low)
    assert ("three-word" in low) or ("three word" in low) or ("3-word" in low) or ("three punchy" in low)
    assert "contrast" in low
    assert r"\n1)" in instr and r"\n5)" in instr
    assert "lovart" not in low


def test_thumbnail_inputs_media_and_no_effect():
    e = _entries()["thumbnail"]
    assert "titleCopy" in e
    assert "inputs: EFFECT_INPUTS" not in e
    assert "cover: cover641('thumbnail')" in e
    assert "feat641('thumbnail'" in e
    assert "ex641('thumbnail'" in e
    assert "video: video('thumbnail')" in e
    assert "examples: [video('thumbnail'), ...ex641(" in e
    assert "quickStartCover: quickStartCover('thumbnail')" in e


def test_dialog_to_agent_path_still_wired():
    dlg = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
    assert 'data-testid="skill-run-go"' in dlg
    assert "skillRunParams" in dlg and "onStart" in dlg
    assert "mode: 'agent'" in SKILLS_TS
    assert "inputs:" in _entries()["thumbnail"]


def test_no_lovart_string_under_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS


def test_locales_desc_mentions_youtube():
    assert "YouTube" in ZH or "youtube" in ZH.lower()
    assert "YouTube" in EN
    assert "skills.desc.thumbnail" in ZH and "skills.desc.thumbnail" in EN
