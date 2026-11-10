"""#707: skill canvases declare real pixels, single-image skills take one generate_image,
and multi-shot calls differ by prompt so the #706 identical-call guard still stops true repeats.

No WaveSpeed call. Sizes are filled in the agent loop with a scripted model and a fake MCP.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ComfyArt.api.bot_send import compose_provider_text
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.guide import AGENT_GUIDE
from ComfyArt.bot.skill_output import OUTPUTS, apply_generate, run_hint, single_image_skip
from tests.test_agent_budget_391 import Rig, calls, reply, stop_of

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")


def _instr(sid: str) -> str:
    m = re.search(rf"\{{ id: '{sid}'.*?instructions: '(.*?)',\n", SKILLS, re.S)
    assert m, sid
    return m.group(1)


def test_declared_sizes():
    assert OUTPUTS["before-after"] == {"width": 1024, "height": 1280, "ratio": "4:5", "images": 1,
                                       "names": OUTPUTS["before-after"]["names"]}
    assert (OUTPUTS["before-after"]["width"], OUTPUTS["before-after"]["height"], OUTPUTS["before-after"]["ratio"]) == (1024, 1280, "4:5")
    assert (OUTPUTS["pose-fission"]["width"], OUTPUTS["pose-fission"]["height"], OUTPUTS["pose-fission"]["ratio"]) == (1536, 2048, "3:4")
    assert (OUTPUTS["game-art"]["width"], OUTPUTS["game-art"]["height"], OUTPUTS["game-art"]["ratio"]) == (1024, 1824, "9:16")
    assert (OUTPUTS["linkedin-banner"]["width"], OUTPUTS["linkedin-banner"]["height"]) == (1584, 396)
    assert "ratio" not in OUTPUTS["linkedin-banner"]
    assert OUTPUTS["linkedin-banner"]["images"] == 1 and OUTPUTS["pose-fission"]["images"] == 4


def test_ts_table_matches_python():
    block = re.search(r"export const SKILL_OUTPUT[\s\S]*?\n\}", SKILLS).group(0)
    for sid, row in OUTPUTS.items():
        assert f"'{sid}'" in block
        assert f"width: {row['width']}" in block and f"height: {row['height']}" in block
        assert f"images: {row['images']}" in block
        if row.get("ratio"):
            assert f"ratio: '{row['ratio']}'" in block
    assert "output } : {})" in SKILLS or "output } : {} }" in SKILLS


def test_apply_fills_from_display_name_and_leaves_other_skills():
    bare = apply_generate({"prompt": "cat", "ratio": "1:1"})
    assert bare == {"prompt": "cat", "ratio": "1:1"}
    custom = apply_generate({"skill": "poster", "prompt": "x", "ratio": "1:1"}, "LinkedIn Banner")
    assert custom == {"skill": "poster", "prompt": "x", "ratio": "1:1"}
    ba = apply_generate({"prompt": "x"}, "前后对比视觉")
    assert ba["skill"] == "before-after" and (ba["width"], ba["height"], ba["ratio"], ba["count"]) == (1024, 1280, "4:5", 1)
    assert ba["size_lock"] is True
    game = apply_generate({"prompt": "key art", "skill": "game-art", "ratio": "1:1", "width": 1024, "height": 1024, "count": 3})
    assert (game["width"], game["height"], game["ratio"], game["count"]) == (1024, 1824, "9:16", 1)
    assert game["size_lock"] is True
    pose = apply_generate({"prompt": "turn"}, "电商同场景角色姿势裂变")
    assert pose["skill"] == "pose-fission" and (pose["width"], pose["height"], pose["ratio"], pose["count"]) == (1536, 2048, "3:4", 1)
    assert pose["size_lock"] is True
    banner = apply_generate({"prompt": "banner", "ratio": "16:9", "width": 1820, "height": 1024}, "LinkedIn Banner")
    assert banner["skill"] == "linkedin-banner"
    assert (banner["width"], banner["height"], banner["count"]) == (1584, 396, 1)
    assert "ratio" not in banner
    assert banner["size_lock"] is True


def test_single_image_skip_does_not_touch_pose_or_the_first_generate():
    assert single_image_skip("list_models", "pose-fission", "zh", 0) is None
    assert single_image_skip("generate_image", "LinkedIn Banner", "zh", 0) is None
    assert single_image_skip("generate_image", "linkedin-banner", "en", 0) is None
    second = single_image_skip("generate_image", "LinkedIn横幅", "zh", 1)
    assert second and "1 次" in second and "[non-retryable]" not in second
    listed = single_image_skip("list_models", "linkedin-banner", "zh", 0)
    assert listed and "list_models" in listed
    assert "expand_image" in (single_image_skip("expand_image", "game-art", "en", 0) or "")
    assert "create_frame" in (single_image_skip("create_frame", "before-after", "zh", 0) or "")


def test_templates_lock_layout_and_pixels():
    ba, pose, game, banner = (_instr(s) for s in ("before-after", "pose-fission", "game-art", "linkedin-banner"))
    assert "ONE comparison card" in ba and "1024" in ba and "1280" in ba and "4:5" in ba
    assert "separate portraits" in ba and "list_models" in ba
    assert "1536" in pose and "2048" in pose and "3:4" in pose and "different pose and angle" in pose
    assert "white backdrop" in pose and "one generate_image call per plan line" in pose
    assert "title bar" in game and "bottom navigation" in game and "1024" in game and "1824" in game
    assert "not key art" in game.lower() or "not key art" in game
    assert "standalone illustration" in game and "9:16" in game
    assert "1584" in banner and "396" in banner and "list_models" in banner and "readable" in banner.lower() or "real words" in banner
    assert "right two thirds" in banner
    for text in (ba, pose, game, banner):
        assert "you are a production" in text.lower()
        assert "lovart" not in text.lower() and "demo" not in text.lower()
    assert "Style: one 9:16 mobile game UI" in SKILLS
    assert "Style: one 4:5 comparison card 1024x1280" in SKILLS
    assert "1584x396" in AGENT_GUIDE and "1024x1824" in AGENT_GUIDE
    hint = run_hint("LinkedIn Banner")
    assert "width=1584" in hint and "height=396" in hint and "exactly once" in hint
    sent = compose_provider_text("Banner for a data engineer", skill_name="LinkedIn Banner")
    assert "action='read'" in sent and hint in sent
    from ComfyArt.bot.self_check import parse_goal
    # The lock line must not invent an image goal the mock/self-check would then demand.
    assert parse_goal(sent) is None


def test_generate_image_schema_accepts_pixels():
    props = canvas.SPECS["generate_image"]["inputSchema"]["properties"]
    assert props["width"]["type"] == "integer" and props["height"]["type"] == "integer"
    assert "1584x396" in canvas.SPECS["generate_image"]["description"]
    src = (ROOT / "src/botCommands.ts").read_text(encoding="utf-8")
    gen = (ROOT / "src/generate.ts").read_text(encoding="utf-8")
    assert "pixelSize" in src and "pixelSizeOf" in gen
    assert "exactW" in src and "nearestRatio" in src


@pytest.fixture
def store():
    from ComfyArt.api.run_store_sqlite import SqliteRunStore
    from ComfyArt.bot.run_store import set_run_store
    saved = SqliteRunStore()
    set_run_store(saved)
    yield saved
    set_run_store(None)


def _mcp(name, args, i):
    import json
    if name == "skill":
        return json.dumps({"id": "linkedin-banner", "instructions": "1584x396"})
    if name == "generate_image":
        return json.dumps({"ids": [f"job{i}"], "width": args.get("width"), "height": args.get("height")})
    return json.dumps({"id": f"shape:{i}"})


async def test_linkedin_real_path_is_one_generate_at_banner_size(monkeypatch, store):
    script = [calls(("skill", {"action": "read", "name": "LinkedIn Banner"})),
              calls(("generate_image", {"prompt": "data engineer banner"})),
              calls(("wait_generation", {"ids": ["job2"]})), reply("完成")]
    r = Rig(monkeypatch, script, store=store, mcp=_mcp)
    res, events = await r.send(compose_provider_text("Banner for a data engineer", skill_name="LinkedIn Banner"))
    assert stop_of(res)["reason"] == "done", stop_of(res)
    assert [c[0] for c in r.mcp] == ["skill", "generate_image", "wait_generation"]
    gen = r.mcp[1][1]
    assert (gen["width"], gen["height"], gen["skill"], gen["count"]) == (1584, 396, "linkedin-banner", 1)
    assert "ratio" not in gen
    assert r.n <= 10
    assert len([e for e in events if e.t == "tool_use"]) <= 10


async def test_linkedin_skips_list_models_expand_and_a_second_generate(monkeypatch, store):
    script = [calls(("list_models", {"type": "image"})),
              calls(("expand_image", {"id": "shape:1", "right": 200})),
              calls(("create_frame", {"width": 1820, "height": 1024})),
              calls(("generate_image", {"prompt": "wide", "ratio": "16:9", "width": 1820, "height": 1024})),
              calls(("generate_image", {"prompt": "again"})),
              calls(("wait_generation", {"ids": ["job4"]})), reply("完成")]
    r = Rig(monkeypatch, script, store=store, mcp=_mcp)
    res, events = await r.send(compose_provider_text("Banner", skill_name="LinkedIn Banner"))
    assert stop_of(res)["reason"] == "done", stop_of(res)
    names = [c[0] for c in r.mcp]
    assert names == ["generate_image", "wait_generation"], names
    assert (r.mcp[0][1]["width"], r.mcp[0][1]["height"]) == (1584, 396)
    assert "ratio" not in r.mcp[0][1]
    assert r.n <= 10
    texts = [e.text for e in events if e.t == "tool_result"]
    assert any("list_models" in t for t in texts)
    assert any("1 次" in t for t in texts)


def test_before_after_template_has_no_default_side_profile():
    ba = _instr("before-after")
    assert "Do not default to a 45° or 90° side profile" in ba
    assert "mostly frontal or near-frontal" in ba
    assert "Default to a 45° or 90° side profile" not in ba


def test_pose_fission_template_changes_only_pose_and_angle():
    pose = _instr("pose-fission")
    assert "change only pose and angle" in pose
    assert "change ONLY camera angle and framing" not in pose
    assert "camera angle and framing" not in pose
    assert "shot size" not in pose.lower()


def test_game_art_template_requires_bottom_nav_only_on_home_and_list_pages():
    game = _instr("game-art")
    assert "bottom navigation is required on home and list pages" in game
    assert "may omit the bottom nav" in game


def test_game_art_template_locks_brand_tingchao_and_go_only():
    game = _instr("game-art")
    assert "The game name must be exactly 「听潮弈社」" in game
    assert "never write 「听潮奔社」" in game
    assert "Guard against 奔 leaking" in game
    assert "Go (围棋) game only" in game
    assert "xiangqi / 象棋" in game
    assert "帅" in game and "将" in game
    assert "playing cards" in game and "牌缘" in game and "扑克" in game
    assert "Invent a new game name" not in game


def test_linkedin_banner_template_keeps_avatar_safe_area_empty():
    banner = _instr("linkedin-banner")
    assert "leave the avatar safe area EMPTY" in banner
    assert "no face" in banner
    # Personal preset also keeps the safe area empty.
    assert "avatar safe area empty (no face drawn there)" in SKILLS
