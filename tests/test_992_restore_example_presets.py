"""#992 homepage same-surface: default UI must not show the five option-chip groups.

Base runtime and original Home have no default chips for these five example cards.
Source P() stays in skills.ts; applyRaw748 clears them at runtime (kind stays
example). Default output packs, #994 explicit text ratios, backend parsing, and
ratio_from_example_preset_992 (idle unless a preset id is later passed) stay.
Logo stays no-template. These tests do not treat default chips or chip-clicks as
acceptance. $0, no paid calls, no network except local node bundling of src/.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from ComfyArt.api.bot_send import compose_provider_text
from ComfyArt.bot.skill_output import (
    LOGO_MATERIAL_SIZE_982,
    LOGO_MATERIALS_982,
    OUTPUTS,
    apply_generate,
    run_hint,
)

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)

RESTORE: dict[str, tuple[str, ...]] = {
    "meta-ads-creative-director": ("feed1x1", "feed4x5", "story9x16", "ugc"),
    "rednote-cover-maker": ("ugc-feed", "ugc-story"),
    "mobile-app-visual-design": ("home", "detail", "checkout", "onboarding"),
    "web-product-visual-design": ("hero", "features", "pricing", "responsive"),
    "marketing-campaign-generator": ("kv", "rednote-cover-maker", "display", "ooh"),
}
# Inventory (a): intentional no-template. Logo plus the five no-P() examples this
# card does not change.
INTENTIONAL_NO_TEMPLATE = (
    "logo-material-explorer",
    "cover-design-director",
    "poster-differentiated-compiler",
    "banner-design-director",
    "universal-multi-angle-grid",
    "interior-architectural-visualization",
)
# Source P() on these five is kept, but default runtime UI must clear them (base behavior).
INTENTIONAL_RUNTIME_CLEAR = frozenset(RESTORE) | frozenset(INTENTIONAL_NO_TEMPLATE)
LOGO = "logo-material-explorer"
DEFAULT_PACKS = {
    "meta-ads-creative-director": ((1024, 1024, "1:1"), (1638, 2048, "4:5"), (1152, 2048, "9:16")),
    "rednote-cover-maker": ((1024, 1024, "1:1"), (1638, 2048, "4:5"), (1152, 2048, "9:16")),
    "marketing-campaign-generator": ((2048, 1152, "16:9"), (1638, 2048, "4:5"), (1152, 2048, "9:16")),
    "mobile-app-visual-design": ((880, 2048, "9:21"), (880, 2048, "9:21")),
    "web-product-visual-design": ((2048, 1152, "16:9"),),
}
RATIO_SIZE = {
    "1:1": (1024, 1024),
    "4:5": (1638, 2048),
    "9:16": (1152, 2048),
    "9:21": (880, 2048),
    "16:9": (2048, 1152),
}
DEAD_PRESET_COPY = re.compile(r"per selected preset", re.I)
CROP_SAME = re.compile(
    r"responsive crop|响应式裁切|crop of the same|scale of the same|裁剪同一|缩放同一",
    re.I,
)

# Exact applyRaw748 example branch this patch restores (matches base 4ce96715).
EXAMPLE_BRANCH_BASE = (
    "  if (r.kind === 'example') return { ...skill, name, description, presets: undefined, "
    "inputs: (r.inputs ?? []).map((q) => toInput(q, ours.placeholders, optional)), "
    "...examplesFromHighlights(skill, r) }\n"
)
# Removed tip behavior reintroduced only inside the mutation test.
REMOVED_EXCEPTIONS_BLOCK = """/** #992 — example-card skills whose source P() options must survive applyRaw748.
 *  Kind stays `example`; the examples[] carousel is kept. These are selectable
 *  Style / ratio / page-focus chips, not raw template tiles. Logo and the
 *  other no-P() example cards are intentionally absent. */
export const EXAMPLE_PRESET_SKILLS_992 = [
  'meta-ads-creative-director',
  'rednote-cover-maker',
  'mobile-app-visual-design',
  'web-product-visual-design',
  'marketing-campaign-generator',
] as const
export const isExamplePresetSkill992 = (id: string) =>
  (EXAMPLE_PRESET_SKILLS_992 as readonly string[]).includes(id)

