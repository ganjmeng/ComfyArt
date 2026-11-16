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
