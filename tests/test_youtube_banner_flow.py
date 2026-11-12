"""youtube-channel-banner flow (Lovart d7672d038e6705b2399981c0bb775c5406c7460e, skill pkBguW4KoU).

Card 1 (1 of 3) -> direction board (16:9 2k) -> card 2 (1 of 2) -> final. 精确排版 final:
text-free Sunburst base, then the server upscales to exactly 2560x1440 and sets the text
inside the YouTube safe areas with the bundled font (api/banner_compose.py).

$0: no WaveSpeed call. Request bodies come from the real relay with submit_command mocked
and from wavespeed.build_payload on the catalog fixture schema. Compositing runs on a
synthetic base image. The youtube-channel-banner Sunburst pin and the ratio-only 2k fill
land in #922; until then the relay test checks the 2048x1152 16:9 args this PR sends, and
after #922 it also checks the Sunburst ids.
"""
from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import re
import sys
import uuid
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from ComfyArt.api import banner_compose as bc
from ComfyArt.api import bot_asks, paid_guard, wavespeed
from ComfyArt.api.mcp_tools import banner, canvas
from ComfyArt.api.mcp_tools._context import GUARD_CHAT_ID

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"

STRICT = (642, 551, 1918, 889)
HARD = (482, 509, 2078, 931)
TARGET = (820, 610, 1740, 818)

# Lovart d7672d03 card text (notes.txt), verbatim.
CARD1 = [
    ("yt_delivery", "这次横幅想怎么交付？（影响后续步骤与文字精度）",
     ["先出三方向选择板，再做终稿", "直接出一张终稿，文字用精确排版渲染", "直接出一张终稿，文字由图像模型生成"],
     "其它想法（比如一次出多个方向终稿）..."),
    ("yt_banner_text", "横幅上实际要出现哪些文字？", None, "自己指定文案（含大小写、符号、换行）..."),
    ("yt_brand_assets", "有需要放进去的品牌资产吗？（Logo／头像／真人）",
     ["没有，纯图形＋文字构成识别", "有 Logo／头像，我上传给你", "需要预留真人出镜位置"],
     "其它（比如指定参考图／配色）..."),
]
CARD2 = [
    ("yt_direction", "选哪个方向做 2560×1440 终稿？", None, "想调整（说哪里改）或让我直接定..."),
    ("yt_text_mode", "终稿的文字怎么上？（中文＋三行信息，精度差异较大）", ["精确排版（推荐）", "图像模型直出"], "其它要求..."),
]
LIVE_TEXT = [
    {"id": "A", "label": "Loomi Studio ＋ AI 绘画教程·创意工作流 ＋ 每周二/五更新"},
    {"id": "B", "label": "Loomi Studio ＋ AI 绘画教程·创意工作流"},
    {"id": "C", "label": "只有 Loomi Studio"},
]
LIVE_DIRECTIONS = [
    {"id": "A", "label": "方向 A：品牌主导·大留白（推荐）", "description": "选择板顶部：最干净，缩到移动端也不丢信息", "recommended": True},
    {"id": "B", "label": "方向 B：全画幅叙事场景（推荐）", "description": "选择板中部：画面最丰富"},
    {"id": "C", "label": "方向 C：模块化工作流网格", "description": "选择板底部：最贴工作流主题"},
]


def _instructions() -> str:
    m = re.search(r"\{ id: 'youtube-channel-banner', name: t\('skills.youtubeChannelBanner'\), instructions: '((?:\\.|[^'\\])*)'", SKILLS)
    assert m, "youtube-channel-banner instructions did not parse"
    return m.group(1).replace("\\n", "\n").replace("\\'", "'").replace("\\\\", "\\")


# --- cards -------------------------------------------------------------------------------------------

def _assert_card(spec: dict, expected: list, page_count: int, live: dict) -> None:
    assert spec["page_count"] == page_count
    assert spec["allow_skip"] is True
    assert "defaults" not in spec
    assert [q["id"] for q in spec["questions"]] == [e[0] for e in expected]
    for q, (qid, prompt, labels, placeholder) in zip(spec["questions"], expected):
        assert q["prompt"] == prompt, qid
        assert q["page"] == 1, qid
        assert q["allow_other"] is True, qid
        assert q["placeholder"] == placeholder, qid
        assert "defaults" not in q, qid
        assert q["min_selections"] == 1 and q["max_selections"] == 1, qid  # single-select
        assert not any(o.get("recommended") for o in q["options"]), qid
        got = [o["label"] for o in q["options"]]
        assert got == (labels if labels is not None else live[qid]), qid


