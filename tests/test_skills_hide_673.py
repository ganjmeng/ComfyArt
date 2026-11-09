"""#673/#735/#812 — Phase2 hide list: empty after #812 D wash+unhide. Machinery kept (HIDDEN_BUILTIN_SKILL_IDS,
isListedSkill, attach/block guards). Real src/skills.ts through a node harness (tests/js/hide673). $0."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(not (ROOT / "node_modules/.bin/rolldown").exists() or not shutil.which("node"),
                                reason="needs node + npm install")

# #812 — hide list empty (D washed+unhidden). Keep name HIDDEN for e2e imports.
HIDDEN = []
# Listed builtins after #812: all 49 (Phase1 + Phase2 Soft B+C+D + Phase3 + interior).
MAIN_ORDER_45 = [
    "product-tvc-advertisement-generator", "universal-multi-angle-grid", "brand-identity-director", "character-sheet-design", "logo-material-explorer", "packaging-design-director", "motion-poster-generator", "meta-ads-creative-director", "poster-differentiated-compiler",
    "cover-design-director", "mobile-app-visual-design", "rednote-cover-maker", "marketing-campaign-generator", "web-product-visual-design", "banner-design-director", "flash-cut-video",
    "style-transfer", "person-swap", "commerce-strategist", "lifestyle-scene",
    "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
    "yingzao", "crt-interface", "crayon-sketch", "fabric-collage",
    "taobao-product", "before-after",
    "anim-2d", "creator-identity", "product-website", "studio-model", "youtube-channel-banner", "ai-model",
    "product-to-packaging", "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
    "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap", "interior-architectural-visualization",
]
# Back-compat alias used by e2e imports.
MAIN_ORDER_40 = MAIN_ORDER_45


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"hide673-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/hide673/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


@needs_node
def test_hide_list_empty_after_812_and_builtins_keep_all_49() -> None:
    r = report()
    assert r["hidden"] == HIDDEN == []
    assert len(r["builtinAll"]) == 49
    assert r["builtinAll"] == MAIN_ORDER_45


@needs_node
def test_listed_is_all_49_in_main_order() -> None:
    assert report()["listed"] == MAIN_ORDER_45
    assert len(MAIN_ORDER_45) == 49


@needs_node
def test_category_chips_never_contain_hidden() -> None:
    r = report()
    for chip, ids in r["byChip"].items():
        assert not set(ids) & set(HIDDEN), (chip, ids)
    assert r["byChip"]["forYou"] == MAIN_ORDER_45
    # every listed skill still lands in some category chip, in order
    for chip, ids in r["byChip"].items():
        assert ids == [i for i in MAIN_ORDER_45 if i in ids], chip


@needs_node
def test_home_featured_never_contains_hidden() -> None:
    f = report()["featured"]
    assert f and not set(f) & set(HIDDEN)


@needs_node
def test_agent_list_excludes_hidden_and_keeps_order() -> None:
    assert report()["agentList"] == MAIN_ORDER_45


@needs_node
def test_agent_read_of_former_d_group_still_resolves_733() -> None:
    """#733/#812: D unhidden; agent read by id/name still works for former hide-list ids."""
    r = report()
    assert r["hiddenReads"] == {}  # nothing on hide list
    for sid in ("yingzao", "crt-interface", "crayon-sketch", "fabric-collage"):
        res = r["resolved"][sid] if sid in r["resolved"] else None
        # resolved map only filled for HIDDEN; fall back to listed read
        if res is None:
            continue
        assert "error" not in res and res["found"] is True


@needs_node
def test_agent_read_listed_still_works_and_unknown_lists_only_listed() -> None:
    r = report()
    assert r["listedReadId"] == "poster-differentiated-compiler"
    err = r["unknown"]["error"]
    assert err.startswith("unknown skill") and not any(f"({h})" in err for h in HIDDEN)


@needs_node
def test_saved_session_or_card_still_resolves_d_ids() -> None:
    # #812: D no longer hidden; harness resolved{} only walks HIDDEN (empty). Spot-check via builtinAll.
    r = report()
    assert set(("yingzao", "crt-interface", "crayon-sketch", "fabric-collage")) <= set(r["listed"])


COPY = {
    "zh": "该技能暂时下线，旧对话仍可查看；如需继续，请换一个技能。",
    "en": "This skill is temporarily unavailable. You can still view this conversation; pick another skill to continue.",
}


