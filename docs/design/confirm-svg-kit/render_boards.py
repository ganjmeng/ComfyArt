#!/usr/bin/env python3
"""Static visual proposals for the confirm / SVG kit.

Draws proposal pixels only. Lovart crops and QA befores are pasted from files.
Nothing here is a Lovart screenshot.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
BEFORE = ROOT / "before"
REFS = ROOT / "refs"
OUT = ROOT / "boards"
SCALE = 2

INTER = {
    "regular": "/usr/share/fonts/truetype/macos/Inter-Regular.ttf",
    "medium": "/usr/share/fonts/truetype/macos/Inter-Medium.ttf",
    "semibold": "/usr/share/fonts/truetype/macos/Inter-SemiBold.ttf",
}
WQY = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
_FONT: dict[tuple, ImageFont.FreeTypeFont] = {}

INK = (26, 26, 26)
MUTED = (92, 92, 92)
FAINT = (122, 122, 122)
LINE = (231, 231, 231)
PAPER = (255, 255, 255)
PAGE = (244, 244, 242)
SCRIM = (102, 102, 102)
PRIMARY = (44, 44, 44)  # measured pill fill, used as a suggestion on dialog buttons
DANGER = (231, 77, 61)
FOCUS = (59, 130, 246)
MOCK = (90, 74, 42)
MOCK_BG = (246, 240, 224)


def sx(n: float) -> int:
    return int(round(n * SCALE))


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    key = (size, weight)
    if key not in _FONT:
        path = INTER[weight] if weight in INTER else WQY
        # Inter has no CJK. WQY covers both, so UI strings use WQY.
        _FONT[key] = ImageFont.truetype(WQY, sx(size), index=0)
    return _FONT[key]


def text(d: ImageDraw.ImageDraw, xy, s, size, fill=INK, weight="regular"):
    d.text((sx(xy[0]), sx(xy[1])), s, font=font(size, weight), fill=fill)


def text_w(s: str, size: int) -> int:
    box = font(size).getbbox(s)
    return (box[2] - box[0]) / SCALE


def tokens(s: str) -> list[str]:
    """Keep words and uiCredits intact. Spaces are their own tokens so lines can break."""
    out, buf = [], ""
    for ch in s:
        if ord(ch) < 128 and not ch.isspace():
            buf += ch
        else:
            if buf:
                out.append(buf)
                buf = ""
            if ch != "\n":
                out.append(ch)
    if buf:
        out.append(buf)
    return out


def wrap(s: str, size: int, max_w: int) -> list[str]:
    if not s:
        return []
    lines, cur = [], ""
    for tok in tokens(s):
        if text_w(tok, size) > max_w and len(tok) > 1:
            if cur:
                lines.append(cur)
                cur = ""
            for ch in tok:
                trial = cur + ch
                if text_w(trial, size) <= max_w:
                    cur = trial
                else:
                    if cur:
                        lines.append(cur)
                    cur = ch
            continue
        trial = cur + tok
        if text_w(trial, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = tok.lstrip() if tok.startswith(" ") else tok
    if cur:
        lines.append(cur)
    return lines


def rrect(d, box, radius, fill=None, outline=None, width=1):
    x0, y0, x1, y1 = [sx(v) for v in box]
    r = sx(radius)
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=fill, outline=outline, width=sx(width) if outline else 1)


def paste(board: Image.Image, src: Image.Image, xy, w, h=None):
    tw = sx(w)
    th = sx(h) if h else int(src.height * tw / src.width)
    fitted = src.resize((tw, th), Image.Resampling.LANCZOS)
    board.paste(fitted, (sx(xy[0]), sx(xy[1])))
    return th / SCALE


def tag(d, xy, label, kind):
    colors = {
        "measured": ((226, 239, 224), (30, 92, 40)),
        "suggest": ((255, 244, 214), (122, 78, 10)),
        "before": ((232, 232, 230), (50, 50, 50)),
        "proposal": ((226, 234, 248), (28, 64, 130)),
    }
    bg, fg = colors[kind]
    pad_x, h = 8, 18
    w = text_w(label, 11) + pad_x * 2
    rrect(d, (xy[0], xy[1], xy[0] + w, xy[1] + h), 9, fill=bg)
    text(d, (xy[0] + pad_x, xy[1] + 2), label, 11, fg)
    return w


def header(d, w, title, note):
    text(d, (28, 20), title, 20)
    text(d, (28, 48), note, 12, MUTED)
    return 78


def footer(d, w, h, note):
    text(d, (28, h - 28), note, 11, FAINT)


def button(d, xy, label, variant, state="default", width=None, height=36):
    """Dialog button. Radius 8 is a suggestion; measured dialog radius is 6–7."""
    pad = 16
    label_w = text_w(label, 14)
    w = width or max(80, label_w + pad * 2)
    h = height
    x, y = xy
    radius = 8
    if state == "disabled":
        rrect(d, (x, y, x + w, y + h), radius, fill=(232, 232, 232), outline=(214, 214, 214), width=1)
        text(d, (x + (w - label_w) / 2, y + 9), label, 14, (168, 168, 168))
        return w
    if variant == "primary":
        fill = (68, 68, 68) if state == "hover" else PRIMARY
        fg = PAPER
        outline = None
    elif variant == "danger":
        fill = (212, 69, 54) if state == "hover" else DANGER
        fg = PAPER
        outline = None
    elif variant == "ghost":
        fill = (244, 244, 244) if state == "hover" else None
        fg = INK
        outline = None
    else:
        fill = (245, 245, 245) if state == "hover" else PAPER
        fg = INK
        outline = LINE
    if state == "loading":
        fill = (232, 232, 232) if variant == "secondary" or variant == "ghost" else ((90, 90, 90) if variant == "primary" else (212, 160, 154))
        fg = PAPER if variant in ("primary", "danger") else INK
        track = (200, 200, 200) if variant in ("primary",) else (210, 210, 210)
        if variant == "primary":
            track = (120, 120, 120)
            fg = PAPER
        rrect(d, (x, y, x + w, y + h), radius, fill=fill, outline=outline, width=1)
        cx, cy, r = x + w / 2, y + h / 2, 7
        box = [sx(cx - r), sx(cy - r), sx(cx + r), sx(cy + r)]
        d.arc(box, 0, 360, fill=track, width=sx(2))
        d.arc(box, -30, 80, fill=fg, width=sx(2))
    else:
        rrect(d, (x, y, x + w, y + h), radius, fill=fill, outline=outline, width=1)
        text(d, (x + (w - label_w) / 2, y + 9), label, 14, fg)
    if state == "focus":
        rrect(d, (x - 3, y - 3, x + w + 3, y + h + 3), radius + 3, outline=FOCUS, width=2)
    return w


def draw_dialog(d, origin, spec) -> float:
    x, y = origin
    width = spec["width"]
    pad = 24
    inner = width - pad * 2
    rrect(d, (x, y, x + width, y + 8), 12, fill=PAPER)  # placeholder, redrawn after height known
    cursor = y + pad
    text(d, (x + pad, cursor), spec["title"], 16)
    cursor += 28
    text(d, (x + pad, cursor), spec["model"], 13, MUTED)
    cursor += 28
    facts = spec["facts"]
    narrow = width < 380
    if narrow:
        for fact in facts:
            text(d, (x + pad, cursor), fact["label"], 12, FAINT)
            cursor += 16
            text(d, (x + pad, cursor), fact["value"], 22)
            vw = text_w(fact["value"], 22)
            text(d, (x + pad + vw + 6, cursor + 6), fact["unit"], 13, MUTED)
            if fact.get("mock"):
                tag(d, (x + pad + vw + text_w(fact["unit"], 13) + 14, cursor + 4), "mock", "suggest")
            cursor += 32
    else:
        col = inner / 3
        for i, fact in enumerate(facts):
            fx = x + pad + col * i
            text(d, (fx, cursor), fact["label"], 12, FAINT)
            text(d, (fx, cursor + 18), fact["value"], 22)
            vw = text_w(fact["value"], 22)
            text(d, (fx + vw + 6, cursor + 24), fact["unit"], 13, MUTED)
            if fact.get("mock"):
                tag(d, (fx + vw + text_w(fact["unit"], 13) + 14, cursor + 22), "mock", "suggest")
        cursor += 52
    if spec.get("adjust"):
        text(d, (x + pad, cursor), spec.get("kicker_adjust", "已调整"), 12, FAINT)
        cursor += 18
        for line in wrap(spec["adjust"], 13, inner):
            text(d, (x + pad, cursor), line, 13, MUTED)
            cursor += 20
        cursor += 4
    # canonical sentence, secondary
    text(d, (x + pad, cursor), spec.get("kicker_sr", "读屏原文 · 不改 confirmDesc"), 11, FAINT)
    cursor += 16
    for line in wrap(spec["sentence"], 12, inner):
        text(d, (x + pad, cursor), line, 12, MUTED)
        cursor += 18
    cursor += 8
    # mock notice
    note_h = 8
    note_lines = wrap(spec["mock"], 12, inner - 16)
    note_h = 10 + 18 * len(note_lines) + 6
    rrect(d, (x + pad, cursor, x + width - pad, cursor + note_h), 8, fill=MOCK_BG)
    ny = cursor + 8
    for line in note_lines:
        text(d, (x + pad + 10, ny), line, 12, MOCK)
        ny += 18
    cursor += note_h + 16
    # buttons
    cancel, ok = spec["cancel"], spec["ok"]
    focus = spec.get("focus")
    bw_ok = max(80, text_w(ok, 14) + 32)
    bw_cancel = max(80, text_w(cancel, 14) + 32)
    if bw_ok + bw_cancel + 8 > inner:
        button(d, (x + pad, cursor), cancel, "secondary", "focus" if focus == "cancel" else "default", width=inner)
        cursor += 44
        button(d, (x + pad, cursor), ok, "primary", "focus" if focus == "ok" else "default", width=inner)
        cursor += 36
    else:
        right = x + width - pad
        button(d, (right - bw_ok, cursor), ok, "primary", "focus" if focus == "ok" else "default", width=bw_ok)
        button(d, (right - bw_ok - 8 - bw_cancel, cursor), cancel, "secondary", "focus" if focus == "cancel" else "default", width=bw_cancel)
        cursor += 36
    height = cursor + pad - y
    # paint card behind content by redrawing border only; fill was incremental.
    # Redraw a border on top so the card edge is visible. Fill already painted per control;
    # paint the card fill FIRST by using a destination that we composite. Simpler: stroke only.
    rrect(d, (x, y, x + width, y + height), 12, outline=(230, 230, 230), width=1)
    return height


def new_page(w, h):
    im = Image.new("RGB", (sx(w), sx(h)), PAGE)
    return im, ImageDraw.Draw(im)


def stage(d, box):
    rrect(d, box, 12, fill=SCRIM)


def confirm_specs():
    model = "openai/gpt-image-2.6-flare/text-to-image"
    mock = "示例 7 积分来自 QA mock（USD 0.07 → uiCredits = 7）。不是实时价格，也不改报价。"
    facts = [
        {"label": "费用", "value": "7", "unit": "积分", "mock": True},
        {"label": "有效帧数", "value": "16", "unit": "帧"},
        {"label": "每帧时长", "value": "20", "unit": "毫秒"},
    ]
    zh = {
        "title": "确认费用",
        "model": model,
        "facts": facts,
        "adjust": "帧数 99 → 16 · 每帧 5 → 20 毫秒",
        "sentence": "这次云端生成约需 7 积分，GIF 16 帧（已从 99 帧调整），每帧 20 毫秒（已从 5 毫秒调整），确定继续吗？",
        "mock": mock,
        "cancel": "取消",
        "ok": "继续生成",
        "width": 440,
        "focus": "cancel",
    }
    en = {
        **zh,
        "title": "Confirm cost",
        "facts": [
            {"label": "Cost", "value": "7", "unit": "credits", "mock": True},
            {"label": "Valid frames", "value": "16", "unit": "frames"},
            {"label": "Per frame", "value": "20", "unit": "ms"},
        ],
        "adjust": "Frames 99 → 16 · Per frame 5 → 20 ms",
        "sentence": "This cloud job costs about 7 credits, GIF 16 frames (adjusted from 99), 20 ms per frame (adjusted from 5). Continue?",
        "mock": "The 7 credits are a QA mock (USD 0.07 → uiCredits = 7). Not a live price.",
        "cancel": "Cancel",
        "ok": "Generate",
        "kicker_adjust": "Adjusted",
        "kicker_sr": "Screen text · confirmDesc unchanged",
    }
    plain = {
        **zh,
        "facts": [
            {"label": "费用", "value": "7", "unit": "积分", "mock": True},
            {"label": "有效帧数", "value": "9", "unit": "帧"},
            {"label": "每帧时长", "value": "200", "unit": "毫秒"},
        ],
        "adjust": "",
        "sentence": "这次云端生成约需 7 积分，GIF 9 帧，每帧 200 毫秒，确定继续吗？",
    }
    return zh, en, plain


def board_confirm(name, before_name, spec, blurb):
    before = Image.open(BEFORE / before_name).convert("RGB")
    col_w = 700
    before_h = before.height * col_w / before.width
    # measure dialog by drawing on a scratch
    scratch = Image.new("RGB", (sx(520), sx(640)), SCRIM)
    sd = ImageDraw.Draw(scratch)
    dh = draw_dialog(sd, (20, 20), spec)
    page_h = int(96 + max(before_h, dh + 36) + 48)
    page_w = 28 + col_w + 24 + col_w + 28
    im, d = new_page(page_w, page_h)
    header(d, page_w, "确认费用 · 视觉对照", blurb)
    y = 86
    tag(d, (28, y), "BEFORE · QA mock · 不是 Lovart", "before")
    tag(d, (28 + col_w + 24, y), "提案 · 不是 Lovart 截图", "proposal")
    y += 26
    paste(im, before, (28, y), col_w)
    stage(d, (28 + col_w + 24, y, 28 + col_w + 24 + col_w, y + before_h))
    dx = 28 + col_w + 24 + (col_w - spec["width"]) / 2
    dy = y + max(16, (before_h - dh) / 2)
    # repaint dialog onto the real board. draw_dialog strokes last but fill of card
    # is not a single rect, so paint a white card first.
    rrect(d, (dx, dy, dx + spec["width"], dy + dh), 12, fill=PAPER)
    draw_dialog(d, (dx, dy), spec)
    footer(d, page_w, page_h, "左：上传的 QA mock 原图。右：按实测弹窗骨架重排的提案。费用 7 积分标明 mock。")
    im.save(OUT / name, optimize=True)


def board_measured():
    w, h = 1480, 1220
    im, d = new_page(w, h)
    header(d, w, "实测参考 · 只贴原像素", "这些裁图来自仓内 Lovart 截图。标注是本轮量到的数。没有的状态不在这张板上。")
    items = [
        (REFS / "lovart-381-confirm-dialog.png", 28, 96, 460, "确认框 default", "418×188 · 圆角拟合 12 · 内边距约 24"),
        (REFS / "lovart-381-buttons.png", 520, 96, 420, "确认框按钮 default", "各约 80×36 · 间距 8 · 圆角 6–7 · 危险色 #E74D3D"),
        (REFS / "lovart-381-primary-pill.png", 980, 96, 280, "非危险实心按钮", "143×48 · 填充 #2C2C2C · 胶囊圆角 24"),
        (REFS / "lovart-381-toast.png", 28, 460, 280, "Toast", "117×48 · 圆角拟合 R11 · 文字墨迹高 12"),
        (REFS / "lovart-376-notify-empty.png", 360, 460, 320, "通知空态", "外框约 383×200 · 边 #EDEDED · 圆角量级 9–10"),
        (REFS / "lovart-376-close-hover.png", 760, 460, 200, "关闭悬停", "底约 #F0F0F0 · 光标挡住右缘，不报宽高"),
        (REFS / "lovart-381-toolbar-under-scrim.png", 28, 900, 760, "工具条（遮罩下）", "能看见结构。遮罩压暗，本轮不报 px"),
    ]
    for path, x, y, width, title, cap in items:
        src = Image.open(path).convert("RGB")
        ph = paste(im, src, (x, y + 22), width)
        text(d, (x, y), title, 13)
        text(d, (x, y + 28 + ph), cap, 12, MUTED)
    footer(d, w, h, "来源见 SOURCES.md。深色确认框、费用内容、SVG 三态、hover/focus/disabled/loading 没有可计量的 Lovart 图，不放在本板冒充实测。")
    im.save(OUT / "00-measured-references.png", optimize=True)


def board_buttons():
    w, h = 1280, 760
    im, d = new_page(w, h)
    header(d, w, "Button · default 有实测，其余是建议", "费用确认的主按钮不用删除红。尺寸沿用确认框 36 高；填充沿用胶囊实测 #2C2C2C。圆角 8 是建议。")
    src = Image.open(REFS / "lovart-381-buttons.png").convert("RGB")
    tag(d, (28, 90), "实测 default · 最近邻不重绘", "measured")
    paste(im, src, (28, 116), 520)
    text(d, (28, 250), "危险实心只用于删除这类操作。费用确认不使用这个红色。", 12, MUTED)
    pill = Image.open(REFS / "lovart-381-primary-pill.png").convert("RGB")
    tag(d, (580, 90), "实测非危险实心 · 另一组件", "measured")
    paste(im, pill, (580, 120), 360)
    text(d, (580, 250), "胶囊是记忆页底部按钮，不是确认框里的那对。确认框不改成胶囊。", 12, MUTED)

    text(d, (28, 300), "建议状态 · 非实测 Lovart", 16)
    rows = [("secondary", "取消"), ("primary", "继续生成"), ("danger", "删除"), ("ghost", "下载")]
    states = ["default", "hover", "focus", "disabled", "loading"]
    labels = ["default", "hover", "focus", "disabled", "loading"]
    for i, lab in enumerate(labels):
        text(d, (180 + i * 180, 336), lab, 12, FAINT)
    for r, (variant, label) in enumerate(rows):
        yy = 364 + r * 64
        text(d, (28, yy + 10), variant, 13, MUTED)
        for c, state in enumerate(states):
            button(d, (180 + c * 180, yy), label, variant, state, width=148)
    footer(d, w, h, "hover / focus / disabled / loading 仓内没有对应 Lovart 截图。焦点环 #3B82F6 来自仓内 --ca-blue，不是这轮量到的。")
    im.save(OUT / "04-button-states.png", optimize=True)


def checker(d, box, cell=8):
    x0, y0, x1, y1 = box
    y = y0
    row = 0
    while y < y1:
        x = x0
        col = 0
        while x < x1:
            if (row + col) % 2 == 0:
                d.rectangle([sx(x), sx(y), sx(min(x + cell, x1)), sx(min(y + cell, y1))], fill=(228, 228, 228))
            x += cell
            col += 1
        y += cell
        row += 1


def icon_image(d, cx, cy, color):
    rrect(d, (cx - 16, cy - 14, cx + 16, cy + 12), 3, outline=color, width=2)
    d.line([sx(cx - 10), sx(cy + 6), sx(cx - 2), sx(cy - 2), sx(cx + 6), sx(cy + 4), sx(cx + 14), sx(cy - 8)], fill=color, width=sx(2))
    d.line([sx(cx - 18), sx(cy - 16), sx(cx + 18), sx(cy + 16)], fill=color, width=sx(2))


def icon_block(d, cx, cy):
    d.ellipse([sx(cx - 22), sx(cy - 22), sx(cx + 22), sx(cy + 22)], fill=(253, 236, 236))
    d.line([sx(cx - 10), sx(cy - 10), sx(cx + 10), sx(cy + 10)], fill=DANGER, width=sx(3))
    d.line([sx(cx + 10), sx(cy - 10), sx(cx - 10), sx(cy + 10)], fill=DANGER, width=sx(3))


def preview_card(d, origin, kind) -> float:
    x, y = origin
    w = 360
    rrect(d, (x, y, x + w, y + 300), 12, fill=PAPER, outline=(230, 230, 230), width=1)
    stage_box = (x + 16, y + 16, x + w - 16, y + 168)
    if kind == "ok":
        rrect(d, stage_box, 8, fill=PAPER)
        checker(d, (stage_box[0] + 1, stage_box[1] + 1, stage_box[2] - 1, stage_box[3] - 1), 8)
        d.rectangle([sx(x + 140), sx(y + 58), sx(x + 220), sx(y + 138)], fill=(0, 200, 70))
        text(d, (x + 16, y + 176), "显示层棋盘格。下载的仍是原来的 SVG。", 12, MUTED)
        button(d, (x + 16, y + 214), "下载原 SVG", "secondary", width=140, height=32)
        text(d, (x + 168, y + 222), "正常 · 可下载", 12, FAINT)
    elif kind == "failed":
        rrect(d, stage_box, 8, fill=(248, 244, 234))
        icon_image(d, x + w / 2, y + 78, (138, 106, 48))
        text(d, (x + 16, y + 176), "安全校验已通过，但本地画不出像素。", 12, (106, 75, 22))
        text(d, (x + 16, y + 194), "例如只有文字。原文件仍可下载。", 12, (106, 75, 22))
        button(d, (x + 16, y + 230), "下载原 SVG", "secondary", width=140, height=32)
    else:
        rrect(d, stage_box, 8, fill=(253, 236, 236))
        icon_block(d, x + w / 2, y + 78)
        lines = wrap("这份 SVG 含有脚本或不允许的内容，不能预览，也不能下载。", 13, w - 32)
        yy = y + 176
        for line in lines:
            text(d, (x + 16, yy), line, 13, (155, 44, 44))
            yy += 20
        text(d, (x + 16, yy + 8), "没有下载入口。", 13, (155, 44, 44))
    return 300


def board_svg():
    w, h = 1180, 860
    im, d = new_page(w, h)
    header(d, w, "SVG 三态 · BEFORE 是夹具，提案不是 Lovart", "Lovart 仓内没有这三态的参考。右侧全部是设计建议。棋盘格只画在显示层。")
    pairs = [
        ("826-01-path-preview.png", "ok", "正常 · 透明"),
        ("826-02-preview-failed.png", "failed", "安全但画不出"),
        ("826-03-rejected.png", "rejected", "危险拒绝"),
    ]
    for i, (fn, kind, title) in enumerate(pairs):
        x = 28 + i * 384
        text(d, (x, 88), title, 14)
        tag(d, (x, 112), "BEFORE · #826 夹具", "before")
        src = Image.open(BEFORE / fn).convert("RGB")
        paste(im, src, (x, 138), 360)
        tag(d, (x, 400), "提案 · 非实测 Lovart", "suggest")
        preview_card(d, (x, 428), kind)
    footer(d, w, h, "BEFORE 源：#844 b00d0b3 docs/qa/826。失败保留下载；拒绝不出现下载。两者图标和底色不同。")
    im.save(OUT / "05-svg-three-states.png", optimize=True)


def board_notice():
    w, h = 1180, 720
    im, d = new_page(w, h)
    header(d, w, "Notice 与下载工具条", "Toast 尺寸有实测。工具条 px、三态文案、焦点环是建议。")
    tag(d, (28, 90), "实测 toast 原像素", "measured")
    src = Image.open(REFS / "lovart-381-toast.png").convert("RGB")
    paste(im, src, (28, 116), 280)
    text(d, (28, 250), "117×48，白底，红色小图标。没有费用提示的 Lovart 图。", 12, MUTED)

    tag(d, (360, 90), "建议 · 对话框内 mock 提示", "suggest")
    rrect(d, (360, 120, 1120, 168), 10, fill=MOCK_BG)
    text(d, (376, 134), "示例 7 积分是 QA mock，不是实时价格。", 14, MOCK)

    tag(d, (360, 190), "建议 · 失败提示（可下载）", "suggest")
    rrect(d, (360, 216, 1120, 276), 10, fill=(248, 244, 234))
    text(d, (376, 234), "预览没有画出来。安全校验已通过，原 SVG 仍可下载。", 14, (106, 75, 22))

    tag(d, (360, 300), "建议 · 拒绝提示（无下载）", "suggest")
    rrect(d, (360, 326, 1120, 386), 10, fill=(253, 236, 236))
    text(d, (376, 344), "已拒绝。不能预览，也不能下载。", 14, (155, 44, 44))

    text(d, (28, 430), "下载工具条 · 建议", 16)
    # three toolbar states
    bars = [
        (28, "正常 / 失败", True),
        (420, "键盘焦点", "focus"),
        (800, "拒绝", False),
    ]
    for x, title, mode in bars:
        text(d, (x, 468), title, 13, MUTED)
        if mode is False:
            rrect(d, (x, 496, x + 340, 560), 14, outline=(210, 210, 210), width=1)
            text(d, (x + 16, 514), "不渲染下载工具条", 14, (155, 44, 44))
        else:
            rrect(d, (x, 496, x + 340, 560), 14, fill=PAPER, outline=LINE, width=1)
            st = "focus" if mode == "focus" else "default"
            button(d, (x + 176, 508), "下载原 SVG", "secondary", st, width=140, height=32)
            text(d, (x + 16, 514), "原文件", 13, MUTED)
    footer(d, w, h, "工具条高度 44、圆角 14 沿用仓内 .ca-bar，不是本轮从遮罩图量到的。拒绝态不放禁用的下载按钮。")
    im.save(OUT / "06-notice-and-toolbar.png", optimize=True)


def board_narrow():
    zh, en, plain = confirm_specs()
    narrow = {**zh, "width": 312, "focus": "cancel"}
    long = {**en, "width": 440, "focus": "ok"}
    scratch = Image.new("RGB", (sx(800), sx(900)), PAGE)
    sd = ImageDraw.Draw(scratch)
    h1 = draw_dialog(sd, (0, 0), narrow)
    h2 = draw_dialog(sd, (0, 0), long)
    page_w, page_h = 1180, int(110 + max(h1, h2) + 56)
    im, d = new_page(page_w, page_h)
    header(d, page_w, "窄屏与长英文 · 建议", "没有 Lovart 窄屏或英文费用框。初始焦点画在「取消」上，避免回车直接扣费。")
    tag(d, (28, 86), "360 宽屏内 · 卡片 312", "suggest")
    tag(d, (400, 86), "长英文 · 焦点在主按钮（Tab 之后）", "suggest")
    y = 116
    rrect(d, (28, y, 28 + 312, y + h1), 12, fill=PAPER)
    draw_dialog(d, (28, y), narrow)
    rrect(d, (400, y, 400 + 440, y + h2), 12, fill=PAPER)
    draw_dialog(d, (400, y), long)
    footer(d, page_w, page_h, "窄屏事实竖排。英文句子换行，不裁切数字。Esc 与遮罩等于取消。确认框不加关闭叉。")
    im.save(OUT / "07-narrow-and-focus.png", optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    zh, en, plain = confirm_specs()
    board_measured()
    board_confirm(
        "01-confirm-zh-adjusted.png",
        "qa-confirm-zh-adjusted.png",
        zh,
        "已调整的帧数和毫秒降为次级信息。主行是费用、有效帧数、每帧时长。",
    )
    board_confirm(
        "02-confirm-en-long.png",
        "qa-confirm-en-adjusted.png",
        {**en, "focus": "cancel"},
        "长英文换行。7 credits 仍标明 mock。按钮保持「Cancel / Generate」。",
    )
    board_confirm(
        "03-confirm-zh-plain.png",
        "qa-confirm-zh-plain.png",
        {**plain, "focus": "cancel"},
        "请求里没有原始整数时，不出现「已调整」。对应 9 帧、每帧 200 毫秒。",
    )
    board_buttons()
    board_svg()
    board_notice()
    board_narrow()
    for p in sorted(OUT.glob("*.png")):
        print(p.name, Image.open(p).size)


if __name__ == "__main__":
    main()