def test_card1_skeleton_is_exact_and_nothing_preselected():
    # What a model might send: wrong placeholders, a default, a recommended flag, an extra question.
    spec = bot_asks.validate_spec({
        "questions": [
            {"id": "x1", "prompt": "这次横幅想怎么交付？", "options": [{"id": "1", "label": "三方向"}, {"id": "2", "label": "终稿"}],
             "defaults": ["1"], "page": 2},
            {"id": "x2", "prompt": "横幅上实际要出现哪些文字？", "options": LIVE_TEXT + [{"id": "D", "label": "多余第四档"}]},
            {"id": "x3", "prompt": "有需要放进去的品牌资产吗？", "options": [{"id": "a", "label": "无", "recommended": True}, {"id": "b", "label": "有"}]},
            {"id": "gender", "prompt": "模特性别？", "options": [{"id": "a", "label": "女"}, {"id": "b", "label": "男"}]},
        ],
        "page_count": 4,
        "allow_skip": False,
    })
    _assert_card(spec, CARD1, 3, {"yt_banner_text": [o["label"] for o in LIVE_TEXT]})


def test_card2_skeleton_is_exact_and_recommended_is_description_prefix_only():
    # Short Q2 prompt must be restored to the full reference text including the bracket.
    # （推荐） in two labels + a recommended flag: move it to the start of the first description only.
    spec = bot_asks.validate_spec({
        "questions": [
            {"id": "direction", "prompt": "选哪个方向做 2560×1440 终稿？", "options": LIVE_DIRECTIONS},
            {"id": "text", "prompt": "终稿的文字怎么上？",
             "options": [{"id": "A", "label": "精确排版", "recommended": True}, {"id": "B", "label": "模型直出"}]},
        ],
    })
    labels = ["方向 A：品牌主导·大留白", "方向 B：全画幅叙事场景", "方向 C：模块化工作流网格"]
    _assert_card(spec, CARD2, 2, {"yt_direction": labels})
    directions = spec["questions"][0]["options"]
    assert [o["description"] for o in directions] == [
        "（推荐）选择板顶部：最干净，缩到移动端也不丢信息",
        "选择板中部：画面最丰富",
        "选择板底部：最贴工作流主题",
    ]
    assert sum(o["description"].startswith("（推荐）") for o in directions) == 1
    assert not any("（推荐）" in o["label"] for o in directions)
    assert not any(o.get("recommended") for o in directions)


def test_other_skill_cards_are_untouched():
    raw = {"questions": [{"id": "look", "prompt": "模特长相方向选哪一档？", "options": [{"id": "A", "label": "x"}, {"id": "B", "label": "y"}],
                          "defaults": ["A"]}], "page_count": 3}
    assert bot_asks.normalize_youtube_banner_card(raw) == raw


def test_skill_text_matches_card_skeleton_and_flow():
    instr = _instructions()
    for qid, prompt, labels, placeholder in CARD1 + CARD2:
        assert f'id "{qid}"' in instr and prompt in instr and placeholder in instr, qid
        for label in labels or []:
            assert f'label:"{label}"' in instr, label
    assert "page_count 3, so the header is 1 of 3" in instr
    assert "page_count 2, so the header is 1 of 2" in instr
    assert instr.index('id "yt_delivery"') < instr.index('id "yt_banner_text"') < instr.index('id "yt_brand_assets"') \
        < instr.index('banner_stage "board"') < instr.index('id "yt_direction"') < instr.index('id "yt_text_mode"') \
        < instr.index('banner_stage "base"') < instr.index("compose_banner_text") < instr.index('banner_stage "direct"')
    assert "Do not set defaults or recommended" in instr and "nothing is preselected" in instr
    assert 'skill: "youtube-channel-banner"' in instr
    assert "never put the banner copy or any quoted text in this prompt" in instr
    assert "no compositing and no fallback" in instr
    for needle in ("recommended: true", '"recommended"', "defaults: ["):
        assert needle not in instr
    # Card text is not in English-only wording, and the old one-shot brief is gone.
    assert "1) Brief: channel name, niche and series identity" not in instr
    assert 'Put "（推荐）" at the start of the description' in instr
    assert 'Append "（推荐）" to the label' not in instr
    assert "yt_shorten_copy" in instr and "dry-runs the 2560×1440 text layout" in instr
    assert "pass channel_name, tagline and schedule" in instr


# --- request bodies ($0) -----------------------------------------------------------------------------

SENT: list = []


@pytest.fixture
def relay(monkeypatch):
    SENT.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        return {"ids": ["shape:g1"], "model": args.get("edit_model") or args.get("model")}

    async def no_approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)


def _run(*, lang: str | None = None, goal_text: str = "", **args):
    chat = paid_guard.noturn_key(f"ytb-{uuid.uuid4().hex}")
    token = GUARD_CHAT_ID.set(chat)
    try:
        if lang is not None:
            paid_guard.begin_turn(chat, text=goal_text, provider_text="", lang=lang)
        return asyncio.run(canvas.TOOLS["generate_image"]["handler"](args))
    finally:
        GUARD_CHAT_ID.reset(token)
        paid_guard.TURNS.pop(chat, None)


