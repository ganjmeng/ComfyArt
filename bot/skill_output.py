"""#707: declared canvas size for skills whose deliverable is not 1024x1024.

The agent is told the size in the skill text. This module also fills generate_image
when a skill run omits it, and skips the list_models / expand / extra-frame detour
on a single-image skill. It does not choose a model and does not change the #706
identical-call guard.

#982: a skill run with no declared canvas used to submit no size at all, so the
provider's schema default decided the pixels (the $0 audit saw 512x512). Every
unpinned skill now gets the documented 1024x1024 floor below, with the size audit
on; product-specific defaults still belong in OUTPUTS (logo/character are pinned
here) and are listed as open questions in the #982 PR.
"""
from __future__ import annotations

import re

# images: how many separate generate_image calls the skill is built for.
# A single-image skill is exactly one call. pose-fission is one call per shot.
#
# #979: the deliverable is now per TEMPLATE (#911 comment 6872615903), not per skill.
# A row may carry `stages` (ordered delivery stages, each with its own images/size)
# and `presets` (one plan per template id; ids come from src/skills.ts → applyRaw748).
# Flat width/height/ratio/images stay on every row: they are the default template
# and keep #707/#974/#905 consumers working unchanged. `images` is the total across
# stages (brand = 3 + 1), so a staged skill is never a single-image skill.
BRAND_STAGES_979: tuple[dict, ...] = (
    # Stage 1: three different logo direction proposals, 1:1.
    {"width": 1024, "height": 1024, "ratio": "1:1", "images": 3,
     "label": "3 logo direction proposals"},
    # Stage 2: only after the user picks one direction (or says "you decide"):
    # one 16:9 guideline board. Never a landscape single board instead of the set.
    {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
     "label": "1 guideline board for the chosen direction"},
)
PACKAGING_PLAYFUL_STAGES_979: tuple[dict, ...] = (
    {"width": 1536, "height": 2048, "ratio": "3:4", "images": 3,
     "label": "3 single-SKU pack images"},
    {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
     "label": "1 range shot"},
)
# #979: product ruling — the template ids below are the ids applyRaw748 keeps from
# the built-in presets (index order of data/skills-748.json). Brand's six templates
# all share the same staged plan; packaging's five templates do not.
BRAND_PRESETS_979: dict[str, dict] = {
    "geometric": {"name": "餐饮服务 / Food Service"},
    "handmade": {"name": "Fashion & Accessories / 服装配饰"},
    "tech": {"name": "Beauty & Personal Care / 美妆个护"},
    "beauty": {"name": "Food & Beverage / 食品饮料"},
    "foodbev": {"name": "Pet Supplies / 宠物用品"},
    "pet": {"name": "Home & Lifestyle / 家居生活"},
}
PACKAGING_PRESETS_979: dict[str, dict] = {
    "eco": {
        "width": 1536, "height": 2048, "ratio": "3:4", "images": 1,
        "name": "主款包装设计 / Master Packaging Design",
    },
    "gold": {
        "width": 2048, "height": 1152, "ratio": "16:9", "images": 3,
        "name": "包装视觉方向 / Packaging Visual Direction",
    },
    "playful": {
        "width": 1536, "height": 2048, "ratio": "3:4", "images": 4,
        "stages": PACKAGING_PLAYFUL_STAGES_979,
        "name": "多 SKU 包装系列 / Multi-SKU Packaging Series",
    },
    "panels": {
        "width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
        "name": "包装面板与结构示意 / Packaging Panels & Structural Diagram",
    },
    "shelf": {
        "width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
        "name": "包装货架展示 / Packaging Shelf Display",
    },
}
# #982: every character template delivers ONE sheet at the ratio the template
# itself declares (src/data/skills-748.json media[]): 1:1 for turnaround /
# outfit / prop / editorial, 16:9 for expression / modeling / basic /
# technical. Sizes follow the product canvases already in use: 1024x1024 for
# 1:1 and 2048x1152 for 16:9. Template ids are the ones applyRaw748 keeps.
CHARACTER_PRESETS_982: dict[str, dict] = {
    "turnaround": {"width": 1024, "height": 1024, "ratio": "1:1", "images": 1,
                   "name": "Character Turnaround Sheet"},
    "expression": {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
                   "name": "Expression & Pose Sheet"},
    "modeling": {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
                 "name": "Modeling Detail Reference Sheet"},
    "outfit": {"width": 1024, "height": 1024, "ratio": "1:1", "images": 1,
               "name": "Outfit / Form Variation Sheet"},
    "prop": {"width": 1024, "height": 1024, "ratio": "1:1", "images": 1,
             "name": "Prop Interaction Sheet"},
    "basic": {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
              "name": "Basic Character Sheet"},
    "technical": {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
                  "name": "Complete Technical Character Sheet"},
    "editorial": {"width": 1024, "height": 1024, "ratio": "1:1", "images": 1,
                  "name": "Editorial Fashion Sheet"},
}
# #982: documented floor for a skill that is neither in OUTPUTS nor managed by a
# registered pin. It is not a product default for that skill; it is the smallest
# canvas the pipeline may submit on its own, and `size_lock` makes a smaller
# provider file visible instead of silently delivering it.
FALLBACK_OUTPUT_982: dict[str, int | str] = {"width": 1024, "height": 1024, "ratio": "1:1"}
OUTPUTS: dict[str, dict] = {
    "before-after": {
        "width": 1920, "height": 1080, "ratio": "16:9", "images": 1,
        "names": ("before-after", "前后对比视觉", "Before / After Visuals"),
    },
    "pose-fission": {
        "width": 1536, "height": 2048, "ratio": "3:4", "images": 4,
        "names": ("pose-fission", "电商同场景角色姿势裂变", "Same-Scene Pose Fission"),
    },
    # #974: product ruling (#911 comment 6872065790) — four SEPARATE 3:4 1536x2048 images,
    # one per angle, never one grid; every call carries the same uploaded reference.
    "universal-multi-angle-grid": {
        "width": 1536, "height": 2048, "ratio": "3:4", "images": 4,
        "names": ("universal-multi-angle-grid", "多角度图像生成器", "Multi-Angle Image Generator"),
    },
    "game-art": {
        "width": 1024, "height": 1824, "ratio": "9:16", "images": 1,
        "names": ("game-art", "游戏美术与运营视觉设计", "Game Art & Ops Visuals"),
    },
    "linkedin-banner": {
        "width": 1584, "height": 396, "images": 1,
        "names": ("linkedin-banner", "LinkedIn横幅", "LinkedIn Banner"),
    },
    # #911: clothing-swap follows the person photo (image 1); see FOLLOW_REF_SIZES.
    # This row is only the fallback when image 1's size cannot be read.
    "clothing-swap": {
        "width": 1536, "height": 2048, "ratio": "3:4", "images": 1,
        "names": ("clothing-swap", "AI服装换装", "AI Clothing Swap"),
    },
    # #982: the example-type skill lost its 4 dead presets (applyRaw748) and had no
    # output contract, so the default path submitted no size. Product-minimal
    # default: one 1:1 1024x1024 brushed-metal study; Additional Details may name
    # another finish, but never a second frame.
    "logo-material-explorer": {
        "width": 1024, "height": 1024, "ratio": "1:1", "images": 1,
        "names": ("logo-material-explorer", "徽标材质探索器", "Logo Material Explorer"),
    },
    # #982: eight templates, eight plans, one sheet each. Flat fields are the
    # default turnaround template (also the dialog's first template).
    "character-sheet-design": {
        "width": 1024, "height": 1024, "ratio": "1:1", "images": 1,
        "presets": CHARACTER_PRESETS_982,
        "names": ("character-sheet-design", "真人角色设定与参考板",
                  "Realistic Human Character Design & Reference Sheets",
                  "角色设定表", "Character Sheet"),
    },
    # #979: brand delivery is TWO stages, 4 images total. Flat fields = stage 1
    # (the safe default when no stage is passed); stages carry the full contract.
    "brand-identity-director": {
        "width": 1024, "height": 1024, "ratio": "1:1", "images": 4,
        "stages": BRAND_STAGES_979,
        "presets": {pid: {"stages": BRAND_STAGES_979, **row}
                    for pid, row in BRAND_PRESETS_979.items()},
        "names": ("brand-identity-director", "品牌视觉识别", "Logo System"),
    },
    # #979: five templates, five plans. Flat fields = the default 「主款」 (eco, t1).
    "packaging-design-director": {
        "width": 1536, "height": 2048, "ratio": "3:4", "images": 1,
        "presets": PACKAGING_PRESETS_979,
        "names": ("packaging-design-director", "品牌包装设计系统",
                  "Brand Packaging Design System"),
    },
}