"""
REMOVED_EXAMPLE_BRANCH = """  if (r.kind === 'example') {
    // #992: keep source P() on the five restored skills so a selection can enter
    // the #978 send body. Do not invent template thumbnails; chips are text-only.
    // Every other example card, including logo-material-explorer, stays no-template.
    const keep = isExamplePresetSkill992(skill.id) ? skill.presets : undefined
    return {
      ...skill, name, description, presets: keep,
      ...(keep?.length ? { presetChips: true } : {}),
      inputs: (r.inputs ?? []).map((q) => toInput(q, ours.placeholders, optional)),
      ...examplesFromHighlights(skill, r),
    }
  }
"""


def _bundle_report(*, skill_raw: Path | None = None, tag: str = "default") -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"preset992-{tag}-{os.getpid()}.mjs"
    env = {**os.environ, "OUT": str(out), "CA992_ROOT": str(ROOT)}
    if skill_raw is not None:
        env["CA992_SKILL_RAW"] = str(skill_raw)
    bundled = subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/preset992/rolldown.config.mjs"],
        cwd=ROOT, capture_output=True, env=env, text=True,
    )
    if bundled.returncode != 0:
        raise RuntimeError(bundled.stderr or bundled.stdout)
    proc = subprocess.run(
        ["node", str(out)], capture_output=True, text=True, timeout=60, env=env, cwd=ROOT,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


@lru_cache(maxsize=1)
def report() -> dict:
    return _bundle_report()


def source_ids(sid: str) -> list[str]:
    return [p["id"] for p in report()["sourcePresets"].get(sid, [])]


def source_prompt(sid: str, pid: str) -> str:
    return next(p["prompt"] for p in report()["sourcePresets"][sid] if p["id"] == pid)


def runtime_ids(sid: str, runtime: dict | None = None) -> list[str]:
    row = (runtime if runtime is not None else report()["runtime"]).get(sid) or {}
    return [p["id"] for p in row.get("presets") or []]


def emptied_source_presets(runtime: dict | None = None) -> dict[str, list[str]]:
    """Skills that still declare P() in src/skills.ts but lose them after applyRaw748."""
    data = report()
    rt = runtime if runtime is not None else data["runtime"]
    lost: dict[str, list[str]] = {}
    for sid, rows in data["sourcePresets"].items():
        declared = [p["id"] for p in rows]
        if not declared:
            continue
        kept = set(runtime_ids(sid, rt))
        missing = [pid for pid in declared if pid not in kept]
        if missing:
            lost[sid] = missing
    return lost


def assert_default_runtime_has_no_chips(runtime: dict) -> None:
    """Acceptance: default visible UI has no option chips on the five homepage skills."""
    for sid, ids in RESTORE.items():
        row = runtime[sid]
        assert runtime_ids(sid, runtime) == [], f"{sid} default runtime still has presets: {runtime_ids(sid, runtime)}"
        assert not row.get("presetChips"), f"{sid} default runtime still sets presetChips"
        assert row["kind"] == "example", sid
        assert row["examples"], f"{sid} must keep the original example area"
        # Source P() must still exist; only the default UI hook-up is removed.
        assert source_ids(sid) == list(ids), (sid, source_ids(sid))


def pack_payloads(sid: str, *, preset_id: str = "", user_text: str = "",
                  attempted=None, prompt: str = "") -> list[dict]:
    """Production compose + apply_generate path used by chat/relay before a mock submit."""
    text = compose_provider_text(
        user_text or "Generate the selected option.",
        skill_name=sid, preset_prompt=prompt, preset_id=preset_id,
    )
    attempts = list(attempted if attempted is not None else DEFAULT_PACKS[sid])
    out = []
    for item in attempts:
        args = {"skill": sid, "prompt": "mock frame", "refs": ["shape:ref-992"], "count": 1}
        if isinstance(item, tuple) and len(item) == 3:
            args["width"], args["height"], args["ratio"] = item
        out.append(apply_generate(args, sid, user_text=text, current_preset=preset_id))
    return out


def sizes(rows: list[dict]) -> list[tuple[int, int, str]]:
    return [(int(r["width"]), int(r["height"]), str(r["ratio"])) for r in rows]


def uniform(ratio: str, count: int) -> list[tuple[int, int, str]]:
    w, h = RATIO_SIZE[ratio]
    return [(w, h, ratio)] * count


def reintroduce_removed_applyRaw748_exceptions(src: str) -> str:
    """Replay the removed tip exceptions into a copy of skillRaw748.ts."""
    if EXAMPLE_BRANCH_BASE not in src:
        raise AssertionError("current skillRaw748.ts is not on the cleared example branch")
    if "isExamplePresetSkill992" in src or "EXAMPLE_PRESET_SKILLS_992" in src:
        raise AssertionError("exceptions are already present; mutation would not be a reintroduction")
    out = src.replace(
        "export function applyRaw748(skill: Skill): Skill {",
        REMOVED_EXCEPTIONS_BLOCK + "export function applyRaw748(skill: Skill): Skill {",
        1,
    )
    out = out.replace(EXAMPLE_BRANCH_BASE, REMOVED_EXAMPLE_BRANCH, 1)
    if "isExamplePresetSkill992" not in out or "presetChips: true" not in out:
        raise AssertionError("failed to reintroduce removed applyRaw748 exceptions")
    return out


def test_home_and_skills_share_skill_run_dialog():
    """Home and Skills both open the same SkillRunDialog over BUILTIN_SKILLS."""
    home = (ROOT / "src/home/Home.tsx").read_text()
    skills = (ROOT / "src/home/Skills.tsx").read_text()
    assert "import { SkillRunDialog } from '../ui/SkillRunDialog'" in home
    assert "import { SkillRunDialog } from '../ui/SkillRunDialog'" in skills
    assert "BUILTIN_SKILLS" in home
    assert "<SkillRunDialog skill={runSkill}" in home
    assert "<SkillRunDialog skill={runSkill}" in skills
    # Comment on Home already documents the shared surface.
    assert "same SkillRunDialog as the Skills page" in home
    raw = (ROOT / "src/skillRaw748.ts").read_text()
    dialog = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
    skills_ts = (ROOT / "src/skills.ts").read_text()
    assert "isExamplePresetSkill992" not in raw
    assert "EXAMPLE_PRESET_SKILLS_992" not in raw
    assert "isExamplePresetSkill992" not in dialog
    assert "isExamplePresetSkill992" not in skills_ts
    assert EXAMPLE_BRANCH_BASE in raw


@needs_node
def test_default_runtime_has_no_chips_and_forbids_unregistered_clearing():
    r = report()
    lost = emptied_source_presets()
    for sid in INTENTIONAL_NO_TEMPLATE:
        assert sid in r["runtime"], sid
        assert runtime_ids(sid) == [], f"{sid} must stay a no-template example card"
        if sid != LOGO:
            assert source_ids(sid) == [], f"{sid} is a no-P() example this card does not change"
        examples = r["runtime"][sid]["examples"]
        assert examples, f"{sid} must keep its example-image area"
        assert r["runtime"][sid]["kind"] == "example", sid
        assert not r["runtime"][sid].get("presetChips"), sid
    assert source_ids(LOGO) == [], "do not restore deleted logo P() templates"
    assert_default_runtime_has_no_chips(r["runtime"])
    unexpected = {sid: pids for sid, pids in lost.items() if sid not in INTENTIONAL_RUNTIME_CLEAR}
    assert unexpected == {}, f"unregistered applyRaw748 emptying: {unexpected}"
    # The five homepage skills are the registered runtime-clear (source P() kept, default UI off).
    for sid in RESTORE:
        assert sid in lost, f"{sid} source P() should be cleared only at default runtime"


@needs_node
def test_logo_is_intentional_no_template_and_keeps_996_contract():
    r = report()["runtime"][LOGO]
    copy = json.loads((ROOT / "src/data/copy-748.json").read_text(encoding="utf-8")).get(LOGO, {})
    blob = "\n".join([
        r["instructions"],
        run_hint(LOGO),
        json.dumps(r, ensure_ascii=False),
        json.dumps(copy, ensure_ascii=False),
    ])
    assert DEAD_PRESET_COPY.search(blob) is None, "leftover 'per selected preset' copy must be deleted"
    assert "per selected preset" not in r["instructions"].lower()
    keys = {f["key"]: f for f in r["inputs"]}
    assert keys["user_image"]["required"] is True
    assert keys["user_requirement"]["required"] is True
    row = OUTPUTS[LOGO]
    assert LOGO_MATERIAL_SIZE_982 == 1254
    assert (row["width"], row["height"], row["ratio"], row["images"]) == (1254, 1254, "1:1", 4)
    assert tuple(row["materials"]) == LOGO_MATERIALS_982
    assert row["lock"] == "ratio"  # 1254 cannot be hit exactly; flare/edit uses the 2k tier
    hint = run_hint(LOGO)
    for mat in LOGO_MATERIALS_982:
        assert mat in hint
    args = apply_generate({"skill": LOGO, "prompt": "brushed metal", "refs": ["shape:logo"], "count": 1}, LOGO)
    assert (args["width"], args["height"], args["ratio"], args["count"]) == (1254, 1254, "1:1", 1)
    assert args["refs"] == ["shape:logo"]
    assert r["presets"] == []
    assert not r.get("presetChips")
    assert LOGO not in report()["deliveries"]


@needs_node
def test_default_runtime_does_not_deliver_cleared_presets_as_ui_selection():
    """Default skill objects have no chips; send probes must not claim a UI selection landed."""
    for sid, ids in RESTORE.items():
        for pid in ids:
            delivery = report()["deliveries"][sid][pid]
            assert delivery.get("reason") == "missing-runtime-preset", delivery
            # Source P() remains available for a later non-default path; this is not UI acceptance.
            assert source_prompt(sid, pid).startswith("Style:")
            assert "{{" not in source_prompt(sid, pid)


@needs_node
def test_unselected_default_packs_and_994_text_ratio_stay():
    """No chip selection keeps typed default packs; explicit #994 wording still wins."""
    for sid, pack in DEFAULT_PACKS.items():
        assert sizes(pack_payloads(sid)) == list(pack), sid
    sid = "meta-ads-creative-director"
    assert sizes(pack_payloads(sid, user_text="做一套 Meta 广告。")) == list(DEFAULT_PACKS[sid])
    got = pack_payloads(sid, user_text="改成 9:16，三张都要这个比例。", attempted=DEFAULT_PACKS[sid])
    assert sizes(got) == uniform("9:16", 3)
    named = pack_payloads("rednote-cover-maker", user_text="请全部做成 4:5，不要改张数。")
    assert sizes(named) == uniform("4:5", 3)