def _schema(mid: str) -> dict:
    return FIXTURE[mid]["api_schema"]["api_schemas"][0]["request_schema"]


@pytest.mark.parametrize("stage,clause", [("board", bc.BOARD_CLAUSE), ("base", bc.BASE_CLAUSE), ("direct", bc.DIRECT_CLAUSE)])
@pytest.mark.parametrize("refs", [None, ["shape:logo"]])
def test_stage_request_bodies(relay, stage, clause, refs):
    args = {"prompt": 'Bright watercolor brand world, brand blue #2F6BFF, coral accents, copy "Loomi Studio"',
            "skill": "youtube-channel-banner", "banner_stage": stage, "count": 3, "width": 1024, "height": 1024, "ratio": "1:1",
            "channel_name": "Loomi Studio", "tagline": "AI 绘画教程 · 创意工作流", "schedule": "每周二 / 周五更新"}
    if refs:
        args["refs"] = refs
    out = _run(**args)
    assert out.get("status") != "failed", out
    assert len(SENT) == 1 and SENT[0][0] == "generate_image"
    sent = SENT[0][1]
    assert "banner_stage" not in sent and "skill" not in sent
    assert "channel_name" not in sent and "tagline" not in sent and "schedule" not in sent
    assert sent["ratio"] == "16:9" and sent["count"] == 1
    assert sent["prompt"].endswith(clause)
    if stage == "base":
        assert "Loomi Studio" not in sent["prompt"]  # no quoted copy on the text-free plate
        assert "absolutely NO text of any kind" in sent["prompt"] and "fake UI" in sent["prompt"]
    else:
        assert '"Loomi Studio"' in sent["prompt"]
    from ComfyArt.api.auto_models import skill_pin
    if skill_pin("youtube-channel-banner"):
        # After #922 (main 30ade316): Sunburst (edit with a ref), ratio-only 2k: aspect_ratio + resolution,
        # no width/height on the page args (Sunburst takes no size).
        if refs:
            assert sent["edit_model"] == SUNBURST_EDIT
        else:
            assert sent["model"] == SUNBURST_T2I and "edit_model" not in sent
        assert sent.get("edit_resolution") == "2k"
        assert "width" not in sent and "height" not in sent
    else:
        assert (sent["width"], sent["height"]) == (2048, 1152)
    model = sent.get("edit_model") or (SUNBURST_EDIT if refs else SUNBURST_T2I)
    model = model if model in (SUNBURST_T2I, SUNBURST_EDIT) else SUNBURST_T2I
    inputs = {"prompt": sent["prompt"], "ratio": sent["ratio"],
              **({"width": sent["width"], "height": sent["height"]} if "width" in sent else {}),
              **({"resolution": sent["edit_resolution"]} if sent.get("edit_resolution") else {})}
    body = asyncio.run(wavespeed.build_payload(None, _schema(model), inputs, model))
    assert body["aspect_ratio"] == "16:9"
    assert body["resolution"] == "2k"
    assert body["prompt"] == sent["prompt"]


def test_unknown_stage_is_refused_before_submit(relay):
    out = _run(prompt="x", skill="youtube-channel-banner", banner_stage="poster")
    assert out["status"] == "failed" and SENT == []


def test_stage_is_ignored_for_other_skills():
    args = {"prompt": "x", "skill": "studio-model", "banner_stage": "base", "ratio": "3:4"}
    assert bc.stage_args(args) == {"prompt": "x", "skill": "studio-model", "ratio": "3:4"}


def test_generate_image_schema_and_tool_registry():
    from ComfyArt.api.mcp_tools import TOOLS
    from ComfyArt.bot.guide import CORE_MCP_TOOLS, PAID_TOOLS
    props = canvas.TOOLS["generate_image"]["inputSchema"]["properties"]
    assert props["banner_stage"]["enum"] == ["board", "base", "direct"]
    for key in ("channel_name", "tagline", "schedule"):
        assert props[key]["type"] == "string"
    assert "compose_banner_text" in TOOLS and "compose_banner_text" in CORE_MCP_TOOLS
    assert "compose_banner_text" not in PAID_TOOLS  # no model call, no charge


# --- compositing lock --------------------------------------------------------------------------------