_BY_NAME = {n.casefold(): sid for sid, row in OUTPUTS.items() for n in row["names"]}
_DETOUR = frozenset({"list_models", "expand_image", "create_frame"})


def resolve(name: object) -> str | None:
    key = str(name or "").strip().casefold()
    return _BY_NAME.get(key)


def output_of(name: object) -> dict | None:
    sid = resolve(name)
    return OUTPUTS.get(sid) if sid else None


# #979: rows whose plan depends on the selected template / delivery stage.
PRESET_PLAN_SKILLS = frozenset(
    sid for sid, row in OUTPUTS.items() if row.get("presets") or row.get("stages")
)


def _preset_row(sid: str, preset_id: object = "") -> tuple[str, dict, bool]:
    """(effective template id, plan row, defaulted). No/unknown template → the skill's
    default template (the first one), never a 1024x1024 fallback."""
    row = OUTPUTS[sid]
    presets: dict[str, dict] = row.get("presets") or {}
    if not presets:
        return "", row, True
    key = str(preset_id or "").strip()
    if key in presets:
        return key, presets[key], False
    first = next(iter(presets))
    return first, presets[first], True


def plan_for(sid: str, preset_id: object = "", stage: object = 1) -> dict:
    """The effective plan for one generate_image call: template + 1-based stage.

    Returns width/height/ratio/images for that stage, the total across stages, and
    the effective template so the lock can state it. Unknown stage clamps to the
    last stage (never to 1024x1024)."""
    pid, spec, defaulted = _preset_row(sid, preset_id)
    stages = list(spec.get("stages") or OUTPUTS[sid].get("stages") or [])
    total = int(spec.get("images") or OUTPUTS[sid]["images"])
    if stages:
        try:
            n = int(stage or 1)
        except (TypeError, ValueError):
            n = 1
        n = max(1, min(len(stages), n))
        chosen = stages[n - 1]
        total = sum(int(s.get("images") or 1) for s in stages)
    else:
        n, chosen = 1, spec
    return {
        "preset": pid,
        "default_template": defaulted,
        "stage": n,
        "stages": stages,
        "total_images": total,
        "width": int(chosen["width"]),
        "height": int(chosen["height"]),
        "ratio": chosen.get("ratio"),
        "images": int(chosen.get("images") or 1),
    }


