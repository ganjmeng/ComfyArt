# v3d — main 3D/preview/names restored; 3D recolor only

From v3c. Reverts 3D stage, preview control (相机/对象/预览), and slider/param names to current ComfyArt main (`AnglePreview` + `ModePanel`). Only recolors cube faces/edges and camera gizmo accents.

## Restored names (main / full-stack)
- View chips: 相机 / 对象 / 预览 (inset)
- Sliders: **水平** 0–360 · **倾斜** −30–60 · **远近** 0–10
- Face labels: 右侧 / 左侧 / 顶面 / 底面 / 背面
- Prompt: `anglePrompt` English line under stage

## Kept from v3c
- Header 重置 (预览 stays in angle bar, not header)
- 2×5 preset grid, no 正面
- No-tick thin sliders
- 「一次生成 4 个角度」 separate bottom button

## 3D color map (main → v3d)
| Role | Main | v3d |
|------|------|-----|
| Yaw ring/handle | `#00D4FF` | `#5B8FB8` |
| Pitch arc/handle | `#FF66FF` | `#B87A9E` |
| Dist line / camera marker | `#FFCC00` | `#C4A35A` |
| Face bg / grid / text | `#2A2D36` / `#3D4150` / `#AEB4C2` | `#2F333C` / `#454B58` / `#C5CAD6` |
| Front fill | `#D8DBE2` | `#E2E5EA` |
| Cube edges | `#1A1A1A` | `#22262E` |
| Wire sphere / inset border | `#8A93A6` | `#8E96A6` |
| Inset bg | `#282828` | `#2A2A2A` |

Geometry/positions identical to `src/ui/AnglePreview.tsx` on main (for grayscale QA).