@needs_node
def test_backend_preset_id_mapping_stays_idle_not_default_ui():
    """Backend still honors a later-passed preset id; this is not default-chip UI acceptance."""
    sid = "meta-ads-creative-director"
    default = DEFAULT_PACKS[sid]
    for pid, ratio in (("feed1x1", "1:1"), ("feed4x5", "4:5"), ("story9x16", "9:16")):
        prompt = source_prompt(sid, pid)
        got = pack_payloads(sid, preset_id=pid, prompt=prompt, attempted=default)
        assert sizes(got) == uniform(ratio, 3), (pid, sizes(got))
        assert all(row["count"] == 1 and row["refs"] == ["shape:ref-992"] and "model" not in row for row in got)
        hint = run_hint(sid, preset_id=pid)
        assert f"ratio={ratio}" in hint
        for other in ("1:1", "4:5", "9:16"):
            if other != ratio:
                assert f"ratio={other}" not in hint, (pid, hint)
    ugc_prompt = source_prompt(sid, "ugc")
    ugc = pack_payloads(sid, preset_id="ugc", prompt=ugc_prompt, attempted=default)
    assert sizes(ugc) == list(default)
    assert "Style:" in ugc_prompt and not any(tag in ugc_prompt for tag in ("1:1", "4:5", "9:16"))

    sid = "rednote-cover-maker"
    assert source_ids(sid) == ["ugc-feed", "ugc-story"]
    for pid, ratio in (("ugc-feed", "1:1"), ("ugc-story", "9:16")):
        prompt = source_prompt(sid, pid)
        got = pack_payloads(sid, preset_id=pid, prompt=prompt, attempted=DEFAULT_PACKS[sid])
        assert sizes(got) == uniform(ratio, 3), (pid, sizes(got))
        assert all(row["count"] == 1 and row["refs"] == ["shape:ref-992"] for row in got)


