# #623 Batch A-video STATUS — new6 skill hover mp4s

**Date:** 2026-11-02 Asia/Shanghai (CST, UTC+8)  
**Issue:** ganjmeng/ComfyArt#623 (soft FU from #575 `SKILL_VIDEO_PENDING_NEW6`)  
**Pin branch:** `assets/623-new6-hover-v1`  
**Eye:** soft PASS 6/6 (mid-frame eye + ffprobe; no Lovart glyphs)

## Recipe
- **Model:** WaveSpeed `bytedance/seedance-v1-pro-fast/image-to-video`
- **Params:** duration=3, resolution=480p, aspect_ratio=4:3, camera_fixed=false
- **Inputs:** `#594` PASS covers `/workspace/594w/review-assets/494/covers-v4/{id}.png` (COVER_V4 / WASH_594 `cc76d743…`)
- **Upload:** local binary → WaveSpeed `/api/v3/media/upload/binary`
- **Match:** #532 skill-list cover videos / `494/wash/videos` manifest kind

## Spend
| | |
|---|---|
| balance_before | $5.234044 |
| balance_after | $5.018044 |
| **spend_actual** | **$0.216** |
| unit_quote | $0.036 × 6 |
| n_ok / n_fail | 6 / 0 |

See `seedance-fast-ledger.json` + `ledger.jsonl`.

## Deliverables
| skill | mp4 bytes | ~dur | eye |
|---|---:|---|---|
| multi-angle | 166741 | 3.04s | soft PASS — 2×2 dripper grid intact; subtle light drift |
| logo-material | 393868 | 3.04s | soft PASS — 4 material tiles locked; specular shimmer |
| meta-ads | 451660 | 3.04s | soft PASS — Meta Ads board + 3 ad cards readable |
| mobile-ui | 251837 | 3.04s | soft PASS — Lumen Habit phones/UI chrome crisp |
| web-product | 227666 | 3.04s | soft PASS — Northboard windows + type readable |
| marketing-campaign | 895943 | 3.04s | soft PASS — YORI board identity kept; props drift OK |

All clips: H.264 640×480 @24fps, **no audio track**, muted-loop friendly.

## Paths (pin)
- Archive: `623/wash/videos/{id}.mp4` + `manifest.json`
- Wire (fullstack tip path): `594/wash/videos/{id}.mp4` (same bytes)
- Prep: `623/prep/STATUS.md`, `seedance-fast-ledger.json`, `ledger.jsonl`, `frames/*-mid.jpg`

## Soft PASS criteria check
- [x] 6/6 playable ~3s
- [x] No Lovart glyphs/watermarks
- [x] Motion subtle; not empty freeze; not wild morph
- [x] Contain-fit grids (multi-angle, logo-material) subjects readable mid-motion
- [x] Mid frames extracted via ffmpeg and reviewed

## Next
Fullstack may tip #623 wiring `Skill.video` → `594/wash/videos/<id>.mp4` @ pin SHA when ready.