def _synthetic_base(w: int = 2048, h: int = 1152) -> bytes:
    """Light paper background, one blue/coral graphic right of the middle band (like Lovart's base)."""
    img = Image.new("RGB", (w, h), (250, 247, 240))
    d = ImageDraw.Draw(img)
    sx, sy = w / 2560, h / 1440
    d.ellipse((1800 * sx, 560 * sy, 2050 * sx, 880 * sy), fill=(47, 107, 255))
    d.rectangle((1930 * sx, 640 * sy, 2040 * sx, 800 * sy), fill=(255, 122, 89))
    d.ellipse((150 * sx, 120 * sy, 600 * sx, 330 * sy), fill=(236, 240, 252))  # soft TV-area texture
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


CASES = {
    "short": ("Loomi Studio", "AI 绘画教程 · 创意工作流", "每周二 / 周五更新"),
    "long": ("Loomi Studio 创意工作室官方频道", "AI 绘画教程 · 创意工作流 · Stable Diffusion / ComfyUI / Midjourney 全流程实战",
             "每周二、周五晚上 8 点更新，周末不定期直播答疑"),
    "unbreakable_latin": ("Supercalifragilisticexpialidocious_ChannelName_WithNoSpacesAtAll_2026",
                          "Tutorials-and-workflows-without-any-break-opportunity-for-the-wrapper", "Tue/Fri"),
    "channel_only": ("只有 Loomi Studio", "", ""),
}

# Fits width if hierarchy is ignored, but cannot keep title ink the largest at the 36px floors.
VERY_LONG_COPY = (
    "Loomi Studio 创意工作室官方频道 Creative Workflow Lab International Edition",
    "AI 绘画教程 · 创意工作流 · Stable Diffusion / ComfyUI / Midjourney / Flux / Krea 全流程实战，从零基础到商业交付的完整课程体系",
    "每周二、周五晚上 8 点更新，周末不定期直播答疑，会员专属工作流模板每月更新一次（北京时间）",
)


def _inside(b, box) -> bool:
    return b[0] >= box[0] and b[1] >= box[1] and b[2] <= box[2] and b[3] <= box[3]


@pytest.mark.parametrize("case", sorted(CASES))
def test_compositing_lock_ink_inside_strict_core_and_hard_boundary(case):
    channel, tagline, schedule = CASES[case]
    base = _synthetic_base()
    png, rep = bc.compose(base, channel=channel, tagline=tagline, schedule=schedule, brand_color="#2F6BFF",
                          skill="youtube-channel-banner", purpose=bc.PURPOSE_USER_FINAL)
    out = Image.open(io.BytesIO(png))
    assert out.size == (2560, 1440) and (rep["width"], rep["height"]) == (2560, 1440)
    # Every line's ink box (measured on its rendered pixels) is inside both areas.
    roles = [r["role"] for r in rep["lines"]]
    assert roles[0] == "channel"
    for r in rep["lines"]:
        assert _inside(r["ink_bbox"], STRICT), (case, r)
        assert _inside(r["ink_bbox"], HARD), (case, r)
    assert rep["all_inside_strict_core"] and rep["all_inside_hard_boundary"]
    # Independent pixel check: everything that differs from the upscaled base is inside the strict core.
    ref = Image.open(io.BytesIO(base)).convert("RGB").resize((2560, 1440), Image.LANCZOS)
    diff = np.abs(np.asarray(out.convert("RGB"), dtype=np.int16) - np.asarray(ref, dtype=np.int16)).sum(axis=2) > 0
    ys, xs = np.nonzero(diff)
    assert len(xs), case
    assert _inside((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), STRICT), case
    # Nothing is clipped or dropped: the wrapped rows join back to the input text.
    for role, text in (("channel", channel), ("tagline", tagline), ("schedule", schedule)):
        rows = [r["text"] for r in rep["lines"] if r["role"] == role]
        squash = lambda s: re.sub(r"\s+", "", s)
        assert squash("".join(rows)) == squash(text), (case, role)
    # Left-aligned at the target box's left edge; the text does not cover the base graphic.
    for r in rep["lines"]:
        if r["role"] != "accent":
            assert TARGET[0] <= r["ink_bbox"][0] <= TARGET[0] + 12, (case, r)
    assert rep["graphic_overlap"] == 0.0 and rep["text_area_clear"]


def test_short_text_ink_sits_in_the_lovart_target_box_with_size_hierarchy():
    _, rep = bc.compose(_synthetic_base(), channel="Loomi Studio", tagline="AI 绘画教程 · 创意工作流", schedule="每周二 / 周五更新",
                        skill="youtube-channel-banner", purpose=bc.PURPOSE_USER_FINAL)
    by = {r["role"]: r for r in rep["lines"]}
    for r in rep["lines"]:
        assert _inside(r["ink_bbox"], TARGET), r
    assert by["channel"]["px"] > by["tagline"]["px"] > by["schedule"]["px"]
    assert by["channel"]["ink_bbox"][3] < by["tagline"]["ink_bbox"][1] < by["accent"]["ink_bbox"][1] < by["schedule"]["ink_bbox"][1]
    assert rep["wrapped"] is False