@needs_node
def test_mobile_web_campaign_default_contracts_and_copy():
    sid = "mobile-app-visual-design"
    default = list(DEFAULT_PACKS[sid])
    assert sizes(pack_payloads(sid)) == default
    for pid in RESTORE[sid]:
        prompt = source_prompt(sid, pid)
        got = pack_payloads(sid, preset_id=pid, prompt=prompt, attempted=default)
        assert sizes(got) == default, (pid, sizes(got))
        hint = run_hint(sid, preset_id=pid)
        assert "ratio=9:21" in hint and "880" in hint and "2048" in hint
        assert "ratio=9:16" not in hint
        assert "exactly 3" not in hint
    instructions = report()["runtime"][sid]["instructions"]
    assert "9:16" not in instructions and "三屏" not in instructions
    assert "9:19.5" not in instructions, instructions
    assert "2-4" not in instructions and "2–4" not in instructions, instructions

    sid = "web-product-visual-design"
    default = list(DEFAULT_PACKS[sid])
    assert sizes(pack_payloads(sid)) == default
    source = {p["id"]: p for p in report()["sourcePresets"][sid]}
    for pid, row in source.items():
        blob = f"{row['zh']} {row['en']} {row['prompt']}"
        if pid == "responsive":
            assert "reflow" in row["prompt"].lower() or "重排" in blob
            assert CROP_SAME.search(blob) is None, f"responsive must be layout reflow, not crop/scale: {blob}"
        got = pack_payloads(sid, preset_id=pid, prompt=row["prompt"], attempted=default)
        assert sizes(got) == default, (pid, sizes(got))
        assert got[0]["count"] == 1 and got[0]["refs"] == ["shape:ref-992"]
    instructions = report()["runtime"][sid]["instructions"]
    assert CROP_SAME.search(instructions) is None, instructions

    sid = "marketing-campaign-generator"
    default = list(DEFAULT_PACKS[sid])
    assert source_ids(sid)[1] == "rednote-cover-maker"
    assert sizes(pack_payloads(sid)) == default
    for pid in RESTORE[sid]:
        prompt = source_prompt(sid, pid)
        got = pack_payloads(sid, preset_id=pid, prompt=prompt, attempted=default)
        assert sizes(got) == default, (pid, sizes(got))
        hint = run_hint(sid, preset_id=pid)
        assert "ratio=16:9" in hint and "ratio=4:5" in hint and "ratio=9:16" in hint
        assert "exactly 3 separate images" in hint or "exactly 3" in hint


