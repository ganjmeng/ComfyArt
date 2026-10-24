# #249 多角度面板 v1 — mock only ($0, no API calls)
Popover 260px, anchored to selected image top-right, non-modal. Tabs 主体/摄像头 share state; reset restores defaults (Rotate 45°, Tilt -30°, Zoom 中等).
## UI → edit-multiple-angles params
- Rotate slider -90..90, snaps -90/-45/0/45/90 → horizontal: -90→270, -45→315, 0→0, 45→45, 90→90 (i.e. (v+360)%360)
- Tilt slider snaps -30/0/30/60 → vertical: same value
- Zoom 特写/中等/广角 (Close-up/Medium/Wide) → distance 0/1/2
Price $0.03 is a mock value. Panel fits at 1280×800 (popover y 150–599).
