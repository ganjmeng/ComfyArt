# #249 多角度面板 v2 — mock only ($0, no API calls)
Popover 260px, anchored to the selected image's top-right, non-modal; fits at 1280×800 (y 150–655, Generate fully visible). Tabs 主体/摄像头 share state; reset restores defaults (Rotate 45°, Tilt -30°, Zoom 中等, preset none, count ×1).
## Controls → edit-multiple-angles params
- Rotate -90..90, snaps -90/-45/0/45/90 → horizontal (v+360)%360: -90→270, -45→315, 0→0, 45→45, 90→90
- Tilt snaps -30/0/30/60 → vertical (same value)
- Zoom 特写/中等/广角 (Close-up/Medium/Wide) → distance 0/1/2
- Presets 左侧/左前/右前/右侧 (Left/Front-left/Front-right/Right) set Rotate = -90/-45/45/90 (1 request)
- 四角度 / 4 angles: 4 requests, horizontal = 270, 315, 45, 90, same vertical/distance; Rotate slider shows 「4 个角度 / 4 angles」 disabled; count locked ×4; button 「生成 4 张 / Generate 4」
- Count ×N (1–4, footer: 取消 | ×N ▾ | 生成): N requests with identical params
- Price = $0.03 × images (mock value)
## Frames
a Subject default · b Camera tab · c snapped + hover Generate · d 四角度 selected · e count menu open (×2) — each in zh/en × light/dark; closeup2x (default) and closeup2x_four at 2x.
compare/: Lovart reference (scaled ×1.25 to match) vs ours (zh light) — internal review only.
