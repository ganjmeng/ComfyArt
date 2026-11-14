"""#982 — every built-in image skill declares its delivery (product ruling, 2026-11-14).

* Coverage: each built-in is in exactly one bucket — declared in OUTPUTS/SKILL_OUTPUT, a dedicated
  server module/pin, video-only, or the hard-coded TODO allowlist. A new built-in with no declaration
  turns this red; the allowlist may only shrink (adding a skill to it is red too).
* Undeclared (TODO) skills get an explicit lock — 1:1, count=1, size_lock in ratio mode — mirrored in
  src/skills.ts, never the page's silent 1:1 fallback.
* Mutations: deleting one skill's declaration is red; a submit without width/height is red.
$0: no WaveSpeed call.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from ComfyArt.bot import skill_output as so
from ComfyArt.bot.skill_output import (
    GENERIC_DEFAULT_982, OUTPUTS, TODO_ALLOWLIST_982, TODO_TEMPLATES_982, apply_generate, plan_for,
    run_hint,
)

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not (ROOT / "node_modules/.bin/rolldown").exists(), reason="needs node + node_modules")

# Hard-coded on purpose. This list may only SHRINK: a skill leaves it when its delivery is declared.
# Never add a skill here — declare its OUTPUTS / SKILL_OUTPUT row instead.
TODO_ALLOWLIST_LITERAL = frozenset({
    "marketing-campaign-generator", "style-transfer", "person-swap", "commerce-strategist", "lifestyle-scene",
    "naive-illustration", "logo-abstract", "photo-split-poster", "promo-ecommerce", "crt-interface",
    "crayon-sketch", "fabric-collage", "live-promo-decor", "creator-identity", "product-website",
    "premium-website", "restaurant-website",
    "flash-cut-video", "animated-poster",  # their still (generate_image) step only
})
TODO_TEMPLATES_LITERAL = frozenset({"character-sheet-design:editorial"})
# A dedicated server module / pin owns the delivery (not a generic size table).
DEDICATED = {
    "portrait-studio": "api/portrait_studio.py",
    "product-to-packaging": "api/product_packaging.py",
    "youtube-channel-banner": "api/banner_compose.py",
    "studio-model": "api/auto_models.json pin; #911/#914: no invented size",
    "ai-model": "api/auto_models.json pin + ask card; #911/#914: no invented size",
}
# Deliver a video only (generate_video, whose ratio/tier logic is separate).
VIDEO_ONLY = frozenset({"product-tvc-advertisement-generator", "motion-poster-generator", "logo-animation", "anim-2d"})

# Product ruling #982 as literals: (width, height, ratio, images) for the default call; stages where set.
EXPECTED = {
    "logo-material-explorer": (so.LOGO_MATERIAL_SIZE_982, so.LOGO_MATERIAL_SIZE_982, "1:1", 4),
    "character-sheet-design": (1024, 1024, "1:1", 1),
    "poster-differentiated-compiler": (1536, 2048, "3:4", 1),
    "rednote-cover-maker": (1024, 1024, "1:1", 3),
    "banner-design-director": (2048, 1152, "16:9", 1),
    "cover-design-director": (2048, 1152, "16:9", 1),
    "meta-ads-creative-director": (1024, 1024, "1:1", 3),
    "mobile-app-visual-design": (1024, 1824, "9:16", 3),
    "web-product-visual-design": (2048, 1152, "16:9", 1),
    "ppt-visual": (2048, 1152, "16:9", 3),
    "yingzao": (1536, 2048, "3:4", 1),
    "taobao-product": (1024, 1024, "1:1", 4),
    "interior-architectural-visualization": (2048, 1152, "16:9", 2),
}
PACK = [(1024, 1024, "1:1"), (1600, 2000, "4:5"), (1024, 1824, "9:16")]
EXPECTED_STAGES = {
    "rednote-cover-maker": PACK,
    "meta-ads-creative-director": PACK,
    "interior-architectural-visualization": [(2048, 1152, "16:9"), (2048, 1536, "4:3")],
}
CHARACTER = {
    "turnaround": (1024, 1024, "1:1"), "expression": (2048, 1152, "16:9"), "modeling": (2048, 1152, "16:9"),
    "outfit": (1024, 1024, "1:1"), "prop": (1024, 1024, "1:1"), "basic": (2048, 1152, "16:9"),
    "technical": (2048, 1152, "16:9"), "editorial": (1024, 1024, "1:1"),  # editorial = generic (TODO)
}


def builtin_ids() -> list[str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    return list(dict.fromkeys(re.findall(r"\{ id: '([a-z0-9-]+)', name: t\(", SKILLS_TS[a:])))


def uncovered(ids, outputs, todo) -> set[str]:
    """Built-ins with no delivery owner at all (the coverage rule)."""
    return {sid for sid in ids if sid not in outputs and sid not in DEDICATED and sid not in VIDEO_ONLY
            and sid not in todo}


def missing_submit_size(ids, apply) -> set[str]:
    """Image skills whose generate_image args (model omitted every size) would reach the page without
    width/height/size_lock — i.e. would fall to the page's silent default."""
    bad = set()
    for sid in ids:
        if sid in VIDEO_ONLY or sid in DEDICATED:
            continue
        out = apply({"prompt": "a study", "skill": sid}, sid)
        if not (out.get("width") and out.get("height") and out.get("size_lock") and out.get("count") == 1):
            bad.add(sid)
    return bad