def pixels_for_ratio(ratio: object) -> tuple[int, int] | None:
    """#982: a 16-multiple canvas with a 1024 long side at the given `a:b` ratio."""
    m = re.fullmatch(r"\s*(\d{1,3})\s*[:：]\s*(\d{1,3})\s*", str(ratio or ""))
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if not a or not b:
        return None
    if a >= b:
        return 1024, max(64, round(1024 * b / a / 16) * 16)
    return max(64, round(1024 * a / b / 16) * 16), 1024


def fill_unpinned_fallback(args: dict, skill: object) -> dict:
    """#982: fill the documented floor for a skill that has no declared canvas.

    A call that would otherwise submit no size gets pixels: the row's 1:1 default,
    or the model's explicit ratio at a 1024 long side. Explicit width+height and a
    resolution tier win. A registered skill pin owns its size (#708/#911), so
    pinned skills are left untouched.
    """
    skill_id = str(skill or "").strip()
    if not skill_id:
        return args
    from ..api.auto_models import skill_pin
    if skill_pin(skill_id):
        return args
    if args.get("width") and args.get("height"):
        return args
    if args.get("resolution") or args.get("edit_resolution"):
        return args
    ratio = args.get("ratio")
    if ratio:
        pixels = pixels_for_ratio(ratio)
        if not pixels:
            return args
        args["width"], args["height"] = pixels
    else:
        args["width"] = int(FALLBACK_OUTPUT_982["width"])
        args["height"] = int(FALLBACK_OUTPUT_982["height"])
        args["ratio"] = str(FALLBACK_OUTPUT_982["ratio"])
    # The page audits the downloaded file; a provider that still returns a small
    # file is reported instead of being silently delivered as the result.
    args["size_lock"] = True
    args.setdefault("skill", skill_id)
    return args