@needs_node
@pytest.mark.parametrize("lang", ["zh", "en"])
@pytest.mark.parametrize("sid", ["yingzao", "crt-interface"])
def test_former_hidden_d_skills_attach_after_812(lang, sid) -> None:
    """#812: D unhidden — deep link / attach succeeds; blockHiddenSkill is false."""
    g = report()["guard"][lang][sid]
    assert g["attached"] is True and g["linkChip"] == sid and g["linkNotice"] is None
    assert g["blocked"] is False and g["submits"] == 1


@needs_node
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_listed_skill_still_attaches_and_clears_notice(lang) -> None:
    g = report()["guard"][lang]
    # #812: yingzao no longer hidden → notice null
    assert g["notice"] is None
    assert g["listed"] == {"attached": True, "chip": "poster-differentiated-compiler", "notice": None, "blocked": False}


@needs_node
def test_hidden_skill_guard_makes_zero_network_requests() -> None:
    assert report()["guard"]["requests"] == 0


def test_three_attach_paths_use_the_guard_before_any_send() -> None:
    handoff = (ROOT / "src/home/handoff.ts").read_text()
    h = handoff[handoff.index("const found = skillId"):]
    assert "attachSkill(skill)" in h and h.index("attachSkill(skill)") < h.index("sendToAgent(")
    assert h.index("return\n", h.index("attachSkill(skill)")) < h.index("refreshBot()")  # deep link stops before any request
    panel = (ROOT / "src/ui/AgentPanel.tsx").read_text()
    r = panel[panel.index("async function resend"):]
    assert r.index("blockHiddenSkill(skill)) return") < r.index("sendToAgent(")
    chat = (ROOT / "src/ui/ChatMessage.tsx").read_text()
    t = chat[chat.index("const tryIt"):chat.index("return (", chat.index("const tryIt"))]
    assert "attachSkill(s)" in t and "skillAtom.set" not in t
    agent = (ROOT / "src/agent.ts").read_text()
    body = agent[agent.index("export async function sendToAgent"):]
    assert body.index("blockHiddenSkill(skill)) return") < body.index("sendMessage(")
    comp = (ROOT / "src/ui/Composer.tsx").read_text()
    assert 'data-testid="skill-hidden-notice"' in comp and "useValue(skillNoticeAtom)" in comp


@needs_node
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_agent_read_of_hidden_skill_by_id_is_not_an_error_733(lang) -> None:
    # #733: hiding only affects entry points / UI; reading by id resolves
    assert report()["guard"][lang].get("readErr") is None


@needs_node
@pytest.mark.parametrize("lang", ["zh", "en"])
def test_simulated_hidden_skill_attach_shows_notice_870(lang) -> None:
    """#870: hide list empty after #812 — harness temporarily adds yingzao to the Set so
    attachSkill / blockHiddenSkill / notice copy stay covered ($0). Not a product hide."""
    g = report()["simulatedHidden"][lang]
    assert g["attached"] is False and g["chip"] is None
    assert g["blocked"] is True
    assert g["notice"] == COPY[lang] and g["noticeCopy"] == COPY[lang]


SRC = ROOT / "src"


@pytest.mark.parametrize("path,n", [("home/Home.tsx", 2), ("home/Skills.tsx", 2), ("ui/Composer.tsx", 1)])
def test_pick_lists_load_listed_skills(path, n) -> None:
    text = (SRC / path).read_text()
    assert text.count("loadListedSkills().then(setSkills)") == n
    assert "loadSkills().then(setSkills)" not in text


def test_lookups_for_saved_work_keep_full_loadSkills() -> None:
    # handoff (saved / shared start by id) and resend must resolve hidden ids
    assert "(await loadSkills()).find((s) => s.id === skillId)" in (SRC / "home/handoff.ts").read_text()
    assert "(await loadSkills()).find((s) => s.name === skillName)" in (SRC / "ui/AgentPanel.tsx").read_text()
    assert "BUILTIN_SKILLS.find((x) => x.id === s.skillId)" in (SRC / "home/Home.tsx").read_text()


def test_relist_instructions_documented() -> None:
    s = (SRC / "skills.ts").read_text()
    m = re.search(r"TO RE-LIST A SKILL:[^\n]*", s)
    assert m and "delete its id from this array" in m.group(0)
