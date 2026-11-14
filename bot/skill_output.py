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
# outfit / prop, 3:4 for editorial, 16:9 for expression / modeling / basic /
# technical. Design review 6874380577 raised 1:1 to 1536x1536 (the 1024 sheet
# made the face ~80 px); 16:9 stays 2048x1152. Template ids are applyRaw748's.
CHARACTER_PRESETS_982: dict[str, dict] = {
    "turnaround": {"width": 1536, "height": 1536, "ratio": "1:1", "images": 1,
                   "name": "Character Turnaround Sheet"},
    "expression": {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
                   "name": "Expression & Pose Sheet"},
    "modeling": {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
                 "name": "Modeling Detail Reference Sheet"},
    "outfit": {"width": 1536, "height": 1536, "ratio": "1:1", "images": 1,
               "name": "Outfit / Form Variation Sheet"},
    "prop": {"width": 1536, "height": 1536, "ratio": "1:1", "images": 1,
             "name": "Prop Interaction Sheet"},
    "basic": {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
              "name": "Basic Character Sheet"},
    "technical": {"width": 2048, "height": 1152, "ratio": "16:9", "images": 1,
                  "name": "Complete Technical Character Sheet"},
    # Design review 6874380577: 1024 square made the face ~80 px; 1:1 stays for
    # turnaround/outfit/prop at 1536 square, editorial is 3:4 at 2K.
    "editorial": {"width": 1536, "height": 2048, "ratio": "3:4", "images": 1,
                  "name": "Editorial Fashion Sheet"},
}
def _out(width: int, height: int, ratio: str, images: int, names: tuple[str, ...],
         *, refs: str = "", calls: list[dict] | None = None, media: str = "") -> dict:
    row: dict = {"width": width, "height": height, "ratio": ratio, "images": images, "names": names}
    if refs:
        row["refs"] = refs
    if calls:
        row["calls"] = calls
    if media:
        row["media"] = media
    return row


def _call(width: int, height: int, ratio: str, label: str) -> dict:
    return {"width": width, "height": height, "ratio": ratio, "images": 1, "label": label}