# #979: the lock itself names the template so a relay pass (no user text) can be
# filled the same way. Kept on the single Output-lock line, which #905/#978 already
# strip before reading the user's own words.
_TEMPLATE_ID_RE = re.compile(r"(?:^|\n)Output lock:[^\n]*?\btemplate=([A-Za-z0-9_.-]+)")


def preset_from_text(text: object) -> str:
    m = _TEMPLATE_ID_RE.search(str(text or ""))
    return m.group(1) if m else ""


def is_single(name: object, preset_id: object = "") -> bool:
    sid = resolve(name)
    if not sid:
        return False
    if sid in PRESET_PLAN_SKILLS:
        return int(plan_for(sid, preset_id)["images"]) == 1
    return int(OUTPUTS[sid]["images"]) == 1

# #905: a ratio the user wrote in their own message overrides the default.
# One exact size per ratio. A ratio the chat model wrote is ignored; a ratio not in the table falls back.
# #979: brand/packaging are default values too — a ratio the user wrote still wins over
# the template's ratio (the plan's images/stage count is unchanged).
# #905: a reference card sets the ratio only for before-after. Packaging/brand keep
# their template ratio when the user names none (an upload is not a ratio request).
REF_CARD_RATIO = frozenset({"before-after"})
USER_RATIOS: dict[str, dict[str, tuple[int, int]]] = {
    "before-after": {"16:9": (1920, 1080), "4:5": (1024, 1280), "1:1": (1024, 1024), "9:16": (1080, 1920)},
    "brand-identity-director": {"1:1": (1024, 1024), "16:9": (2048, 1152),
                                "4:5": (1024, 1280), "9:16": (1152, 2048)},
    "packaging-design-director": {"3:4": (1536, 2048), "16:9": (2048, 1152), "1:1": (1536, 1536),
                                  "4:5": (1600, 2000), "9:16": (1152, 2048)},
}
_RATIO_WORDS = {"横版": "16:9", "竖版": "9:16", "方图": "1:1", "正方形": "1:1"}
_RATIO_RE = re.compile(r"(?<![\d.])(\d{1,2})\s*[:：]\s*(\d{1,2})(?![\d.])")
# Text the app adds to the user turn (skill start hint, output lock); never the user's own words.
_INJECTED_RE = re.compile(r"Use the ComfyArt skill [\s\S]*?then follow those instructions\.|Output lock:[^\n]*")
# #978 HOLD: the selected template prompt is also app-added text, not the user's words. Size/ratio parsing
# must not read it: a template's 16:9 must never override the 4:5 the user typed this turn. The markers are
# emitted by api/bot_send.compose_provider_text (keep the two in sync).
TEMPLATE_BLOCK_START = "[ComfyArt selected template]"
TEMPLATE_BLOCK_END = "[/ComfyArt selected template]"
_TEMPLATE_BLOCK_PATTERN = re.escape(TEMPLATE_BLOCK_START) + r"[\s\S]*?" + re.escape(TEMPLATE_BLOCK_END)
TEMPLATE_BLOCK_RE = re.compile(_TEMPLATE_BLOCK_PATTERN + r"[ \t]*\n?")
USER_RATIO_KEY = "_user_ratio"

# #911: skills whose output ratio follows image 1 (the first reference). The
# server reads that image's pixel size and snaps to the closest ratio here
# (api/wavespeed._nearest, the same snap used for a model's aspect_ratio enum;
# the model's own enum snap still runs on submit). One in-limit size per ratio.
# If image 1 cannot be read, the OUTPUTS row (3:4) is used.
FOLLOW_REF_SIZES: dict[str, dict[str, tuple[int, int]]] = {
    "clothing-swap": {
        "1:1": (1536, 1536),
        "4:5": (1600, 2000), "5:4": (2000, 1600),
        "3:4": (1536, 2048), "4:3": (2048, 1536),
        "2:3": (1344, 2016), "3:2": (2016, 1344),
        "9:16": (1152, 2048), "16:9": (2048, 1152),
    },
}
# Marker so the relay pass (no image bytes) keeps the ratio the chat loop read.
REF_RATIO_KEY = "_ref_ratio"