def test_every_builtin_has_exactly_one_delivery_owner():
    ids = builtin_ids()
    assert len(ids) == 49
    assert uncovered(ids, OUTPUTS, TODO_ALLOWLIST_982) == set()
    buckets = [set(OUTPUTS), set(DEDICATED), set(VIDEO_ONLY), set(TODO_ALLOWLIST_982)]
    for sid in ids:
        assert sum(sid in b for b in buckets) == 1, sid
    assert set(OUTPUTS) <= set(ids) and set(DEDICATED) <= set(ids) and set(TODO_ALLOWLIST_982) <= set(ids)


def test_todo_allowlist_only_shrinks():
    # Growing the module list (or the TS mirror) beyond the literal is red.
    assert set(TODO_ALLOWLIST_982) <= TODO_ALLOWLIST_LITERAL
    assert set(TODO_TEMPLATES_982) <= TODO_TEMPLATES_LITERAL
    # A declared skill must leave the list (no stale entries).
    assert not (set(TODO_ALLOWLIST_982) & set(OUTPUTS))
    for entry in TODO_TEMPLATES_982:
        sid, pid = entry.split(":")
        assert OUTPUTS[sid]["presets"][pid].get("todo") is True, entry
    todo_presets = {f"{sid}:{pid}" for sid, row in OUTPUTS.items()
                    for pid, plan in (row.get("presets") or {}).items() if plan.get("todo")}
    assert todo_presets == set(TODO_TEMPLATES_982)


def test_mutation_deleting_one_declaration_is_red():
    ids = builtin_ids()
    for victim in ("logo-material-explorer", "character-sheet-design", "yingzao"):
        mutated = {k: v for k, v in OUTPUTS.items() if k != victim}
        assert uncovered(ids, mutated, TODO_ALLOWLIST_982) == {victim}
    # Moving a declared skill into the allowlist instead is red too.
    assert not (set(TODO_ALLOWLIST_982) | {"yingzao"}) <= TODO_ALLOWLIST_LITERAL


def test_every_image_skill_submits_explicit_pixels():
    assert missing_submit_size(builtin_ids(), apply_generate) == set()


def test_mutation_submit_without_pixels_is_red():
    def dropped(args, skill=""):
        out = apply_generate(args, skill)
        out.pop("width", None)
        out.pop("height", None)
        return out

    def page_fallback(args, skill=""):  # the pre-#982 behavior: unknown skill left alone
        return dict(args)

    ids = builtin_ids()
    assert missing_submit_size(ids, dropped) == set(OUTPUTS) | set(TODO_ALLOWLIST_982)
    assert missing_submit_size(ids, page_fallback) >= set(OUTPUTS) | set(TODO_ALLOWLIST_982)