# #982 product ruling (HOLD comment 6874283882): 33 unpinned skills get a typed
# default, not one square. Accepted 1:1 (8), wide 16:9 (7), portrait 3:4 (3),
# multi-ratio packs (3), 9:21 phone (1), 4:3 (1), video stills (6), follow-ref (2),
# multi-asset (3 calls) (2). Sizes use the page's card semantics: 1024 SHORT
# side, long side snapped to 16 (16:9 = 1824x1024, 3:4 = 1024x1360, ...).
TYPE_OUTPUTS_982: dict[str, dict] = {
    # --- accepted 1:1 (product: keep 1024x1024) ---
    "logo-abstract": _out(1024, 1024, "1:1", 1,
        ("logo-abstract", "极简几何抽象 Logo", "Minimal Geometric Abstract Logo"),
        refs="reference photo (image 1)"),
    "lifestyle-scene": _out(1024, 1024, "1:1", 1,
        ("lifestyle-scene", "电商生活场景设计师", "E-commerce Lifestyle Scene Designer"),
        refs="product image (when provided)"),
    "crayon-sketch": _out(1024, 1024, "1:1", 1,
        ("crayon-sketch", "潦草蜡笔画风", "Rough Crayon Sketch"),
        refs="subject image (image 1)"),
    "fabric-collage": _out(1024, 1024, "1:1", 1,
        ("fabric-collage", "布艺拼贴画", "Fabric Collage"),
        refs="uploaded refs"),
    "naive-illustration": _out(1024, 1024, "1:1", 1,
        ("naive-illustration", "稚拙手绘插画", "Naive Illustration"),
        refs="uploaded refs"),
    "commerce-strategist": _out(1024, 1024, "1:1", 1,
        ("commerce-strategist", "电商视觉策略师", "Commerce Visual Strategist"),
        refs="optional ref assets"),
    "promo-ecommerce": _out(1024, 1024, "1:1", 1,
        ("promo-ecommerce", "电商促销主视觉", "E-commerce Promo Key Visual"),
        refs="product image"),
    "taobao-product": _out(1024, 1024, "1:1", 1,
        ("taobao-product", "淘宝商品视觉", "Taobao Product Visuals"),
        refs="product image (main image is 1:1)"),
    # --- wide 16:9 (product: 1824x1024 / 2k) ---
    # TODO(design 6874380577): website/PPT count pending visual review; current 1.
    "banner-design-director": _out(1824, 1024, "16:9", 1,
        ("banner-design-director", "横幅设计", "Banner Design"),
        refs="uploaded refs; pass every one"),
    "ppt-visual": _out(1824, 1024, "16:9", 1,
        ("ppt-visual", "高级感 PPT 视觉", "Premium PPT Visual"),
        refs="uploaded refs; pass every one"),
    "web-product-visual-design": _out(1824, 1024, "16:9", 1,
        ("web-product-visual-design", "Web产品视觉设计", "Web Product Visual Design"),
        refs="uploaded refs; pass every one"),
    "product-website": _out(1824, 1024, "16:9", 1,
        ("product-website", "产品网站设计师", "Product Website Designer"),
        refs="uploaded refs; pass every one"),
    "premium-website": _out(1824, 1024, "16:9", 1,
        ("premium-website", "高端网站艺术总监", "Premium Website Art Director"),
        refs="uploaded refs; pass every one"),
    "restaurant-website": _out(1824, 1024, "16:9", 1,
        ("restaurant-website", "餐厅网站创建器", "Restaurant Website Builder"),
        refs="uploaded refs; pass every one"),
    # TODO(design 6874380577): confirm 16:9 vs 4:3; current 16:9 with the
    # instruction's 4:3 detail vignette left to the agent.
    "interior-architectural-visualization": _out(1824, 1024, "16:9", 1,
        ("interior-architectural-visualization", "室内与建筑可视化", "Interior & Architectural Visualization"),
        refs="uploaded refs; eye-level wide shot, detail vignette is 4:3"),
    # --- portrait 3:4 (product: 1024x1360 / 2k) ---
    "poster-differentiated-compiler": _out(1024, 1360, "3:4", 1,
        ("poster-differentiated-compiler", "海报设计", "Poster Design"),
        refs="uploaded refs; instruction says default 3:4"),
    # TODO(design 6874380577): 4:5 vs 3:4 pending visual review; current 3:4.
    "photo-split-poster": _out(1024, 1360, "3:4", 1,
        ("photo-split-poster", "照片对半抽象海报", "Photo Split Abstract Poster"),
        refs="photo (image 1); keep the photo/geometry split"),
    "yingzao": _out(1024, 1360, "3:4", 1,
        ("yingzao", "营造·在地编辑海报", "Yingzao Local Editorial Poster"),
        refs="photo (image 1); no invented architecture"),
    # --- multi-ratio packs (3 calls, 1 image each) ---
    "meta-ads-creative-director": _out(1024, 1024, "1:1", 3,
        ("meta-ads-creative-director", "Meta广告创意", "Meta Ads Creative"),
        refs="product/person refs, same on every call",
        calls=[_call(1024, 1024, "1:1", "feed 1:1"),
               _call(1024, 1280, "4:5", "feed 4:5"),
               _call(1024, 1824, "9:16", "story/reel 9:16")]),
    "rednote-cover-maker": _out(1024, 1024, "1:1", 3,
        ("rednote-cover-maker", "小红书封面制作器", "RedNote Cover Maker"),
        refs="product/person refs, same on every call",
        calls=[_call(1024, 1024, "1:1", "feed 1:1"),
               _call(1024, 1280, "4:5", "post 4:5"),
               _call(1024, 1824, "9:16", "story 9:16")]),
    # TODO(design 6874380577): pack composition pending visual review; current
    # 16:9 hero + 1:1 social + 4:5 display.
    "marketing-campaign-generator": _out(1824, 1024, "16:9", 3,
        ("marketing-campaign-generator", "营销活动生成器", "Marketing Campaign Generator"),
        refs="brand/product refs, same on every call",
        calls=[_call(1824, 1024, "16:9", "hero KV 16:9"),
               _call(1024, 1024, "1:1", "social 1:1"),
               _call(1024, 1280, "4:5", "display 4:5")]),
    # --- 9:19.5 phone frames (2 calls) ---
    # Design 6874380577: 9:19.5 is not in the model enum; 9:21 880x2048 (2K long
    # edge) is the supported phone frame, so size lock does not false-alarm.
    "mobile-app-visual-design": _out(880, 2048, "9:21", 2,
        ("mobile-app-visual-design", "移动应用视觉设计", "Mobile APP Visual Design"),
        refs="uploaded refs; phone-framed screens",
        calls=[_call(880, 2048, "9:21", "home screen"),
               _call(880, 2048, "9:21", "detail screen")]),
    # --- 4:3 ---
    "crt-interface": _out(1360, 1024, "4:3", 1,
        ("crt-interface", "CRT 复古界面", "CRT Retro Interface"),
        refs="uploaded refs"),
    # --- video skills: still/image-call default only; film uses generate_video/animate_image ---
    "product-tvc-advertisement-generator": _out(1824, 1024, "16:9", 1,
        ("product-tvc-advertisement-generator", "产品广告片", "Product Commercial"),
        refs="product image (always pass it)", media="video"),
    "motion-poster-generator": _out(1360, 1024, "4:3", 1,
        ("motion-poster-generator", "动态海报", "Motion Poster"),
        refs="source_image (the static artwork)", media="video"),
    "flash-cut-video": _out(1824, 1024, "16:9", 1,
        ("flash-cut-video", "截图闪剪视频", "Screenshot Flash-Cut Video"),
        refs="landscape 16:9 screenshot", media="video"),
    # TODO(design 6874380577): video fallback still pending visual review; current 1:1.
    "anim-2d": _out(1024, 1024, "1:1", 1,
        ("anim-2d", "2D动画转换器", "2D Animation Converter"),
        refs="primary visual", media="video"),
    # TODO(design 6874380577): video fallback still pending visual review; current 4:3.
    "animated-poster": _out(1360, 1024, "4:3", 1,
        ("animated-poster", "动态海报生成器", "Animated Poster Generator"),
        refs="source artwork", media="video"),
    # TODO(design 6874380577): video fallback still pending visual review; current 1:1.
    "logo-animation": _out(1024, 1024, "1:1", 1,
        ("logo-animation", "LOGO动画视频", "Logo Animation Video"),
        refs="logo image (image 1)", media="video"),
    # --- follow-ref (server reads image 1; see FOLLOW_REF_SIZES) ---
    "style-transfer": _out(1024, 1024, "1:1", 1,
        ("style-transfer", "自适应风格迁移导演", "Adaptive Style Transfer Director"),
        refs="content image first, style image second"),
    "person-swap": _out(1024, 1360, "3:4", 3,
        ("person-swap", "电商三图换人", "E-commerce 3-Image Person Swap"),
        refs="scene/pose first, then face and outfit"),
    # --- multi-asset kits (3 calls) ---
    # TODO(design 6874380577): asset count pending visual review; current 3 calls.
    "creator-identity": _out(1024, 1024, "1:1", 3,
        ("creator-identity", "创作者视觉识别系统", "Creator Visual Identity System"),
        refs="creator refs",
        calls=[_call(1024, 1024, "1:1", "avatar 1:1"),
               _call(1824, 1024, "16:9", "channel cover 16:9"),
               _call(1024, 1280, "4:5", "social template 4:5")]),
    # TODO(design 6874380577): asset count pending visual review; current 3 calls.
    "live-promo-decor": _out(1824, 1024, "16:9", 3,
        ("live-promo-decor", "电商直播素材", "Live Commerce Promo Decor"),
        refs="product/stream refs",
        calls=[_call(1824, 1024, "16:9", "background 16:9"),
               _call(1024, 1024, "1:1", "price tag 1:1"),
               _call(1024, 1024, "1:1", "corner badge 1:1")]),
}