def user_ratio(sid: str, user_text: object) -> str | None:
    """The first whitelisted ratio in the user's own text, or None (default size)."""
    table = USER_RATIOS.get(sid)
    if not table:
        return None
    # #978 HOLD: user_text may be the whole provider turn, including our template block; strip it first.
    text = TEMPLATE_BLOCK_RE.sub(" ", str(user_text or ""))
    text = _INJECTED_RE.sub(" ", text)
    for m in _RATIO_RE.finditer(text):
        r = f"{int(m.group(1))}:{int(m.group(2))}"
        if r in table:
            return r
    for word, r in _RATIO_WORDS.items():
        if word in text and r in table:
            return r
    return None


def follows_ref(name: object) -> bool:
    sid = resolve(name)
    return bool(sid) and sid in FOLLOW_REF_SIZES


def image_size(data: bytes | None) -> tuple[int, int] | None:
    """Pixel (width, height) of image bytes; None when absent or undecodable."""
    if not data:
        return None
    try:
        import io

        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
    except Exception:
        return None
    return (int(w), int(h)) if w and h else None


def ref_ratio(sid: str, data: bytes | None) -> str | None:
    """Closest FOLLOW_REF_SIZES ratio to image 1's pixel aspect; None if unreadable."""
    table = FOLLOW_REF_SIZES.get(sid)
    size = image_size(data)
    if not table or not size:
        return None
    from ..api.wavespeed import _nearest
    return _nearest(list(table), size[0] / size[1])


