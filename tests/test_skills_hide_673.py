"""#673 — the 9 deferred Phase2 built-ins are a real hide list: not offered for new selection on any pick-list
(home featured / chips / + menu, Skills page, composer /, agent skill list + read) but still resolvable by id so
saved sessions and cards keep opening. Real src/skills.ts through a node harness (tests/js/hide673). $0."""
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

HIDDEN = ["naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
          "yingzao", "crt-interface", "crayon-sketch", "fabric-collage"]
# BUILTIN_SKILLS order on main eb0d60b1 with the 9 removed — the 40 must keep exactly this order.
MAIN_ORDER_40 = [
    "product", "multi-angle", "brand", "character", "logo-material", "packaging", "motion", "meta-ads", "poster",
    "thumbnail", "mobile-ui", "social", "marketing-campaign", "web-product", "banner", "flash-cut-video",
    "style-transfer", "person-swap", "commerce-strategist", "lifestyle-scene", "taobao-product", "before-after",
    "anim-2d", "creator-identity", "product-website", "studio-model", "youtube-channel-banner", "ai-model",
    "product-to-packaging", "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
    "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap", "interior",
]


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"hide673-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/hide673/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={**os.environ, "OUT": str(out)})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


@needs_node
def test_hide_list_is_the_9_and_builtins_keep_all_49() -> None:
    r = report()
    assert r["hidden"] == HIDDEN
    assert len(r["builtinAll"]) == 49 and set(HIDDEN) <= set(r["builtinAll"])  # nothing deleted
    assert [i for i in r["builtinAll"] if i not in HIDDEN] == MAIN_ORDER_40


@needs_node
def test_listed_is_the_other_40_in_main_order() -> None:
    assert report()["listed"] == MAIN_ORDER_40


@needs_node
def test_category_chips_never_contain_hidden() -> None:
    r = report()
    for chip, ids in r["byChip"].items():
        assert not set(ids) & set(HIDDEN), (chip, ids)
    assert r["byChip"]["forYou"] == MAIN_ORDER_40
    # every listed skill still lands in some category chip, in order
    for chip, ids in r["byChip"].items():
        assert ids == [i for i in MAIN_ORDER_40 if i in ids], chip


@needs_node
def test_home_featured_never_contains_hidden() -> None:
    f = report()["featured"]
    assert f and not set(f) & set(HIDDEN)


@needs_node
def test_agent_list_excludes_hidden_and_keeps_order() -> None:
    assert report()["agentList"] == MAIN_ORDER_40


@needs_node
@pytest.mark.parametrize("sid", HIDDEN)
def test_agent_read_of_hidden_is_not_available_non_retryable(sid) -> None:
    for how in ("byId", "byName"):
        err = report()["hiddenReads"][sid][how]["error"]
        assert err.startswith("[non-retryable]") and "is not available" in err, err


@needs_node
def test_agent_read_listed_still_works_and_unknown_lists_only_listed() -> None:
    r = report()
    assert r["listedReadId"] == "poster"
    err = r["unknown"]["error"]
    assert err.startswith("unknown skill") and not any(f"({h})" in err for h in HIDDEN)


@needs_node
@pytest.mark.parametrize("sid", HIDDEN)
def test_saved_session_or_card_still_resolves_hidden_by_id(sid) -> None:
    res = report()["resolved"][sid]
    assert "error" not in res, res
    assert res["found"] is True and res["name"] and res["params"] is True


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