@pytest.mark.parametrize("size", [(2048, 1152), (1664, 936), (1536, 1024)])
def test_output_is_exactly_2560x1440_for_any_base(size):
    png, rep = bc.compose(_synthetic_base(*size), channel="Loomi Studio", skill="youtube-channel-banner",
                          purpose=bc.PURPOSE_USER_FINAL)
    assert Image.open(io.BytesIO(png)).size == (2560, 1440)
    assert rep["base_size"] == list(size)


def test_glyphs_the_font_cannot_draw_fail_instead_of_tofu():
    with pytest.raises(bc.LayoutError):
        bc.compose(_synthetic_base(), channel="Loomi 🎨", skill="youtube-channel-banner", purpose=bc.PURPOSE_USER_FINAL)


def test_bundled_font_is_ofl_renamed_and_draws_chinese():
    from PIL import ImageFont
    ofl = (ROOT / "api/fonts/OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in ofl and "Reserved Font Name 'Source'" in ofl
    for path, style in ((bc.FONT_BOLD, "Bold"), (bc.FONT_REGULAR, "Regular")):
        # Modified OFL font: renamed, not "Noto" / "Source".
        assert ImageFont.truetype(str(path), 20).getname() == ("ComfyArt Banner Sans SC", style)
    assert bc.missing_glyphs("Loomi Studio AI 绘画教程 · 创意工作流 每周二 / 周五更新（）、，。＋频道") == []
    assert bc.missing_glyphs("Loomi 🎨 \U00020000") == ["🎨", "\U00020000"]


def test_bundled_font_is_not_referenced_from_frontend_src_or_dist():
    needles = ("api/fonts", "ComfyArtBannerSansSC")
    files = []
    for rel in ("src", "dist"):
        root = ROOT / rel
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file())
    for cfg in (ROOT / "vite.config.ts", ROOT / "tests/js/rolldown.config.mjs",
                ROOT / "tests/js/rolldown.error721.mjs", ROOT / "tests/js/rolldown.objerr.mjs"):
        if cfg.exists():
            files.append(cfg)
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in needles:
            assert needle not in text, f"{path.relative_to(ROOT)} references {needle}"


def _ink_heights(rep, role: str) -> list[int]:
    return [r["ink_bbox"][3] - r["ink_bbox"][1] for r in rep["lines"] if r["role"] == role]


def _schedule_ink_heights(rep) -> list[int]:
    return _ink_heights(rep, "schedule")


def _line_texts(rep, role: str) -> list[str]:
    return [r["text"] for r in rep["lines"] if r["role"] == role]


_FIT_CASES = ("short", "long")
_LATIN_WORD = re.compile(r"[A-Za-z]+")
_SHORT_LATIN = 8


@pytest.mark.parametrize("case", list(_FIT_CASES))
def test_title_tagline_schedule_hierarchy_and_36px_ink_floors(case):
    copy = CASES[case]
    _, rep = bc.compose(_synthetic_base(), channel=copy[0], tagline=copy[1], schedule=copy[2],
                        skill="youtube-channel-banner", purpose=bc.PURPOSE_USER_FINAL)
    for role in ("channel", "tagline", "schedule"):
        heights = _ink_heights(rep, role)
        assert heights, (case, role)
        assert all(h >= bc.LINE_MIN_INK for h in heights), (case, role, heights)
    ch_px = [r["px"] for r in rep["lines"] if r["role"] == "channel"]
    tag_px = [r["px"] for r in rep["lines"] if r["role"] == "tagline"]
    sch_px = [r["px"] for r in rep["lines"] if r["role"] == "schedule"]
    assert ch_px and tag_px and sch_px
    assert min(ch_px) > max(tag_px) >= max(sch_px), (case, ch_px, tag_px, sch_px)
    assert min(tag_px) >= max(sch_px), (case, tag_px, sch_px)
    ch_ink = _ink_heights(rep, "channel")
    tag_ink = _ink_heights(rep, "tagline")
    assert min(ch_ink) > max(tag_ink), (case, ch_ink, tag_ink)