@pytest.mark.parametrize("sid", sorted(EXPECTED))
def test_declared_default_call(sid):
    w, h, ratio, images = EXPECTED[sid]
    row = OUTPUTS[sid]
    assert (row["width"], row["height"], row["ratio"], row["images"]) == (w, h, ratio, images)
    out = apply_generate({"prompt": "x", "skill": sid}, sid)
    assert (out["width"], out["height"], out["ratio"], out["count"]) == (w, h, ratio, 1)
    assert out["size_lock"] is True and out["size_lock_mode"] == "ratio"
    # The model invents a size: the declared one wins.
    inv = apply_generate({"prompt": "x", "skill": sid, "width": 512, "height": 512, "ratio": "1:1", "count": 3}, sid)
    assert (inv["width"], inv["height"], inv["count"]) == (w, h, 1)
    assert run_hint(sid, preset_id="").startswith("Output lock:")


@pytest.mark.parametrize("sid", sorted(EXPECTED_STAGES))
def test_ratio_packs_are_stages(sid):
    want = EXPECTED_STAGES[sid]
    for i, (w, h, ratio) in enumerate(want, 1):
        plan = plan_for(sid, "", i)
        assert (plan["width"], plan["height"], plan["ratio"], plan["images"]) == (w, h, ratio, 1)
        out = apply_generate({"prompt": "x", "skill": sid, "stage": i}, sid)
        assert (out["width"], out["height"], out["ratio"], out["stage"]) == (w, h, ratio, i)
        assert "preset" not in out  # a staged row without templates carries no template id
        # relay pass is idempotent
        assert apply_generate(dict(out)) == out
    assert plan_for(sid, "", 1)["total_images"] == len(want) == OUTPUTS[sid]["images"]
    hint = run_hint(sid)
    assert f"exactly {len(want)} separate images" in hint and "template=" not in hint


@pytest.mark.parametrize("pid", list(CHARACTER))
def test_character_sheet_per_template(pid):
    w, h, ratio = CHARACTER[pid]
    out = apply_generate({"prompt": "x", "skill": "character-sheet-design", "preset": pid}, "character-sheet-design")
    assert (out["width"], out["height"], out["ratio"], out["count"], out["preset"]) == (w, h, ratio, 1, pid)
    assert out["size_lock_mode"] == "ratio"
    assert so.is_single("character-sheet-design", pid)
    hint = run_hint("character-sheet-design", preset_id=pid)
    assert f"template={pid}" in hint and f"width={w} height={h}" in hint
    assert ("TODO #982" in hint) == (pid == "editorial")


def test_logo_material_four_materials_with_refs():
    row = OUTPUTS["logo-material-explorer"]
    assert row["materials"] == ("brushed metal", "clear glass", "woven fabric / embroidered emblem", "glazed ceramic")
    hint = run_hint("logo-material-explorer")
    assert "exactly 4 separate images" in hint and "refs" in hint and "one material per call" in hint
    for m in row["materials"]:
        assert m in hint
    assert not so.is_single("logo-material-explorer")
    out = apply_generate({"prompt": "glass", "skill": "logo-material-explorer", "refs": ["shape:logo"]})
    assert out["refs"] == ["shape:logo"]
    # One switch: LOGO_MATERIAL_SIZE_982 (product may move 1254 <-> 1024).
    assert row["width"] == row["height"] == so.LOGO_MATERIAL_SIZE_982 == 1254
    assert "LOGO_MATERIAL_SIZE_982 = 1254" in SKILLS_TS