def apply_generate(args: dict | None, current_skill: str = "", user_text: str | None = None,
                   ref_image: bytes | None = None, current_preset: str = "") -> dict:
    """Fill the skill id and its declared pixels.

    #982: skills without a declared canvas (and without a registered pin) get the
    documented 1024x1024 floor instead of submitting no size; explicit pixels/ratio
    still win. Skills managed by a pin keep that pin's size behavior.

    A declared size replaces a square default or a ratio the model invented.
    count stays 1: a multi-shot skill varies the prompt per call, not count.
    #905: user_text is given only where the user's own message is known (the chat
    loop); it sets or clears the USER_RATIO_KEY marker. Without it (the relay),
    only a marker matching the table is kept. A before-after reference with no
    user ratio follows the card inside it.
    #911: a FOLLOW_REF_SIZES skill takes image 1's ratio (ref_image bytes, or the
    marker a previous pass set); unreadable -> the declared fallback row.
    """
    args = dict(args or {})
    raw = str(args.get("skill") or "").strip()
    named = resolve(raw)
    if raw and not named:
        # #982: an unknown/custom skill id must not reach the provider with no size.
        return fill_unpinned_fallback(args, raw)
    sid = named or resolve(current_skill)
    if not sid:
        # #911 / #912: studio-model and ai-model are not in OUTPUTS (no
        # declared canvas). Still pass skill= on generate_image so the call
        # is attributable. Only in that skill's session, only when skill is
        # omitted, and only when the call did not name an explicit model.
        # Do not invent a size, do not use a generic skill_pin hook, and
        # do not fill when the call already names a model.
        from ..api.auto_models import named_or_none
        cur_raw = str(current_skill or "").strip()
        cur = cur_raw.casefold()
        if (
            cur in {"studio-model", "ai-model"}
            and not raw
            and not named_or_none(args.get("model"))
            and not named_or_none(args.get("edit_model"))
        ):
            args["skill"] = cur
            return args
        if cur_raw:
            # #982: a custom/undeclared skill run also gets the floor.
            return fill_unpinned_fallback(args, cur_raw)
        return args
    row = OUTPUTS[sid]
    if not named:
        args["skill"] = sid
    # #979: resolve the template before anything else. An explicit arg wins (the relay
    # re-runs this function), then the lock line the client already received, then the
    # skill's default template. Unknown/no template never becomes 1024x1024.
    plan = None
    if sid in PRESET_PLAN_SKILLS:
        requested = str(args.pop("preset", "") or "").strip()
        preset_id = requested or preset_from_text(user_text) or str(current_preset or "").strip()
        stage_raw = args.pop("stage", None)
        if stage_raw is None:
            # The model may pass the stage's pixels instead of stage=N (the lock names both).
            # Use a size that exactly matches one of this template's stages; otherwise stage 1.
            try:
                asked = (int(args.get("width") or 0), int(args.get("height") or 0))
            except (TypeError, ValueError):
                asked = (0, 0)
            _pid, _spec, _ = _preset_row(sid, preset_id)
            _stages = _spec.get("stages") or OUTPUTS[sid].get("stages") or []
            stage_raw = next((i + 1 for i, st in enumerate(_stages)
                              if (int(st["width"]), int(st["height"])) == asked), 1)
        plan = plan_for(sid, preset_id, stage_raw)
    picked = None
    if sid in USER_RATIOS:
        # #905: user_text is given only where the user's own message is known (the chat loop); it sets
        # or clears the marker. Without it (the relay), only a marker matching the table is kept.
        if user_text is not None:
            picked = user_ratio(sid, user_text)
            if not picked and ref_image and args.get("refs") and sid in REF_CARD_RATIO:
                # #905: no ratio in the user message, but a reference: follow the card inside it.
                # Decided from pixels on the server (bot/ref_orientation.py); the model has no say.
                from .ref_orientation import reference_ratio
                ref = reference_ratio(ref_image)
                picked = ref if ref in USER_RATIOS[sid] else None
        else:
            picked = str(args.get(USER_RATIO_KEY) or "")
            picked = picked if picked in USER_RATIOS.get(sid, {}) else None
    elif sid in FOLLOW_REF_SIZES:
        picked = ref_ratio(sid, ref_image) if ref_image is not None else None
        if picked is None and ref_image is None:
            marker = str(args.get(REF_RATIO_KEY) or "")
            picked = marker if marker in FOLLOW_REF_SIZES[sid] else None
    # Drop incoming markers for every OUTPUTS skill (linkedin-banner may carry a stale
    # _user_ratio; a relay for a non-follow-ref skill must not leak _ref_ratio).
    args.pop(USER_RATIO_KEY, None)
    args.pop(REF_RATIO_KEY, None)
    if picked and sid in USER_RATIOS:
        w, h = USER_RATIOS[sid][picked]
        args["width"], args["height"], args["ratio"] = w, h, picked
        args[USER_RATIO_KEY] = picked
    elif picked and sid in FOLLOW_REF_SIZES:
        args["width"], args["height"] = FOLLOW_REF_SIZES[sid][picked]
        args["ratio"] = picked
        args[REF_RATIO_KEY] = picked
    else:
        picked = None
    if not picked:
        # #979: a preset plan's own stage size; otherwise the row's flat default.
        width = plan["width"] if plan else int(row["width"])
        height = plan["height"] if plan else int(row["height"])
        ratio = plan.get("ratio") if plan else row.get("ratio")
        args["width"], args["height"] = width, height
        if ratio:
            args["ratio"] = ratio
        else:
            args.pop("ratio", None)
    args["count"] = 1
    # The page audits the downloaded file against these pixels. This does not change the model.
    args["size_lock"] = True
    if plan:
        # #979: keep the resolved template/stage on the args so the relay pass
        # (api/mcp_tools/canvas.py applies this a second time) is idempotent.
        args["preset"] = plan["preset"]
        args["stage"] = plan["stage"]
    return args


def _size_text(sid: str, width: int, height: int, ratio: object, picked: str | None = None) -> str:
    if sid in FOLLOW_REF_SIZES:
        return ("the size and ratio of image 1 (the server fills width, height and ratio; "
                "do not pass them)")
    if picked:
        return f"width={width} height={height} ratio={picked}"
    out = f"width={width} height={height}"
    return out + (f" ratio={ratio}" if ratio else "")