@pytest.mark.parametrize("case", list(_FIT_CASES))
def test_wrap_keeps_english_words_and_rejects_orphan_lines(case):
    channel, tagline, schedule = CASES[case]
    _, rep = bc.compose(_synthetic_base(), channel=channel, tagline=tagline, schedule=schedule,
                        skill="youtube-channel-banner", purpose=bc.PURPOSE_USER_FINAL)
    box_w = TARGET[2] - TARGET[0]
    for role, src in (("channel", channel), ("tagline", tagline), ("schedule", schedule)):
        rows = _line_texts(rep, role)
        if not src:
            assert rows == []
            continue
        assert rows, (case, role)
        assert all(len(r.strip()) != 1 for r in rows), (case, role, rows)
        if len(rows) > 1:
            orphans = [r for r in rows if re.fullmatch(r"[A-Za-z]+", r.strip()) and len(r.strip()) <= _SHORT_LATIN]
            assert orphans == [], (case, role, rows)
        # Space-delimited English words that fit in the box stay intact (never split).
        px = next(r["px"] for r in rep["lines"] if r["role"] == role)
        font = bc._font(bc.FONT_BOLD if role == "channel" else bc.FONT_REGULAR, px)
        joined = " ".join(rows)
        got = _LATIN_WORD.findall(joined)
        for word in _LATIN_WORD.findall(src):
            if bc._width(font, word) <= box_w:
                assert word in got, (case, role, word, rows)


# 120 characters is the field cap. Dense CJK at the 36px line-3 floor wraps to more rows
# than the strict core can hold, even after shrinking the title and tagline to the
# consistency limit (title ink stays above 36px).
OVERFLOW_COPY = (
    ("创意工作室官方频道全流程商业交付与案例复盘国际版" * 5)[:120],
    ("人工智能绘画教程创意工作流从零基础到商业交付的完整课程体系与案例库" * 5)[:120],
    ("每周二周五晚上八点更新周末不定期直播答疑会员专属工作流模板每月更新一次另加专题加更与一对一复盘并附下载与作业点评" * 5)[:120],
)


def test_line3_overflow_at_floor_raises_instead_of_shrinking_below_36px():
    with pytest.raises(bc.LayoutError):
        bc.layout(*OVERFLOW_COPY)
    with pytest.raises(bc.LayoutError):
        bc.compose(_synthetic_base(), channel=OVERFLOW_COPY[0], tagline=OVERFLOW_COPY[1],
                   schedule=OVERFLOW_COPY[2], skill="youtube-channel-banner", purpose=bc.PURPOSE_USER_FINAL)


def test_very_long_copy_raises_when_title_cannot_stay_largest():
    with pytest.raises(bc.LayoutError):
        bc.layout(*VERY_LONG_COPY)
    with pytest.raises(bc.LayoutError):
        bc.compose(_synthetic_base(), channel=VERY_LONG_COPY[0], tagline=VERY_LONG_COPY[1],
                   schedule=VERY_LONG_COPY[2], skill="youtube-channel-banner", purpose=bc.PURPOSE_USER_FINAL)


def test_wrap_breaks_at_preferred_punctuation_and_spaces_without_splitting_english():
    font = bc._font(bc.FONT_REGULAR, 40)
    text = "AI 绘画教程 · 创意工作流 · Stable Diffusion / ComfyUI / Midjourney 全流程实战"
    # Wide enough that a mid-word split is not required; a preferred break must be used.
    lines = bc.wrap(font, text, 800)
    assert lines and all(bc._width(font, ln) <= 800 for ln in lines)
    assert all(len(ln.strip()) != 1 for ln in lines)
    joined = " ".join(lines)
    for word in ("Stable", "Diffusion", "ComfyUI", "Midjourney"):
        assert word in _LATIN_WORD.findall(joined)
        assert all(word not in ln or word in _LATIN_WORD.findall(ln) for ln in lines)
    # Breaks happen at · or / or spaces, not inside an English word.
    for ln in lines[:-1]:
        assert ln[-1] in "·、，/" or ln[-1].isspace() or ln.split()[-1] in _LATIN_WORD.findall(text)


def test_wrap_does_not_leave_edition_alone_or_split_international():
    font = bc._font(bc.FONT_BOLD, 46)
    text = "Creative Workflow Lab International Edition"
    # Width that would naturally park "Edition" on its own line under a naive wrap.
    edition_w = bc._width(font, "Edition")
    intl_ed_w = bc._width(font, "International Edition")
    naive_cut = bc._width(font, "Creative Workflow Lab International")
    width = max(edition_w + 1, naive_cut)  # "International" fits; "International Edition" may not
    width = naive_cut  # first five words fit exactly-ish; Edition would be the remainder
    lines = bc.wrap(font, text, width)
    if lines is not None:
        assert all(len(ln.strip()) != 1 for ln in lines)
        if len(lines) > 1:
            assert not any(re.fullmatch(r"[A-Za-z]+", ln.strip()) and len(ln.strip()) <= _SHORT_LATIN for ln in lines)
            assert "Edition" not in [ln.strip() for ln in lines] or len(lines) == 1
        assert "International" in _LATIN_WORD.findall(" ".join(lines))
        # International itself fits, so it must not be character-split.
        assert any("International" in _LATIN_WORD.findall(ln) for ln in lines)
    else:
        # Refusing this width is also legal; layout will shrink or raise the shorten card.
        assert bc._width(font, "International Edition") > width


