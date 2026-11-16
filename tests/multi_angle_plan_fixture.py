"""Mock agent-generated plan for the headphones fixture; NEVER production defaults."""
HEADPHONES_PLAN = {
    "subject": "gray over-ear headphones from the supplied reference",
    "purpose": "商品详情页，纯白无缝背景 / PDP white seamless",
    "panels": [
        {"id": str(i), "name": name, "description": description}
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