# #982: last-resort neutral floor for a custom/unknown skill that is neither in
# OUTPUTS nor managed by a registered pin. Known unpinned skills are typed in
# TYPE_OUTPUTS_982 instead. The floor follows the page's card semantics (1024
# SHORT side), never the old long-side interpretation that shrank wide/portrait
# outputs; `size_lock` still makes a smaller provider file visible.
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
        "width": 1536, "height": 1536, "ratio": "1:1", "images": 1,
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
OUTPUTS.update(TYPE_OUTPUTS_982)

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
# #982: rows whose default delivery is a set of calls, each with its own canvas
# (ratio packs, phone screens, multi-asset kits). Flat row fields = call 1.
CALL_PLAN_SKILLS = frozenset(sid for sid, row in OUTPUTS.items() if row.get("calls"))
# #982: the six video skills. Their image call is a still/storyboard only; the
# film itself is generate_video / animate_image, so they are never single-image.
VIDEO_SKILLS = frozenset(sid for sid, row in OUTPUTS.items() if row.get("media") == "video")


def call_plan(sid: str, ratio: object = "", width: object = 0, height: object = 0) -> dict:
    """#982: the effective call for one generate_image of a multi-call default.

    An explicit ratio (or a width/height pair the relay already filled) selects the
    matching call; otherwise call 1. The model is told each call's ratio in the
    Output lock, so the pack is reachable without a second table."""
    row = OUTPUTS[sid]
    calls = list(row.get("calls") or [])
    if not calls:
        raise KeyError(f"{sid} has no calls")
    chosen = None
    if ratio:
        chosen = next((c for c in calls if str(c.get("ratio")) == str(ratio)), None)
    if chosen is None and width and height:
        chosen = next((c for c in calls
                       if (int(c["width"]), int(c["height"])) == (int(width), int(height))), None)
    if chosen is None:
        chosen = calls[0]
    return {
        "width": int(chosen["width"]),
        "height": int(chosen["height"]),
        "ratio": chosen.get("ratio"),
        "images": int(chosen.get("images") or 1),
        "label": chosen.get("label", ""),
        "index": calls.index(chosen) + 1,
        "calls": calls,
        "total_images": int(row["images"]),
    }


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


