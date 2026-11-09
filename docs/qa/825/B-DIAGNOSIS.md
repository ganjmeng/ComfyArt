# Group B diagnosis (no paid calls) — #825 / #869

**Date:** 2026-11-10 Asia/Shanghai · tip under diagnosis: `9da7d2f5` artifacts

## Symptom
- **B2** (`openai/gpt-image-2.6-sunburst/edit`, pred `625389052fad43ceacebf0fb48ce56ee`): solid **black band** over the top ~421/1184 rows (= masked sky band).
- **B1** (`openai/gpt-image-2.5-sunburst/edit`): sky-only crop input (script path), full-peach sky result — **not** apples-to-apples with B2.

## Raw vs composite
- Raw provider file: `docs/qa/825/out/B2.png` (downloaded straight from WaveSpeed `outputs[0]`; **no** local pasteback).
- Top 421 rows: near-black frac **1.000** (mean ≈ 0.1). Bottom rows are warm building tones — black is **in the provider output**, not introduced by our collage.

## (1) Mask polarity / format in our script
| Piece | Detail |
|---|---|
| ComfyArt mask input | `inputs/mask-sky-top.png` RGBA: **α=0 = target (sky)**, α=255 = keep. Matches app convention (`tests/test_region_pasteback.py` `comfy_mask`, `api/wavespeed.py` `mask_array` L1850–1856). |
| Script conversion | Same as app `mask_to_white` (`api/wavespeed.py` **L750–759**): invert alpha → **grayscale L, white=edit, black=keep**. |
| Uploaded to WaveSpeed | `mask_image` = that grayscale PNG (top all-255, bottom all-0). |

**Conclusion:** polarity/format matched the **app’s WaveSpeed upload helper**. Black band is **not** explained by forgetting `mask_to_white` or sending raw alpha. It *is* explained by using a **non-production** API shape (full canvas + `mask_image`) that region-edit never uses.

## (2) App real masked-edit path (2.6 vs 2.5)
Production region / brush inpaint (`src/actions.ts` `editRegion` / `regionGraph` ~L175–192; `api/wavespeed.py`):

1. `submit` sees `paste` → `_submit_paste` (**L1728–1729**, **L1985–2003**).
2. Crops the selection (`crop_around`, pad 25%, min 384, ×8) from the base.
3. **`region_inputs` strips `mask`** (**L1964–1977**): “only the crop, at crop size, **mask not sent**.”
4. Cloud payload: `images=[crop]` only — test asserts **`"mask_image" not in payload`** (`tests/test_region_pasteback.py` **L84–95**).
5. On complete: `paste_result` (**L2027–2031**) composites model output back through the **local** mask so pixels outside stay byte-identical.

`build_payload` only adds `mask_image` when `inputs.mask` is present **and** the model schema has `mask_image` (**L1001–1005**). Region pasteback never reaches that with a mask.

| Model | Schema `mask_image`? | How app does masked edit |
|---|---|---|
| `openai/gpt-image-2.5-sunburst/edit` | **No** | Same crop-only + local pasteback (mask never sent). |
| `openai/gpt-image-2.6-sunburst/edit` | **Yes** (unused by region path) | Same crop-only + local pasteback. |

`masked_edit_model()` (**L1815–1823**) only picks the Auto table row (`api/auto_models.json` `image_edit.masked` → 2.6 Sunburst after #869); it does not change the crop/pasteback protocol.

**Would the app produce this black band?** **No** — for region edits it never ships `mask_image` / full-frame mask. Even a bad crop result is pasted only inside the mask; outside must match original pixel-for-pixel (acceptance already in `test_region_edit_sends_only_the_crop_to_sunburst_and_keeps_outside_pixels`).

## (3) Product-bug verdict (blocks Auto masked → 2.6 Sunburst?)
**No — not from this B2 artifact.** Black band is a **compare-script methodology miss** (full image + `mask_image` for 2.6; crop-only for 2.5), not evidence that production pasteback paints black. Auto row change remains the same pasteback path tests already cover for 2.6 Sunburst.

*If* a future pasteback rerun shows black **inside** the mask after local composite, that would be a real bug → then open the drafted issue. Condition for `/workspace/issues/825-mask-blackband.md` is **not** met by current evidence (see stub there).

## Script vs production (what we did wrong)
| | B1 (script) | B2 (script) | Production region edit |
|---|---|---|---|
| Image sent | sky-band **crop only** | **full** base 768×1024 | **crop** via `crop_around` |
| Mask to provider | none | `mask_image` (mask_to_white) | **none** |
| Pasteback | none | none | local `paste_result` |

For this base, production crop would be `{x:0,y:0,w:768,h:632}` around sky `{0,0,768,421}`.

## Known deviations (B pasteback rerun — Design PASS, no re-run)

1. **Hard-coded `aspect_ratio=3:4`** on a **768×632** crop. Production `build_payload` (`api/wavespeed.py` ~L1010–1012) would set `aspect_ratio` via `_nearest` from crop `width/height` → **`5:4`** for 768/632≈1.215. Provider returned **880×1184** (3:4-ish); pasteback bicubic-scaled that into the 768×632 box, so the sky was mildly **squashed**. Fair 2.5 vs 2.6 comparison (identical inputs/params); **gradient sky hides** the squash. Scripts now use `nearest_aspect(crop_w, crop_h)` (mirror of `_nearest`); **do not re-run** for this docs fix.

2. **Test mask one extra row:** sky α=0 included **row 420**, which is wall color on the base (wall starts at y=420). Correct seam is rows **0..419**. Mask asset regenerated to end at 419 (file-only; no API). Prior pasteback still Design PASS — 1px sky line only.

3. **Synthetic flat/gradient base:** B proves pasteback placement, clean seam, and that 2.6 color is more natural on this fixture. It does **not** prove which model is better on complex real-photo scenes; feathered real-photo seam → later real-device/E2E acceptance (技术经理).
