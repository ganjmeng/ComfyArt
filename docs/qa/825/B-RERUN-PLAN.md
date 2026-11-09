# Group B corrected rerun plan (await 技术经理 GO) — #825

**Status:** **DO NOT RUN** until 技术经理 approves. Cap **$0.12**. No other paid work concurrent.

## Goal
Apples-to-apples Flare-path fairness: **both** B1 (2.5 Sunburst edit) and B2 (2.6 Sunburst edit) through the **real production masked-edit path** (region pasteback). 2.5 input must match production exactly (crop only; no `mask_image`).

## Protocol (mirror `api/wavespeed.py` `_submit_paste` + `paste_result`)
Inputs (unchanged files):
- Base: `docs/qa/825/inputs/base-window-sky.png` (768×1024)
- Mask: `docs/qa/825/inputs/mask-sky-top.png` (ComfyArt: α=0 sky)
- Prompt (exact): `Replace only the sky in the selection with a soft peach sunset, keep the building and window frames unchanged`

Per model (serial):
1. Compute `crop_around` on sky bbox → expected `{x:0,y:0,w:768,h:632}` on this asset.
2. Crop RGB base to that box; build crop-local ComfyArt mask (same as `_submit_paste`).
3. **POST** `images=[crop_url]` only — **do not** send `mask_image` — `resolution=1k`, medium unpinned, `aspect_ratio` nearest to crop (≈3:4 or omit and let schema default if that matches how estimate/submit builds from width/height — prefer passing `width`/`height` of crop like `region_inputs`).
4. Poll; download **raw crop result** to `docs/qa/825/out/B{n}-raw-crop.png`.
5. Local `paste_result(orig, mask, box, result)` → `docs/qa/825/out/B{n}-pasteback.png`.
6. Log prediction id at submit; balance before/after; latency; actual cost.
7. Acceptance (tester): **outside the mask, pasteback must match original pixel-for-pixel**; **no black band** in the sky selection (peach sunset). If black band appears **after** pasteback inside the mask, treat as product bug (see `/workspace/issues/825-mask-blackband.md` stub) and stop.

Models:
| # | Model | Catalog 1k (prior actual) |
|---|-------|---------------------------|
| B1 | `openai/gpt-image-2.5-sunburst/edit` | $0.039 (actual was $0.039) |
| B2 | `openai/gpt-image-2.6-sunburst/edit` | $0.065 (actual was $0.072) |

## Budget
- Catalog sum ≈ **$0.104**; prior actuals sum **$0.111**.
- **Hard cap $0.12** cumulative actual. Balance &lt; $20 → abort. Same image fails twice → abandon that image.
- WaveSpeed key: `/home/box/.secrets/comfyart-test.env` only; never print/commit keys.

## Deliverables after GO
- Raw crops + pastebacks + L|R collage of pastebacks labeled with model / size / cost / latency.
- Update `SPEND.md` / PR #869 B section; note prior B2 black band was non-production path.
