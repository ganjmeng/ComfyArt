# lovart-align-v1 — Lovart dialog chrome + product locks

Mock-only review assets for YohakuX/ComfyArt #249. `$0`. No production code.

## Layout (2-col)
Left = Lovart 实测 · Right = ours (lovart-align-v1)

## Product locks
1. Dialog shell + segmented tabs **主体 / 摄像头** (Lovart style: gray track + white elevated pill).
2. Header top-right: **重置 + 预览** both (ours). Lovart left remains reset-only as measured.
3. Corner live preview thumbnail kept on **摄像头** stage (not a tab).
4. **四角度** = separate bottom button「一次生成 4 个角度」(not in preset chips).
5. Lovart thin continuous sliders, circular thumbs, **no ticks**. Labels 水平 / 垂直 / 远近.
6. Presets: no 正面; keep 左前 右前 左侧 右侧 背面 俯视 仰视 特写 中等 广角.
7. Foot: 取消 / 生成. Title: 多角度.
8. Light 3D polish on existing main gizmos only (not redraw).

## Sheets
- `out/compare/compare_subject_zh_light.png` — 主体 zh-light (primary)
- `out/compare/compare_camera_zh_light.png` — 摄像头 zh-light (primary)
- `out/compare/compare_*_zh_dark.png` — dark placeholders (Lovart dark N/A)
- `out/compare/compare_all.png` — overview
- `out/right_*.png` — our panel alone
- `panel.html` — mock source

## Author
高审美设计师 <design-bot@users.noreply.github.com>
