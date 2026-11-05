# Lovart motion-rec measurements (2026-11-05)

Source captures: `/workspace/lovart-inputs/motion-rec/` (`stack-expand.mp4`, `hover.mp4`, `modal-open-close.mp4`, `pill-select.mp4`, stills).  
Capture: 30 fps. 1920×1200 screen (chrome top 88px → content viewport 1920×1072).  
All published images/video have Lovart account name / avatar / authors / usage & bookmark counts solid-masked.

## Measured transition durations

Method: frame-to-frame mean abs diff in a ROI; start = first frame above threshold after quiet; end = last frame above quiet threshold within a short window. Card-hover chrome below also uses alpha blend vs hidden/shown references in a corner ROI.

| Interaction | Duration | Notes |
|---|---|---|
| Stack expand (card hover-on) | **~400 ms** (~12 frames) | Packaging Visual Direction card ROI in `stack-expand.mp4`; starts frame 49 / 191 |
| Stack collapse (hover-off) | **~367–400 ms** (~11–12 frames) | Starts frame 115 / 273 |
| Modal open | **~200 ms** (~6 frames) | `modal-open-close.mp4` open clusters |
| Modal close | **~167–200 ms** (~5–6 frames) | close clusters |
| Skills-wall card hover chrome | **~0–33 ms** (1 frame) | Try-this-skill chrome appears in one frame; weak residual diffs ~10 frames later (~video fade), **not** a stack expand |
| Template / card select state | **~0–33 ms** | single-frame grid spikes (instant outline / selected check) |

Timed modal crops published at **0 / 33 / 67 / 100 / 133 / 200 / 267 / 333 / 400 / 500 ms** after expand-on (frame 49) and expand-off (frame 115).

### Skills page category chip (NOT the card Select pill)

Source: `pill-select.mp4` (Skills Explore filter row: For you / E-commerce / Branding / …).

| Interaction | Duration | Notes |
|---|---|---|
| Skills page category chip change | **~167–200 ms** | pill-bar clusters (frames ~20–25, ~289–293) |

This is the top-of-Skills-page category chip animation. It is **not** the template-card hover 「选择」/Select control.

### Card hover Select pill / View Full Size icon

Source: `stack-expand.mp4` @ 30 fps, 1920×1200 (viewport y0 = screen y88). Card: Packaging Visual Direction at viewport **(788, 334)** size **388×321**. Measured separately from the stack expand/collapse (stack ~400 ms).

Method: corner ROIs on the thumb — View Full Size top-left ~(12,12) 28×28; Select/check top-right. For View Full Size, estimate opacity as linear blend between a fully-hidden rest frame and a fully-shown hover frame; transition = first non-zero alpha → alpha≈1 (appear) or reverse (disappear).

| Interaction | Duration | Notes |
|---|---|---|
| View Full Size icon appear (hover-on) | **~100–133 ms** (3–4 frames) | Cycles: frames 49→52 (~100 ms), 192→196 (~133 ms). Starts with stack expand but finishes much sooner. |
| View Full Size icon disappear (hover-off) | **~133 ms** (4 frames) | Cycles: frames 116→120, 273→277. Parallel to stack collapse start; icon is gone while stack is still collapsing. |
| Select pill / selected check appear & disappear | **not measurable as a hover fade in this clip** | Card is **already selected** for the whole `stack-expand.mp4`: top-right control is a **checkmark** present in **every** frame (including rest / hover-off), TR ROI mean and dark-blob size unchanged (0 frame-to-frame diff). Unselected 「Select」 text pill never appears here. |

**30 fps coarseness:** frame step = 33.3 ms. A ~100–133 ms fade spans only 3–4 samples, so the value is quantized to ±33 ms and cannot resolve e.g. 80 vs 100 vs 120. Still enough to show the icon chrome is **~100 ms-class**, not the stack’s ~400 ms and not the category chip’s ~167–200 ms. A higher-fps capture would be needed to pin an exact CSS duration. For the unselected Select text pill, need a clip that hovers an **unselected** template card (1280 hover still shows Select on Packaging when unselected; this motion clip does not).

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