def test_wrap_character_break_never_leaves_a_single_char():
    font = bc._font(bc.FONT_BOLD, 48)
    token = "Supercalifragilisticexpialidocious"
    # Force a character break: no preferred break point, token wider than the box.
    width = bc._width(font, token) - 10
    assert width < bc._width(font, token)
    lines = bc.wrap(font, token, width)
    assert lines is not None and len(lines) >= 2
    assert all(len(ln.strip()) >= 2 for ln in lines)
    assert "".join(ln.strip() for ln in lines) == token


# --- wash pipelines cannot call the compositor --------------------------------------------------------

def test_guard_refuses_other_skills_and_purposes():
    base = _synthetic_base()
    for skill, purpose in (("cover-design-director", bc.PURPOSE_USER_FINAL), ("youtube-channel-banner", "gold"),
                           ("youtube-channel-banner", None), (None, bc.PURPOSE_USER_FINAL)):
        with pytest.raises(bc.CompositorRefused):
            bc.compose(base, channel="Loomi Studio", skill=skill, purpose=purpose)


@pytest.mark.parametrize("name", ["kie_wash_phase3_fake.py", "gold_wash_runner.py"])
def test_wash_pipeline_on_the_stack_is_refused(tmp_path, name):
    mod = tmp_path / name
    mod.write_text(
        "from ComfyArt.api import banner_compose as bc\n"
        "def run(base):\n"
        "    return bc.compose(base, channel='Loomi Studio', skill=bc.SKILL, purpose=bc.PURPOSE_USER_FINAL)\n",
        encoding="utf-8")
    spec = importlib.util.spec_from_file_location(mod.stem, mod)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    with pytest.raises(bc.CompositorRefused, match="wash pipeline"):
        m.run(_synthetic_base())


def test_scripts_dir_is_refused(tmp_path):
    d = tmp_path / "scripts"
    d.mkdir()
    mod = d / "batch_examples.py"
    mod.write_text("from ComfyArt.api import banner_compose as bc\n"
                   "def run():\n    bc.guard(bc.SKILL, bc.PURPOSE_USER_FINAL)\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("batch_examples_ytb", mod)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    with pytest.raises(bc.CompositorRefused):
        m.run()


def test_wash_scripts_do_not_import_the_compositor():
    for path in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "scripts").glob("*.sh")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "banner_compose" not in text and "compose_banner_text" not in text, path.name


def test_compose_tool_refuses_other_skills(monkeypatch):
    called = []

    async def submit(*a, **k):
        called.append(a)
        return {}

    monkeypatch.setattr(banner, "submit_command", submit)
    out = asyncio.run(banner.compose_banner_text({"base": "shape:b", "skill": "cover-design-director", "channel_name": "x"}))
    assert out["status"] == "failed" and out["kind"] == "bannerComposeRefused" and called == []


def test_compose_tool_writes_2560x1440_and_places_it_next_to_the_base(monkeypatch, fresh_user_dir):
    calls = []

    async def submit(action, args, project, timeout, chat=""):
        calls.append((action, dict(args)))
        if action == "get_canvas":
            return {"shapes": [{"id": "shape:base", "type": "image", "url": "/api/view?filename=b.png&subfolder=&type=output"}]}
        return {"id": "shape:final"}

    monkeypatch.setattr(banner, "submit_command", submit)
    monkeypatch.setattr(banner, "_local_bytes", lambda src: _synthetic_base() if "b.png" in src else None)
    out = asyncio.run(banner.compose_banner_text({
        "base": "shape:base", "skill": "youtube-channel-banner", "channel_name": "Loomi Studio",
        "tagline": "AI 绘画教程 · 创意工作流", "schedule": "每周二 / 周五更新", "brand_color": "#2F6BFF"}))
    assert out["status"] == "done" and out["charged"] is False, out
    assert (out["width"], out["height"]) == (2560, 1440) and out["id"] == "shape:final"
    assert out["all_inside_strict_core"] and out["all_inside_hard_boundary"] and out["text_area_clear"]
    assert [c[0] for c in calls] == ["get_canvas", "place_banner"]
    place = calls[1][1]
    assert place["near"] == "shape:base" and place["image"]["type"] == "output"
    import folder_paths
    path = Path(folder_paths.get_output_directory()) / place["image"]["subfolder"] / place["image"]["filename"]
    assert Image.open(path).size == (2560, 1440)


_ZH_SHORTEN = "横幅上的文字排在安全区内有点长，请缩短后再继续。"
_EN_SHORTEN = "The banner text is a bit long for the safe area. Please shorten it to continue."


