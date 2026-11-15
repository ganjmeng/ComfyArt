"""#992 reproduction: example-card presets must reach #978 agent input and mock submit.

applyRaw748 currently clears presets on every kind=example skill. Product ruling
https://github.com/ganjmeng/ComfyArt/issues/992#issuecomment-6888538718:

* logo-material-explorer is an intentional no-template skill (keep #996 defaults,
  do not restore deleted P(), delete leftover "per selected preset" copy).
* Five skills must restore their existing options so a real selection enters the
  #978 send body and survives into the mock generate_image payload — not title or
  thumbnail only. Counts, refs and models stay unchanged. Kind stays example.

These tests are expected to fail on current main until that restore lands. $0, no
paid calls, no network except local node bundling of src/.
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
# Selecting these options is an explicit ratio choice and must enter the #994 chain.
RATIO_OPTIONS = {
    ("meta-ads-creative-director", "feed1x1"): "1:1",
    ("meta-ads-creative-director", "feed4x5"): "4:5",
    ("meta-ads-creative-director", "story9x16"): "9:16",
    ("rednote-cover-maker", "ugc-feed"): "1:1",
    ("rednote-cover-maker", "ugc-story"): "9:16",
}
STYLE_ONLY = {
    ("meta-ads-creative-director", "ugc"),
    ("mobile-app-visual-design", "home"),
    ("mobile-app-visual-design", "detail"),
    ("mobile-app-visual-design", "checkout"),
    ("mobile-app-visual-design", "onboarding"),
    ("web-product-visual-design", "hero"),
    ("web-product-visual-design", "features"),
    ("web-product-visual-design", "pricing"),
    ("web-product-visual-design", "responsive"),
    ("marketing-campaign-generator", "kv"),
    ("marketing-campaign-generator", "rednote-cover-maker"),
    ("marketing-campaign-generator", "display"),
    ("marketing-campaign-generator", "ooh"),
}
DEAD_PRESET_COPY = re.compile(r"per selected preset", re.I)
CROP_SAME = re.compile(
    r"responsive crop|响应式裁切|crop of the same|scale of the same|裁剪同一|缩放同一",
    re.I,
)


@lru_cache(maxsize=1)
def report() -> dict:
    out = Path(os.environ.get("TMPDIR", "/tmp")) / f"preset992-{os.getpid()}.mjs"
    env = {**os.environ, "OUT": str(out), "CA992_ROOT": str(ROOT)}
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/preset992/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True, env=env,
    )
    proc = subprocess.run(
        ["node", str(out)], capture_output=True, text=True, timeout=60, env=env, cwd=ROOT,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


def source_ids(sid: str) -> list[str]:
    return [p["id"] for p in report()["sourcePresets"].get(sid, [])]


def source_prompt(sid: str, pid: str) -> str:
    return next(p["prompt"] for p in report()["sourcePresets"][sid] if p["id"] == pid)


def runtime_ids(sid: str) -> list[str]:
    return [p["id"] for p in (report()["runtime"].get(sid) or {}).get("presets") or []]


def emptied_source_presets() -> dict[str, list[str]]:
    """Skills that still declare P() in src/skills.ts but lose them after applyRaw748."""
    lost: dict[str, list[str]] = {}
    for sid, rows in report()["sourcePresets"].items():
        declared = [p["id"] for p in rows]
        if not declared:
            continue
        kept = set(runtime_ids(sid))
        missing = [pid for pid in declared if pid not in kept]
        if missing:
            lost[sid] = missing
    return lost


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


@needs_node
def test_inventories_register_intentional_empty_and_forbid_unregistered_clearing():
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
    assert source_ids(LOGO) == [], "do not restore deleted logo P() templates"
    # Inventory (b): the five restored skills must no longer be silently emptied.
    for sid, ids in RESTORE.items():
        assert source_ids(sid) == list(ids), (sid, source_ids(sid))
        assert runtime_ids(sid) == list(ids), (
            f"{sid} still lost its P() options at applyRaw748 runtime: {runtime_ids(sid)}"
        )
        assert r["runtime"][sid]["kind"] == "example", "do not change kind to template"
        assert r["runtime"][sid]["examples"], f"{sid} must keep the original example area"
    unexpected = {sid: pids for sid, pids in lost.items()
                  if sid not in RESTORE and sid not in INTENTIONAL_NO_TEMPLATE}
    assert unexpected == {}, f"unregistered applyRaw748 emptying: {unexpected}"
    # The five restored skills are exactly the registered emptying that this card must undo.
    assert set(lost) <= (set(RESTORE) | set(INTENTIONAL_NO_TEMPLATE))
    assert not any(sid in lost for sid in RESTORE), lost


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
    # Selecting a leftover template must not start working again.
    assert r["presets"] == []
    assert LOGO not in report()["deliveries"]


@needs_node
@pytest.mark.parametrize("sid,pid", [(s, p) for s, ids in RESTORE.items() for p in ids])
def test_restored_option_reaches_978_agent_input(sid, pid):
    delivery = report()["deliveries"][sid][pid]
    assert delivery["ok"] is True, delivery
    payload = delivery["payload"]
    assert payload["preset"]["id"] == pid
    prompt = payload["preset"]["prompt"]
    assert prompt and prompt == delivery["expectedPrompt"]
    assert prompt.startswith("Style:")
    # Not a title/thumbnail-only restore: the Style prompt is in the real send body.
    assert "{{" not in prompt
    context = compose_provider_text(delivery["ask"], skill_name=sid,
                                    preset_prompt=prompt, preset_id=pid)
    assert prompt in context
    assert "Selected template instructions" in context
    # Kind stays example; example images are not sent as if they were Lovart templates.
    assert report()["runtime"][sid]["kind"] == "example"


@needs_node
def test_meta_ratio_templates_submit_that_ratio_on_every_image_ugc_does_not():
    sid = "meta-ads-creative-director"
    default = DEFAULT_PACKS[sid]
    assert sizes(pack_payloads(sid)) == list(default)
    for pid, ratio in (("feed1x1", "1:1"), ("feed4x5", "4:5"), ("story9x16", "9:16")):
        prompt = source_prompt(sid, pid)
        # Even if the model still emits the old mixed pack, the selected ratio wins.
        got = pack_payloads(sid, preset_id=pid, prompt=prompt, attempted=default)
        assert sizes(got) == uniform(ratio, 3), (pid, sizes(got))
        assert all(row["count"] == 1 and row["refs"] == ["shape:ref-992"] and "model" not in row for row in got)
        hint = run_hint(sid, preset_id=pid)
        assert f"ratio={ratio}" in hint
        # The lock must not keep advertising the unselected pack ratios as the plan.
        for other in ("1:1", "4:5", "9:16"):
            if other != ratio:
                assert f"ratio={other}" not in hint, (pid, hint)
    # UGC is style only — default three-ratio pack, no secret ratio rewrite.
    ugc_prompt = next(p["prompt"] for p in report()["sourcePresets"][sid] if p["id"] == "ugc")
    ugc = pack_payloads(sid, preset_id="ugc", prompt=ugc_prompt, attempted=default)
    assert sizes(ugc) == list(default)
    assert "Style:" in ugc_prompt and not any(tag in ugc_prompt for tag in ("1:1", "4:5", "9:16"))


@needs_node
def test_rednote_templates_are_1x1_and_9x16_and_explicit_ratio_keeps_count():
    sid = "rednote-cover-maker"
    assert source_ids(sid) == ["ugc-feed", "ugc-story"]  # no third template
    assert sizes(pack_payloads(sid)) == list(DEFAULT_PACKS[sid])
    for pid, ratio in (("ugc-feed", "1:1"), ("ugc-story", "9:16")):
        prompt = source_prompt(sid, pid)
        got = pack_payloads(sid, preset_id=pid, prompt=prompt, attempted=DEFAULT_PACKS[sid])
        assert sizes(got) == uniform(ratio, 3), (pid, sizes(got))
        assert all(row["count"] == 1 and row["refs"] == ["shape:ref-992"] for row in got)
    # 4:5 remains available by explicit user wording; count stays three.
    named = pack_payloads(sid, user_text="请全部做成 4:5，不要改张数。")
    assert sizes(named) == uniform("4:5", 3)


@needs_node
def test_mobile_page_presets_do_not_change_two_screen_921_contract():
    sid = "mobile-app-visual-design"
    default = list(DEFAULT_PACKS[sid])
    assert sizes(pack_payloads(sid)) == default
    for pid in RESTORE[sid]:
        prompt = source_prompt(sid, pid)
        got = pack_payloads(sid, preset_id=pid, prompt=prompt, attempted=default)
        assert sizes(got) == default, (pid, sizes(got))
        assert all(row["count"] == 1 and row["refs"] == ["shape:ref-992"] for row in got)
        hint = run_hint(sid, preset_id=pid)
        assert "ratio=9:21" in hint and "880" in hint and "2048" in hint
        assert "ratio=9:16" not in hint
        assert "exactly 3" not in hint
    instructions = report()["runtime"][sid]["instructions"]
    assert "9:16" not in instructions and "三屏" not in instructions
    assert "9:19.5" not in instructions, instructions
    assert "2-4" not in instructions and "2–4" not in instructions, instructions


@needs_node
def test_web_presets_keep_one_16x9_and_responsive_is_reflow_not_crop():
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


@needs_node
def test_campaign_presets_keep_three_image_pack_and_do_not_invent_ooh_pixels():
    sid = "marketing-campaign-generator"
    default = list(DEFAULT_PACKS[sid])
    assert source_ids(sid)[1] == "rednote-cover-maker"  # social extension keeps this preset id
    assert sizes(pack_payloads(sid)) == default
    for pid in RESTORE[sid]:
        prompt = source_prompt(sid, pid)
        got = pack_payloads(sid, preset_id=pid, prompt=prompt, attempted=default)
        assert sizes(got) == default, (pid, sizes(got))
        assert all(row["count"] == 1 and row["refs"] == ["shape:ref-992"] and "model" not in row for row in got)
        # OOH must not invent a new canvas; hint still describes the current pack only.
        hint = run_hint(sid, preset_id=pid)
        assert "ratio=16:9" in hint and "ratio=4:5" in hint and "ratio=9:16" in hint
        assert "exactly 3 separate images" in hint or "exactly 3" in hint


@needs_node
def test_explicit_user_ratio_is_not_stripped_as_a_system_default():
    """#994: an explicit later ratio still wins; a template ratio is user intent, not a default."""
    sid = "meta-ads-creative-director"
    prompt = next(p["prompt"] for p in report()["sourcePresets"][sid] if p["id"] == "feed1x1")
    # User later names 9:16 — latest explicit intent wins, count stays 3.
    got = pack_payloads(
        sid, preset_id="feed1x1", prompt=prompt,
        user_text="改成 9:16，三张都要这个比例。", attempted=DEFAULT_PACKS[sid],
    )
    assert sizes(got) == uniform("9:16", 3)
    # No selection + no named ratio keeps the default mixed pack (not stripped / not forced).
    assert sizes(pack_payloads(sid, user_text="做一套 Meta 广告。")) == list(DEFAULT_PACKS[sid])


@needs_node
def test_title_only_restore_would_still_fail_delivery():
    """Mutation lock: a runtime preset without a Style prompt must not count as restored."""
    clothing = report()["runtime"]["clothing-swap"]["presets"]
    assert any(p["prompt"].startswith("Style:") for p in clothing)
    for sid, ids in RESTORE.items():
        for pid in ids:
            delivery = report()["deliveries"][sid][pid]
            # Current main fails earlier (preset missing). Once present, prompt must be in the body.
            if delivery.get("reason") == "missing-runtime-preset":
                pytest.fail(f"{sid}/{pid} is still cleared by applyRaw748: {delivery}")
            assert delivery["payload"]["preset"]["prompt"].startswith("Style:")


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
    # Historical wording put a period immediately after the id; the recognizer must still be exact.
    stale = ("Output lock: the user explicitly requested ratio 1:1; every IMAGE call uses "
             "width=1024 height=1024 ratio=1:1 count=1 skill='meta-ads-creative-director' "
             "template=feed1x1. Keep this skill's delivery count 3..3.")
    assert preset_from_text(stale) == "feed1x1"
    assert ratio_from_example_preset_992("meta-ads-creative-director", "feed1x1.") == "1:1"