# #982 / design 6874380577: the model enums do not name 9:19.5; the supported
# phone frame is 9:21 at 880x2048 (2K long edge). Map the old wording to it so the
# page's RATIOS gate and the size lock do not reject a size-less phone request.
RATIO_ALIASES_982: dict[str, tuple[str, int, int]] = {
    "9:19.5": ("9:21", 880, 2048),
    "9:21": ("9:21", 880, 2048),
}


def pixels_for_ratio(ratio: object) -> tuple[int, int] | None:
    """#982: the page's targetSize semantics: 1024 SHORT side, long side snapped to 16.

    16:9 -> 1824x1024, 3:4 -> 1024x1360, 9:16 -> 1024x1824, 4:3 -> 1360x1024.
    This is deliberately not a 1024 long side: that shrank wide/portrait defaults.
    """
    m = re.fullmatch(r"\s*(\d{1,3}(?:\.\d+)?)\s*[:：]\s*(\d{1,3}(?:\.\d+)?)\s*", str(ratio or ""))
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if not a or not b:
        return None
    snap = lambda v: max(64, round(v / 16) * 16)  # noqa: E731 - one-line 16px snap
    if a >= b:
        return snap(1024 * a / b), 1024
    return 1024, snap(1024 * b / a)


def fill_unpinned_fallback(args: dict, skill: object) -> dict:
    """#982: fill the documented floor for a skill that has no declared canvas.

    A call that would otherwise submit no size gets pixels: the neutral 1:1
    default, or the model's explicit ratio at the page's 1024 SHORT side. Explicit
    width+height and a resolution tier win. A registered skill pin owns its size
    (#708/#911), so pinned skills are left untouched.
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
        alias = RATIO_ALIASES_982.get(str(ratio).strip())
        if alias:
            args["ratio"], args["width"], args["height"] = alias
        else:
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
    if sid in VIDEO_SKILLS:
        # #982: a video skill is never a one-shot still skill; its still path may
        # legitimately run more than once (storyboard/style candidates).
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
# #982: style-transfer follows the content image (image 1); person-swap follows
# the scene/pose base (image 1). These are the page's card sizes at a 1024 short
# side, so a readable reference never produces a smaller request than main.
FOLLOW_REF_SIZES_982 = {
    "1:1": (1024, 1024),
    "4:5": (1024, 1280), "5:4": (1280, 1024),
    "3:4": (1024, 1360), "4:3": (1360, 1024),
    "2:3": (1024, 1536), "3:2": (1536, 1024),
    "9:16": (1024, 1824), "16:9": (1824, 1024),
}
FOLLOW_REF_SIZES["style-transfer"] = FOLLOW_REF_SIZES_982
FOLLOW_REF_SIZES["person-swap"] = FOLLOW_REF_SIZES_982
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
    # #982: a multi-call default (ratio pack / kit / screens) picks the call by
    # explicit ratio or by the pixels the relay already filled; otherwise call 1.
    call = None
    if sid in CALL_PLAN_SKILLS:
        try:
            asked_w = int(args.get("width") or 0)
            asked_h = int(args.get("height") or 0)
        except (TypeError, ValueError):
            asked_w = asked_h = 0
        call = call_plan(sid, args.get("ratio"), asked_w, asked_h)
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
        # #982: a call's own canvas; #979: a preset plan's stage size; otherwise the
        # row's flat default.
        if call:
            width, height, ratio = call["width"], call["height"], call.get("ratio")
        elif plan:
            width, height, ratio = plan["width"], plan["height"], plan.get("ratio")
        else:
            width, height, ratio = int(row["width"]), int(row["height"]), row.get("ratio")
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


def _calls_hint(sid: str, row: dict) -> str:
    """#982: a default set of calls with different canvases (packs, kits, screens)."""
    calls = list(row.get("calls") or [])
    total = int(row["images"])
    parts = []
    for i, call in enumerate(calls, 1):
        n = int(call.get("images") or 1)
        label = f" ({call['label']})" if call.get("label") else ""
        parts.append(f"call {i}{label} = {n} image(s) at "
                     f"{_size_text(sid, int(call['width']), int(call['height']), call.get('ratio'))}")
    refs = f" Refs: {row['refs']}." if row.get("refs") else ""
    return (
        f"Output lock: deliver exactly {total} separate images in {len(calls)} calls: "
        + "; ".join(parts)
        + f". Call generate_image exactly {total} times, count=1 each, with a different prompt per call; "
          f"pass skill={sid!r} and that call's ratio on every call. Do not use 1024x1024 unless that call says so."
        + refs
    )