def _preset_hint(sid: str, preset_id: str, user_text: str) -> str:
    """#979: one-line lock naming the template, its count(s) and its size(s)."""
    row = OUTPUTS[sid]
    plan = plan_for(sid, preset_id, 1)
    preset = plan["preset"]
    name = str((row.get("presets") or {}).get(preset, {}).get("name") or preset)
    picked = user_ratio(sid, user_text) if user_text else None
    if picked:
        w, h = USER_RATIOS[sid][picked]
        override = f" The user named ratio {picked}, so use width={w} height={h} ratio={picked} on every image."
    else:
        override = ""
    stages = plan["stages"]
    total = plan["total_images"]
    default = " (skill default template: none was selected)" if plan["default_template"] else ""
    if sid == "brand-identity-director":
        sizes = []
        for i, s in enumerate(stages, 1):
            sw, sh = (USER_RATIOS[sid][picked] if picked else (s["width"], s["height"]))
            size = _size_text(sid, sw, sh, s.get("ratio"), picked)
            sizes.append(f"stage {i} = {int(s['images'])} image(s) at {size}")
        return (
            f"Output lock: template={preset} ({name}){default} — brand delivery is 2 stages / "
            f"{total} images total, and is NOT one landscape board. " + "; ".join(sizes) + ". "
            "Stage 1 this run, before the user picks a direction: exactly 3 separate images, count=1, "
            "one per distinct direction (different shape language, palette and type); then stop and ask "
            "the user to choose one. Do not render stage 2 before they pick. Stage 2, only after they pick "
            "a direction (or say you decide): exactly 1 guideline board with the main mark, horizontal and "
            "stacked lockups, black-and-white versions and basic usage examples; pass stage=2. "
            f"Every generate_image passes skill={sid!r} and preset={preset!r}, count=1; total exactly "
            f"{total} images, never a 5th and never 4 in one round." + override
        )
    if stages:
        parts = []
        call_at = 1
        for i, s in enumerate(stages, 1):
            sw, sh = (USER_RATIOS[sid][picked] if picked else (s["width"], s["height"]))
            size = _size_text(sid, sw, sh, s.get("ratio"), picked)
            n = int(s["images"])
            part = f"stage {i} = {n} image(s) at {size}"
            if n > 1:
                part += f" (pass stage={i} on calls {call_at}-{call_at + n - 1})"
            else:
                part += f" (pass stage={i})"
            parts.append(part)
            call_at += n
        return (
            f"Output lock: template={preset} ({name}){default} — deliver exactly {total} separate images "
            f"in {len(stages)} stages: " + "; ".join(parts) + ". "
            f"Call generate_image exactly {total} times, count=1 each, with a different prompt each time; "
            f"pass skill={sid!r} and preset={preset!r} on every call and use each stage's declared size. "
            "Do not substitute 1024x1024." + override
        )
    plan_w, plan_h = (USER_RATIOS[sid][picked] if picked else (plan["width"], plan["height"]))
    size = _size_text(sid, plan_w, plan_h, plan.get("ratio"), picked)
    n = int(plan["images"])
    if n == 1:
        return (
            f"Output lock: template={preset} ({name}){default} — call generate_image exactly once with "
            f"skill={sid!r}, preset={preset!r}, stage=1, {size}, count=1. Do not call list_models, "
            "expand_image, or create_frame. Do not outpaint. Then wait_generation and finish. "
            "Lettering must be real words in quotes, large enough to read." + override
        )
    return (
        f"Output lock: template={preset} ({name}){default} — deliver exactly {n} separate images, each "
        f"{size}, count=1. Call generate_image exactly {n} times with a different prompt each time; "
        f"pass skill={sid!r}, preset={preset!r}, stage=1 and count=1 on every call. "
        "Do not repeat the same arguments. Do not use 1024x1024." + override
    )


