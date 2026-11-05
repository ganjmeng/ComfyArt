#760 / #761 r7 — Master Packaging single 3:4 (tip ComfyArt `2cab3c6c`)

## Design HOLD (review 5781075686) — only blocker
Zoom / tile on **主包装设计** still showed **2 rotated under-layers / paper edges**. Lovart is single 3:4 vertical centered, nothing behind. Prior tip claimed `nLayers:0` but wash bitmap lied.

## Root cause
- CSS stack: **already correct** (`media.length===1` → no `.ca-skillrun__stack`; DOM `nLayers:0`).
- **`packaging__eco.webp` wash itself** drew a fanned paper stack (2 rotated under-sheets + shadow) inside the bitmap.
- Not duplicate img / `::before` / box-shadow fake (selection `::after` is ring only).

## Fix (tip `2cab3c6c`)
- Swap Master (eco) cover → `/comfyart/skills/packaging/master.webp` = packaging raw media **270×360** single frame (LUMIÈRE / 主款).
- Portrait single frame: `object-fit: contain` (exact 3:4 → identical to cover inside 181.5×242).
- DOM well: **exactly 1** `<img>`; zoom: **1** img; `stackMounted: false`.

## DOM proof @1280 (`metrics-master.json`)
| field | value |
|-------|-------|
| stackMounted | false |
| nLayers | 0 |
| directImgCount / allImgCountInWell | **1** / **1** |
| natural | **270×360** (ratio 0.75) |
| box | **181.48×242** portrait contain centered |
| src | `/comfyart/skills/packaging/master.webp` |
| zoom imgCount | **1** |

## SBS (sign-off)
- **`sbs-master-raw-1to1.png`** — LEFT Lovart packaging media 270×360 \| RIGHT ours `master.webp` (1:1 same bytes content)
- **`sbs-master-card.png`** — LEFT design Master media \| RIGHT ours Master well (DOM imgs=1)
- Also: `ours-master-well.png`, `ours-master-zoom-board.png` (zoom board crop, no under-layers)

Non-blocking: sbs-01/02 same-card-index pick deferred.