def test_base_preflight_overflow_returns_shorten_card_and_does_not_submit(relay):
    out = _run(lang="zh", goal_text="",
               prompt="text-free brand plate, brand blue #2F6BFF",
               skill="youtube-channel-banner", banner_stage="base",
               channel_name=OVERFLOW_COPY[0], tagline=OVERFLOW_COPY[1], schedule=OVERFLOW_COPY[2])
    assert SENT == []
    assert out.get("submitted") is False and out.get("charged") is False
    assert out["status"] == "needs_input" and out["kind"] == "bannerTextShorten"
    assert out["prompt"] == _ZH_SHORTEN == bc.SHORTEN_COPY["zh"]["prompt"]
    assert "失败" not in out["prompt"] and "重跑" not in out["prompt"] and "不通过" not in out["prompt"]
    questions = out["questions"]
    assert [q["id"] for q in questions] == ["yt_shorten_copy"]
    assert questions[0]["prompt"] == _ZH_SHORTEN
    assert questions[0]["allow_other"] is True
    assert questions[0]["placeholder"] == bc.SHORTEN_COPY["zh"]["placeholder"]
    assert out["ask"]["questions"][0]["id"] == "yt_shorten_copy"


@pytest.mark.parametrize("copy", ["overflow", "very_long"])
@pytest.mark.parametrize("lang,prompt", [
    ("zh", "横幅上的文字排在安全区内有点长，请缩短后再继续。"),
    ("en", "The banner text is a bit long for the safe area. Please shorten it to continue."),
])
def test_base_preflight_shorten_card_follows_ui_language(relay, lang, prompt, copy):
    src = OVERFLOW_COPY if copy == "overflow" else VERY_LONG_COPY
    out = _run(lang=lang, goal_text="",
               prompt="text-free brand plate, brand blue #2F6BFF",
               skill="youtube-channel-banner", banner_stage="base",
               channel_name=src[0], tagline=src[1], schedule=src[2])
    assert SENT == []
    assert out.get("submitted") is False and out.get("charged") is False
    assert out["status"] == "needs_input" and out["kind"] == "bannerTextShorten"
    assert out["prompt"] == prompt
    assert out["questions"][0]["prompt"] == prompt
    assert out["questions"][0]["placeholder"] == bc.SHORTEN_COPY[lang]["placeholder"]
    assert "失败" not in out["prompt"] and "fail" not in out["prompt"].lower()
    assert "重跑" not in out["prompt"] and "rerun" not in out["prompt"].lower()


def _visible_shorten_fields(payload: dict) -> list[str]:
    """User-visible ask-card strings (prompt, placeholder, labels, descriptions)."""
    out: list[str] = []
    for key in ("prompt", "placeholder"):
        if payload.get(key):
            out.append(str(payload[key]))
    for q in payload.get("questions") or []:
        for key in ("prompt", "placeholder", "title"):
            if q.get(key):
                out.append(str(q[key]))
        for opt in q.get("options") or []:
            for key in ("label", "description"):
                if opt.get(key):
                    out.append(str(opt[key]))
    if payload.get("ask"):
        out.extend(_visible_shorten_fields(payload["ask"]))
    return out


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_shorten_card_is_one_language_and_has_no_debug_copy(lang):
    other = "en" if lang == "zh" else "zh"
    card = bc.shorten_copy_card(lang)
    result = bc.shorten_copy_result(lang)
    visible = "\n".join(_visible_shorten_fields(card) + _visible_shorten_fields(result))
    assert bc.SHORTEN_COPY[lang]["prompt"] in visible
    assert bc.SHORTEN_COPY[lang]["placeholder"] in visible
    # Only the current language: the other locale's sentence must not appear.
    assert bc.SHORTEN_COPY[other]["prompt"] not in visible
    assert bc.SHORTEN_COPY[other]["placeholder"] not in visible
    # Debug / internal strings must not reach user-visible card fields.
    for needle in ("dry-run", "未提交生成", "id yt_shorten_copy", "yt_shorten_copy", "bannerTextShorten"):
        assert needle not in visible, needle


@pytest.mark.parametrize("case", ["short", "long"])
def test_base_preflight_fitting_copy_proceeds_to_submit(relay, case):
    ch, tg, sc = CASES[case]
    out = _run(prompt="text-free brand plate, brand blue #2F6BFF",
               skill="youtube-channel-banner", banner_stage="base",
               channel_name=ch, tagline=tg, schedule=sc)
    assert out.get("status") != "failed" and out.get("kind") != "bannerTextShorten", out
    assert len(SENT) == 1 and SENT[0][0] == "generate_image"
    assert "channel_name" not in SENT[0][1]


def test_place_banner_page_handler_exists():
    ts = (ROOT / "src/botCommands.ts").read_text(encoding="utf-8")
    assert "place_banner: async (editor, args, _onError, chat) =>" in ts
    assert banner.PLACE_ACTION == "place_banner"