@needs_node
def test_rollback_ratio_mapping_turns_payload_assertions_red(monkeypatch):
    """Real seam rollback: dropping the #992 preset→#994 mapping leaves the mixed pack."""
    from ComfyArt.bot import skill_output as so
    monkeypatch.setattr(so, "ratio_from_example_preset_992", lambda *a, **k: None)
    sid = "meta-ads-creative-director"
    got = pack_payloads(sid, preset_id="feed1x1", prompt=source_prompt(sid, "feed1x1"),
                        attempted=DEFAULT_PACKS[sid])
    with pytest.raises(AssertionError):
        assert sizes(got) == uniform("1:1", 3)
    assert sizes(got) == list(DEFAULT_PACKS[sid])


def test_lock_template_id_does_not_swallow_trailing_period():
    """A sentence period after template=id must not become part of the preset id."""
    from ComfyArt.bot.skill_output import preset_from_text, run_hint, ratio_from_example_preset_992
    hint = run_hint("meta-ads-creative-director", "", None, preset_id="feed1x1")
    assert preset_from_text(hint) == "feed1x1"
    stale = ("Output lock: the user explicitly requested ratio 1:1; every IMAGE call uses "
             "width=1024 height=1024 ratio=1:1 count=1 skill='meta-ads-creative-director' "
             "template=feed1x1. Keep this skill's delivery count 3..3.")
    assert preset_from_text(stale) == "feed1x1"
    assert ratio_from_example_preset_992("meta-ads-creative-director", "feed1x1.") == "1:1"


@needs_node
def test_reintroducing_removed_applyRaw748_exceptions_turns_no_chip_assertion_red():
    """Reverse mutation: putting the five exceptions back must fail the same no-chip acceptance."""
    src = (ROOT / "src/skillRaw748.ts").read_text(encoding="utf-8")
    mutated = reintroduce_removed_applyRaw748_exceptions(src)
    # Keep the mutant beside the original so its relative ./data imports still resolve.
    mutant = ROOT / "src" / "skillRaw748.mutation992.ts"
    mutant.write_text(mutated, encoding="utf-8")
    try:
        r = _bundle_report(skill_raw=mutant.resolve(), tag="mutant")
        with pytest.raises(AssertionError):
            assert_default_runtime_has_no_chips(r["runtime"])
        # Proof the failure is the reintroduced chips, not an unconditional throw.
        for sid, ids in RESTORE.items():
            assert runtime_ids(sid, r["runtime"]) == list(ids), sid
            assert r["runtime"][sid].get("presetChips") is True, sid
        # Logo and other no-template example cards must stay empty under the same mutation.
        assert runtime_ids(LOGO, r["runtime"]) == []
        assert not r["runtime"][LOGO].get("presetChips")
    finally:
        mutant.unlink(missing_ok=True)
