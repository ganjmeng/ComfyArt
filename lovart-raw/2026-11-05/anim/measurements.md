# Lovart motion-rec measurements (2026-11-05)

Source captures: `/workspace/lovart-inputs/motion-rec/` (`stack-expand.mp4`, `hover.mp4`, `modal-open-close.mp4`, `pill-select.mp4`, stills).  
Capture: 30 fps. 1920×1200 screen (chrome top 88px → content viewport 1920×1072).  
All published images/video have Lovart account name / avatar / authors / usage & bookmark counts solid-masked.

## Measured transition durations

Method: frame-to-frame mean abs diff in a ROI; start = first frame above threshold after quiet; end = last frame above quiet threshold within a short window.

| Interaction | Duration | Notes |
|---|---|---|
| Stack expand (card hover-on) | **~400 ms** (~12 frames) | Packaging Visual Direction card ROI in `stack-expand.mp4`; starts frame 49 / 191 |
| Stack collapse (hover-off) | **~367–400 ms** (~11–12 frames) | Starts frame 115 / 273 |
| Modal open | **~200 ms** (~6 frames) | `modal-open-close.mp4` open clusters |
| Modal close | **~167–200 ms** (~5–6 frames) | close clusters |
| Skills-wall card hover chrome | **~0–33 ms** (1 frame) | Try-this-skill chrome appears in one frame; weak residual diffs ~10 frames later (~video fade), **not** a stack expand |
| Category pill change | **~167–200 ms** | `pill-select.mp4` pill-bar clusters (frames ~20–25, ~289–293) |
| Template / card select state | **~0–33 ms** | single-frame grid spikes (instant outline / selected check) |

Timed modal crops published at **0 / 33 / 67 / 100 / 133 / 200 / 267 / 333 / 400 / 500 ms** after expand-on (frame 49) and expand-off (frame 115).

## 1920 viewport / modal geometry (from recordings)

- Content viewport: **1920×1072** (screen y = viewport y + 88)
- Modal (white detect): viewport **(360, 125)** size **1200×820** → screen crop used for frames
- Packaging Visual Direction card (viewport): **(788, 334)** size **388×321**

## 1280×1072 viewport (static + hover stills)

Measured / specified layout for the Brand Packaging Design System modal on the 1280-wide capture:

| Element | Value |
|---|---|
| Viewport | 1280×1072 |
| Modal | **1112×820** at ~(84, 126) |
| Left pane | **752** wide |
| Templates grid | **2 cols**, gap **16**, padding **24 / 24 / 2 / 24** (T/R/B/L) |
| Card | **344×288** |
| Thumb area | **344×258** (aspect 160/120), radius **12** |
| Stack inset | **8 px** → stack stage **328×242** |
| Static layers | size **328×184.04**, `translateY(28.98px)` `scale(0.757178)`, rotate **5° / −5° / 10°**, z **3 / 2 / 1** |
| Hover row | **3×** cells **105.33×242** at `translateX` **0 / 111.33 / 222.67**, no scale/rotate |
| Hover images | **105.33×59.1**, vertically centered in cell |
| Hover chrome | **Select** pill top-right; **View Full Size** icon top-left |

Published: `lovart-1280x1072-static.masked.png`, `lovart-1280x1072-hover.masked.png`.

## Published files (this folder)

- `frames/stack-on-XXXms.masked.png` / `stack-off-XXXms.masked.png` — modal crops at timed offsets
- `sheets/stack-*-contact.masked.png` — card-ROI contact sheets
- `sheets/stack-*-modal-contact.masked.png` — full-modal contact sheets (0/100/200/400)
- `stack-static.modal.masked.png` / `stack-expanded.modal.masked.png`
- `lovart-1280x1072-static.masked.png` / `lovart-1280x1072-hover.masked.png`
- `stack-expand-on.masked.mp4` / `.gif` — ~0.5 s expand clip (masked)
- `stack-expand-off.masked.mp4` — collapse clip (masked)
- `manifest.json` — frame indices + duration dump