def run_hint(name: object, user_text: str = "", ref_image: bytes | None = None,
             preset_id: str = "") -> str:
    """One line appended to the skill-start user text. Empty when the skill has no declared size.

    #905: when the user's own message names a whitelisted ratio, the lock states that size, so the
    model is not told 16:9 while the user asked for 4:5. A reference with no user ratio follows
    the card inside it.
    #911: FOLLOW_REF_SIZES skills tell the model the server will fill size from image 1.
    #979: for a template-aware skill the lock states the selected template's count(s) and size(s)
    (and its default when no template was sent), so a template's plan is never read as the skill default.
    """
    sid = resolve(name)
    if not sid:
        return ""
    if sid in PRESET_PLAN_SKILLS:
        return _preset_hint(sid, preset_id, user_text)
    row = OUTPUTS[sid]
    if sid in FOLLOW_REF_SIZES:
        # #911: the server sets width/height/ratio from image 1; the model must not pick one.
        size = "the size and ratio of image 1 (the server fills width, height and ratio; do not pass them)"
    else:
        picked = user_ratio(sid, user_text) if user_text else None
        if not picked and ref_image and sid in REF_CARD_RATIO:
            from .ref_orientation import reference_ratio
            ref = reference_ratio(ref_image)
            picked = ref if ref in USER_RATIOS[sid] else None
        if picked:
            w, h = USER_RATIOS[sid][picked]
            size = f"width={w} height={h} ratio={picked}"
        else:
            size = f"width={row['width']} height={row['height']}"
            if row.get("ratio"):
                size += f" ratio={row['ratio']}"
    if int(row["images"]) == 1:
        return (
            f"Output lock: call generate_image exactly once with skill={sid!r}, {size}, count=1. "
            "Do not call list_models, expand_image, or create_frame. Do not outpaint. "
            "Then wait_generation and finish. Lettering must be real words in quotes, large enough to read."
        )
    if sid == "universal-multi-angle-grid":
        # #974: this skill's own wording, not pose-fission's. Four separate angle images, same reference each call.
        return (
            f"Output lock: deliver exactly {int(row['images'])} separate images, each {size}, count=1. "
            f"Call generate_image {int(row['images'])} times, one angle per call (front, 3/4, strict 90° side profile, "
            "detail/macro), with a different prompt each time. Pass the same uploaded subject shape id in refs "
            "(ref_modes content) on every call. Never merge the angles into one grid, collage or contact sheet. "
            "Do not use 1024x1024."
        )
    return (
        f"Output lock: each generate_image uses skill={sid!r}, {size}, count=1, and a different prompt "
        "(pose and angle only, not camera or shot size). Do not repeat the same arguments. Do not use 1024x1024."
    )


def single_image_skip(tool: str, skill: object, lang: str, generated: int,
                      preset_id: object = "") -> str | None:
    """Canned result for a detour or a second generate on a single-image skill. None = run the tool.

    The text is a normal tool result, not a non-retryable error, so the model can finish.
    #979: single-image is per template — packaging gold (3) and playful (4) are never skipped.
    """
    sid = resolve(skill)
    if not sid or not is_single(sid, preset_id):
        return None
    row = OUTPUTS[sid]
    plan = plan_for(sid, preset_id) if sid in PRESET_PLAN_SKILLS else None
    width = plan["width"] if plan else row["width"]
    height = plan["height"] if plan else row["height"]
    size = f"{width}x{height}"
    base = tool.split(".")[-1]
    if base == "generate_image" and generated < 1:
        return None
    if base != "generate_image" and base not in _DETOUR:
        return None
    if lang == "zh":
        if base == "generate_image":
            return (
                f"单图技能 {sid} 只生成 1 次，这一次没有提交，也没有扣费。"
                f"请调用 wait_generation 查看已有结果，然后结束。不要再生成、不要扩图、不要 list_models。"
            )
        return (
            f"单图技能 {sid} 不使用 {base}。请直接 generate_image 一次，"
            f"skill={sid}，width={width}，height={height}（{size}），count=1。"
            "不要扩图，不要另建不同尺寸的画框。"
        )
    if base == "generate_image":
        return (
            f"Single-image skill {sid} already used its one generate_image. This call did not submit "
            "and nothing was charged. Call wait_generation if needed, then finish. "
            "Do not generate again, expand, or list models."
        )
    return (
        f"Single-image skill {sid} does not use {base}. Call generate_image once with "
        f"skill={sid!r}, width={width}, height={height} ({size}), count=1. "
        "Do not outpaint and do not create a frame at another size."
    )
