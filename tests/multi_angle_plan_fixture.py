"""Mock agent-generated plan for the headphones fixture; NEVER production defaults."""
HEADPHONES_PLAN = {
    "subject": "gray over-ear headphones from the supplied reference",
    "purpose": "商品详情页，纯白无缝背景 / PDP white seamless",
    "subject_geometry": "over-ear headphones with oval earcups, headband and yokes",
    "appearance": "gray reference material, pure white seamless background",
    "panels": [
        {"id": str(i), "name": name, "description": description, "geometry": description, "appearance": ""}
        for i, (name, description) in enumerate([
            ("正面全景", "front full headphones, earcups and headband symmetrically visible"),
            ("四分之三全景", "three-quarter full headphones showing earcup depth and curved headband"),
            ("90°侧面", "strict 90-degree side profile showing the earcup shell silhouette"),
            ("耳罩内衬", "inside earcup cushion detail and lining texture"),
            ("外壳细节", "outer earcup shell and surface finish close-up"),
            ("后侧轮廓", "rear three-quarter headphones showing yoke and headband joins"),
            ("顶部结构", "top-down view of headband arc and cup spacing"),
            ("连接处", "close-up of headband adjustment joint without inventing controls"),
            ("低角度展示", "low product angle emphasizing earcup volume and headband curve"),
        ], 1)
    ],
}

# Exact frozen plan from the 2026-11-17 scripted paid failure (0 LLM, $0.2763).
# Source: /workspace/qa1002-0f0e9328-appstack-paid/paid/chat-after-composition-card.json
# Embedded so tests do not depend on a symlink to the archive. Do not rewrite IDs or geometry.
PAID_FAILURE_PLAN = {
    "subject": "matte gray over-ear headphones in the supplied front-view reference: cushioned oval earcups, padded headband, slim yokes, no visible logo or extra controls invented",
    "purpose": "商品详情页，纯白无缝背景 / product detail page on a seamless pure-white background",
    "panels": [
        {"id": "1", "name": "正面全景", "description": "front-on full product, both earcups and the padded headband symmetrically visible, exact gray materials, pure white seamless background"},
        {"id": "2", "name": "四分之三全景", "description": "three-quarter view of the same headphones showing earcup depth, yoke, and headband curve, identity unchanged, white seamless"},
        {"id": "3", "name": "90°侧面轮廓", "description": "strict 90-degree side profile of one earcup shell and headband arc, silhouette accurate to the reference, white seamless"},
        {"id": "4", "name": "耳罩内衬特写", "description": "close-up of the visible cushion/lining texture inside an earcup, do not invent hidden electronics, white seamless"},
        {"id": "5", "name": "外壳表面特写", "description": "outer earcup shell and matte surface finish close-up matching the reference plastic, white seamless"},
        {"id": "6", "name": "后侧连接", "description": "rear three-quarter view showing how the headband meets the yokes, same product, white seamless"},
        {"id": "7", "name": "顶部头梁", "description": "top-down view of the headband arc and spacing between cups, proportions from the reference, white seamless"},
        {"id": "8", "name": "调节连接处", "description": "close-up of the headband-to-cup joint only as visible in the reference, do not invent sliders or buttons, white seamless"},
        {"id": "9", "name": "低角度体积", "description": "low product angle emphasizing earcup volume and the curve of the headband, same gray headphones, white seamless"},
    ],
}


# #1003: finals crop the selected cell from the delivered preview FILE, so test previews are a
# real synthetic image with UNEQUAL cells (never equal thirds), an outer frame, number labels and
# one drawing per cell. Written under the stubbed ComfyUI output dir like a WaveSpeed download.
GRID_W, GRID_H = 900, 1600
GRID_X, GRID_Y = (330, 610), (520, 1090)


def grid_png(w=GRID_W, h=GRID_H, xs=GRID_X, ys=GRID_Y, *, slant=0, stroke=3, frame=True, labels=True, lines=True):
    import io
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    if frame:
        d.rectangle([0, 0, w - 1, h - 1], outline="black", width=2)
    if lines:
        for x in xs:
            d.line([(x - slant // 2, 0), (x + slant - slant // 2, h)], fill="black", width=stroke)
        for y in ys:
            d.line([(0, y), (w, y)], fill="black", width=stroke)
    bx, by = [0, *xs, w], [0, *ys, h]
    for r in range(3):
        for c in range(3):
            x0, x1, y0, y1 = bx[c], bx[c + 1], by[r], by[r + 1]
            if labels:  # a "number": small isolated glyph cluster in the top-left corner
                d.rectangle([x0 + 14, y0 + 14, x0 + 18, y0 + 40], fill="black")
                d.rectangle([x0 + 10, y0 + 14, x0 + 16, y0 + 18], fill="black")
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            rw, rh = (x1 - x0) // 3, (y1 - y0) // 3
            d.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], outline="black", width=3)
            d.line([(cx - rw, cy), (cx + rw, cy)], fill="black", width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def preview_url(name="ma-preview-test.png", **kw):
    """Write the synthetic preview into the (per-test) output dir; return its /api/view URL."""
    import os
    import folder_paths
    root = os.path.join(folder_paths.get_output_directory(), "wavespeed")
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, name), "wb") as f:
        f.write(grid_png(**kw))
    return f"/api/view?filename={name}&subfolder=wavespeed&type=output"
