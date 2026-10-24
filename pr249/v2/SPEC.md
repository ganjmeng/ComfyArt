# pr249/v2 — Jingmeng 2026-10-25 locked direction

Supersedes peripheral-only freeze. Voids putting 四角度 into preset chips (v3 row4 wrong).

## Locks

1. **一次生成 4 个角度** — separate bottom control above 取消/生成 (main pattern). NOT in preset chips.
2. **预览** — keep tab AND camera viewport corner live preview thumbnail.
3. **Sliders** — Lovart-leaning: thin track, circular thumb, **no tick marks**.
4. **Presets** — remove **正面** only. Keep 左前, 右前, 左侧, 右侧, **背面**, 俯视, 仰视, 特写, 中等, 广角.
5. **3D** — light polish on existing main gizmos (cleaner edges, soft contact shadow, smaller hint text). Same interaction model. NOT detail-v1/v3 redraw; NOT Lovart 主体/摄像头 rename.
6. **Chrome** — Lovart-leaning spacing/radius/shadow from peripheral-v1 feel.

Panel chrome: 相机/对象/预览 (Chinese as main), 水平/垂直/远近, 取消/生成.

## Compares

Three columns: **Lovart 实测 | 当前 main | 我们 v2**.
- zh-light: full 3-col for 对象 + 相机 (Lovart crops from `/workspace/lovart-ma/` box 812,148,1015,548).
- zh-dark: same layout; Lovart column notes no dark capture.

## Out of scope

- detail-v1 voided; #254 generate-blocked out of scope
- Do not rename tabs to 主体/摄像头