@pytest.mark.parametrize("sid", sorted(TODO_ALLOWLIST_LITERAL))
def test_todo_skills_get_the_explicit_generic_lock(sid):
    g = GENERIC_DEFAULT_982
    assert (g["width"], g["height"], g["ratio"], g["images"]) == (1024, 1024, "1:1", 1)
    for args, cur in (({"prompt": "x", "skill": sid}, ""), ({"prompt": "x"}, sid),
                      ({"prompt": "x", "skill": sid, "ratio": "16:9", "width": 2048, "height": 1152, "count": 4}, "")):
        out = apply_generate(args, cur)
        assert (out["skill"], out["width"], out["height"], out["ratio"], out["count"]) == (sid, 1024, 1024, "1:1", 1)
        assert out["size_lock"] is True and out["size_lock_mode"] == "ratio"
    # resolves by display name too (the chat loop passes the visible name)
    name = TODO_ALLOWLIST_982[sid][2]
    assert apply_generate({"prompt": "x"}, name)["skill"] == sid
    assert "TODO #982" in run_hint(sid) and "width=1024 height=1024 ratio=1:1" in run_hint(sid)
    assert not so.is_single(sid)  # generic is count=1 per call, not a single-image skip


def test_custom_and_unknown_skills_are_left_alone():
    assert apply_generate({"prompt": "cat", "ratio": "1:1"}) == {"prompt": "cat", "ratio": "1:1"}
    assert apply_generate({"prompt": "x", "skill": "my-own-skill"}) == {"prompt": "x", "skill": "my-own-skill"}
    assert run_hint("my-own-skill") == ""
    # studio-model / ai-model keep #911/#914 (skill= only, no invented size)
    for sid in ("studio-model", "ai-model"):
        out = apply_generate({"prompt": "x"}, sid)
        assert "width" not in out and "size_lock" not in out


def test_existing_rows_keep_exact_lock():
    for sid in ("before-after", "pose-fission", "universal-multi-angle-grid", "game-art", "linkedin-banner",
                "clothing-swap", "brand-identity-director", "packaging-design-director"):
        assert "lock" not in OUTPUTS[sid], sid
        assert "size_lock_mode" not in apply_generate({"prompt": "x", "skill": sid}, sid), sid


@lru_cache(maxsize=1)
def js_report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"output982-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/preset978/rolldown.config.mjs"],
                   cwd=ROOT, check=True, capture_output=True,
                   env={**os.environ, "OUT": str(out), "ENTRY": "../output982/main.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True, timeout=60).stdout)


@needs_node
def test_ts_mirror_matches_python():
    js = js_report()
    assert sorted(js["builtins"]) == sorted(builtin_ids())
    assert set(js["todo"]) == set(TODO_ALLOWLIST_982)
    assert js["logoSize"] == so.LOGO_MATERIAL_SIZE_982
    g = js["generic"]
    assert {k: g[k] for k in ("width", "height", "ratio", "images", "lock")} == GENERIC_DEFAULT_982
    for sid, row in OUTPUTS.items():
        got = js["skillOutput"][sid]
        for key in ("width", "height", "ratio", "images"):
            assert got.get(key) == row.get(key), (sid, key)
        assert got.get("lock") == row.get("lock"), sid
        if row.get("stages") and not row.get("presets"):
            assert got["stages"] == [{k: s[k] for k in ("width", "height", "ratio", "images")} for s in row["stages"]], sid
        for pid, plan in (row.get("presets") or {}).items():
            tp = got["presets"][pid]
            if not plan.get("stages"):
                for key in ("width", "height", "ratio", "images"):
                    assert tp.get(key) == plan.get(key), (sid, pid, key)
                assert bool(tp.get("todo")) == bool(plan.get("todo")), (sid, pid)
    # skill read reports a delivery for every built-in image skill (declared row or the generic lock)
    for sid in builtin_ids():
        read = js["readOutput"][sid]
        if sid in OUTPUTS:
            assert read == js["skillOutput"][sid], sid
        elif sid in TODO_ALLOWLIST_982:
            assert read == js["generic"], sid
        else:
            assert read is None, sid
    # template ids are the real ones the page has; logo has no presets (#981)
    assert js["characterPresets"] == list(CHARACTER) == list(OUTPUTS["character-sheet-design"]["presets"])
    assert js["logoPresets"] == []
