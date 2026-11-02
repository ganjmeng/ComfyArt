# #575 Motion rewash STATUS

**Date:** 2026-11-02 Asia/Shanghai  
**Issue:** ganjmeng/ComfyArt#575 (cost card) · P2 from #569  
**Balance start:** 3329.4 credits · **end:** 3067.0 · **spend:** 262.4  
**Design soft PASS** (2026-11-02 Asia/Shanghai). Pin branch `assets/575-motion-wash-v1`; deliverables under `575/wash/` (569 old kept).  
**Attempts:** 1/2 per slot (no second seedance gen)

## Goal
1. **motion-01** Poster Animation — left mini-poster STATIC (no wobble); right may animate; ~4:3 ~12s; LUMEN DRIFT / KOI-77 copy sharp.
2. **motion-02** First-to-Last — mid-transition text stays sharp (no ~0.5s blur); ~9:16 ~4s; cream magazine morph OK.

## Models
- Frames: reused #569 washed keyframes extracted from live mp4s (tempfile CDN expired). No still regen.
- Video 01: `bytedance/seedance-2-mini` ×2 (6s first=last) + ffmpeg 0.6s xfade + **per-clip left-panel still lock** (470px strip)
- Video 02: `bytedance/seedance-2` first+last 4s + **ffmpeg text chrome** (static top headline; bottom caption hard-cut first→last @2.10s)

## Ledger
| ts (UTC+8) | slot | event | taskId | credits | note |
|---|---|---|---|---|---|
| 14:55:47–51 | — | upload keys | — | — | m0-first/last, m1-first/last → tempfile …/575-wash/motion/ |
| 14:55:59 | m0a | submit | `ad1700623ef8bf61b513f2dab7c729aa` | — | seedance-2-mini 6s LUMEN |
| 14:55:59 | m0b | submit | `6bf3f1e1e53ed0c805971f6d5b4444c1` | — | seedance-2-mini 6s KOI-77 |
| 14:55:59 | m1 | submit | `b3a0ab88132e644689de98cad2af58dd` | — | seedance-2 4s cream morph |
| 14:58:05 | m0a | complete | `ad170062…` | **49.2** | raw/m0a.mp4 |
| 14:58:06 | m0b | complete | `6bf3f1e1…` | **49.2** | raw/m0b.mp4 |
| 15:01:10 | m1 | complete | `b3a0ab88…` | **164.0** | raw/m1.mp4 |
| 15:01+ | post | ffmpeg | — | 0 | 01 left lock + xfade; 02 text chrome; posters/thumbs/SBS |

**Total spend:** 49.2 + 49.2 + 164.0 = **262.4** · bal 3329.4 → **3067.0**

## Rejects
_(none — all 3 seedance tasks success on attempt 1)_

## P2 verdict (executor eye — needs design PASS)

### motion-01 — **LIKELY FIXED** (wobble)
- Output: `1112×834` · `11.5s` · 276f · 24fps
- Left strip MAD within H1 (LUMEN): **~0.01**; within H2 (KOI): **~0.05–0.61** (locked). Right MAD animates as intended.
- Crossfade ~5.4–6.0s intentionally morphs left LUMEN→KOI (template narrative); not wobble.
- Copy sharp: LUMEN DRIFT / AYA NOVAK / STREAMING MARCH 14 → KOI-77 / HARBOR LIGHTS LIVE / PIER 9 LISBON / OCT 03 2027. No Lovart glyphs/watermarks.

### motion-02 — **LIKELY FIXED** (mid-text blur)
- Output: `720×1280` · `4.00s` · 96f · 24fps
- Native seedance mid-morph still softens embedded type; mitigated by overlay:
  - Top `"WHAT SHAPES YOUR LOOK?"` static chrome entire duration (edge≈10, stable).
  - Bottom caption hard-cut first→last @2.10s (no ghost xfade); mid bot edge≈15–18, legible **"Night Circuit"** etc.
- Cream magazine morph of figure OK. Design should confirm mid look vs Lovart reference.

## Deliverables (pinned under `575/wash/`)
```
575/wash/templates/
  01-poster-animation.mp4
  01-poster-animation.webp
  01-poster-animation@poster.webp
  01-poster-animation@thumb.webp
  02-first-to-last-frame-animation.mp4
  02-first-to-last-frame-animation.webp
  02-first-to-last-frame-animation@poster.webp
  02-first-to-last-frame-animation@thumb.webp

575/wash/sbs/
  sbs-motion-01.webp   # left=#569 old · right=#575 new @2.5s
  sbs-motion-02.webp
  sbs-motion.webp      # stacked

/workspace/ComfyArt-review-assets/575/prep/
  STATUS.md  INVENTORY.md  wash_motion_575.py
  submitted.json  results.json  ledger.jsonl  key_urls.json
```

## Design soft PASS (pinned)
- motion-01: left strip MAD≈0 at t1–t2.5 (static); intentional LUMEN→KOI change at xfade/t9 OK
- motion-02: mid text sharp (Ivory Bloom / Night Circuit / WHAT SHAPES YOUR LOOK?); mild figure haze mid-morph acceptable; **P2 text-blur FIXED**
- Pin path: `575/wash/templates/` (+ `575/wash/sbs/`); keep `569/wash/motion/templates/` old
- Fullstack: wire `preset.video` to `575/wash/templates/01-poster-animation.mp4` and `…/02-first-to-last-frame-animation.mp4` on this pin SHA

## Next
1. ~~Eye PASS / FAIL~~ → soft PASS
2. Pin + raw URL verify (this commit)
3. Fullstack wires `preset.video` (no design COMMENT on #621)