def _video_hint(sid: str, row: dict) -> str:
    """#982: a video skill's still/storyboard default, never a one-image film."""
    size = _size_text(sid, int(row["width"]), int(row["height"]), row.get("ratio"))
    refs = f" Refs: {row['refs']}." if row.get("refs") else ""
    return (
        f"Output lock: {sid!r} is a video skill. The final deliverable is a video via generate_video or "
        f"animate_image, not a single generate_image. If you generate a still/storyboard frame, use "
        f"skill={sid!r}, {size}, count=1; do not submit a size-less image. The film's own "
        "ratio and duration belong to the generate_video/animate_image flow, not this image lock."
        + refs
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
    row = OUTPUTS[sid]
    if sid in CALL_PLAN_SKILLS:
        return _calls_hint(sid, row)
    if sid in VIDEO_SKILLS:
        return _video_hint(sid, row)
    if sid in PRESET_PLAN_SKILLS:
        return _preset_hint(sid, preset_id, user_text)
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
    refs = f" Refs: {row['refs']}." if row.get("refs") else ""
    if int(row["images"]) == 1:
        return (
            f"Output lock: call generate_image exactly once with skill={sid!r}, {size}, count=1. "
            "Do not call list_models, expand_image, or create_frame. Do not outpaint. "
            "Then wait_generation and finish. Lettering must be real words in quotes, large enough to read."
            + refs
        )
    if sid in FOLLOW_REF_SIZES:
        # #982: person-swap is a 3-frame set, not the generic pose-fission wording.
        return (
            f"Output lock: deliver exactly {int(row['images'])} separate images, each at the size and ratio "
            "of image 1 (the server fills width, height and ratio; do not pass them), count=1. "
            f"Call generate_image {int(row['images'])} times, one useful frame per call "
            "(hero, side/detail, ...), with a different prompt each time; pass skill={sid!r} and every "
            "uploaded ref on every call." + refs
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
