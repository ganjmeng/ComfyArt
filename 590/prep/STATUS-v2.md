# #590 wash-v2 STATUS — subtle copyright-dodge rewash (WaveSpeed GPT Image 2.5 Sunburst EDIT)

**When:** 2026-11-02 ~12:54–12:59 Asia/Shanghai (CST, UTC+8)  
**Issue:** #590  
**Ashley lock (t295u):** wash = subtle name/motif dodge ONLY — keep old featured-v1 composition / color / layout / density / lighting almost 1:1  
**Model:** `openai/gpt-image-2.5-sunburst/edit` (i2i / edit — NOT text-to-image, NOT flare, NOT banana)  
**Source inputs:** `/workspace/594w/review-assets/580/featured-v1/{slot}/NN.webp`  
**Out:** `/workspace/ComfyArt-review-assets/590/wash-v2/`  
**Helper:** `590/prep/wash_ws_590_v2.py` · ledger `590/prep/ledger-v2.jsonl` (no secrets)  
**GitHub/room/commit/push:** pinned (see Pin section below)  
**Pin `b85f38cd`:** SUPERSEDED by wash-v2 pin on `assets/590-featured-wash-v2`

## Credits / spend

| | value |
|---|---|
| WaveSpeed balance before subtle batch | **5.585044** |
| WaveSpeed balance after | **5.273044** |
| Subtle 8-slot spend | **$0.312** (~$0.039 × 8) |
| Aborted dense-pass brand/01 (pre-t295u, discarded) | ~**$0.039** (balance 5.624044 → 5.585044) |
| Session WS total (incl. abort) | ~**$0.351** |
| Kie / nano-banana | **stopped** — credits unchanged at **3329.4** (no further banana spend) |

## Retry — interior/02 only (Ashley t296u / pt296u)

**When:** 2026-11-02 ~13:27 Asia/Shanghai (CST, UTC+8)  
**Reject:** proportion wrong — wash looked scaled down / letterboxed vs old 900×1200 portrait crop.  
**Root cause:** SBS pad compared unequal thumbs (featured-v1 `02@thumb` **600×800** vs wash-v2 **450×600**) → dark bars made R look shrink-to-fit. Full `02.webp` was already 900×1200 but framing lock reinforced on re-edit.  
**Action:** re-run ONLY `interior/02` via `openai/gpt-image-2.5-sunburst/edit` i2i; stronger fill-frame / EXACT crop prompt; strip letterbox in `save_webp_pair`; `make_sbs` now resizes to common height (no pad).  
**taskId:** `7a42785e61a241f3a149780209497816`  
**Out overwrite:** `wash-v2/interior/02.webp` (116906 B) + `02@thumb.webp` (26548 B); `prep/sbs-v2/interior_02_sbs.webp` rebuilt (1208×800).  
**Dims:** ffprobe/PIL **900×1200** (identify unavailable — no ImageMagick on box).  
**Spend:** balance 5.273044 → **5.234044** (−$0.039).  
**GitHub / push / room:** pinned with wash-v2 (interior/02 retry included).

## Must slots — result

| # | slot | brand | taskId | state | w×h | full bytes | thumb bytes |
|---|---|---|---|---|---|---|---|
| 1 | brand/01 | ARC RIDE | `8343d0afb2fd40d8913bea3bca333e0f` | OK | 1200×900 | 133054 | 41982 |
| 2 | poster/01 | HALCYON | `965b85e70e674e208fd5e507a6f4f883` | OK | 1200×900 | 126054 | 30578 |
| 3 | poster/03 | Daylight Notes | `5b9aa136cd9d48feb19f1375b9710dd6` | OK | 1200×900 | 91306 | 26414 |
| 4 | product/01 | NODAL | `993aea97ca85465d9a7b79079ae18be2` | OK | 1200×900 | 83446 | 27578 |
| 5 | banner/02 | HELIO | `d44a27b8c0cb47bb8209d8353528ab00` | OK | 1200×900 | 123368 | 42120 |
| 6 | interior/02 | HALCYON | `7a42785e61a241f3a149780209497816` | OK (retry) | 900×1200 | 116906 | 26548 |
| 7 | social/02 | Tide Ledger | `f6cac776de124e4fa178f42fe708899b` | OK | 1200×900 | 164964 | 30594 |
| 8 | packaging/01 | HELIO | `7aa7f818366d484eac184237b6225b28` | OK | 1200×900 | 144864 | 46290 |

**Score: 8/8 wash-v2 fulls + thumbs saved. Failures: none. Retries: interior/02 once (t296u proportion).**

## Deliverables

- Fulls + thumbs: `wash-v2/{brand,poster,product,banner,interior,social,packaging}/NN.webp` + `@thumb.webp`
- Slice manifest: `wash-v2/manifest-slice.json` (paths, brands, taskIds, w×h, model)
- SBS-v2 (L=old featured-v1 thumb · R=new wash-v2 thumb): `prep/sbs-v2/*_sbs.webp` (8 pairs)
- Raw PNG downloads: `prep/raw-v2/` (scratch)
- Helper: `prep/wash_ws_590_v2.py` · log: `prep/wash_v2_sunburst.log`
- `prep/wash_kie_590_v2.py` is a hard redirect stub (banana disabled)

## L/R design notes (executor eye — subtle dodge)

SBS pairs: left = `580/featured-v1` old · right = `590/wash-v2` new.

| slot | L (old) | R (new) | note |
|---|---|---|---|
| brand/01 | VOLTA dense board + billboard + specs | ARC RIDE same dense board; specs→icon chips; VOID ROOM cleared; tagline RIDE THE ARC | Composition/density kept. Soft: highway billboard retained (1:1 lock). **PASS lean** |
| poster/01 | equinox + cairn | HALCYON + fern/seed-pod botanical; room 1:1 | Cairn/name hit cleared without emptying poster. **PASS** |
| poster/03 | Golden Hours triptych density | Daylight Notes; photo density kept; microcopy cleaned | Still triptych (1:1 lock) — name dodge OK. Soft: still multi-poster vs earlier “one poster” wish; superseded by t295u. **PASS lean** |
| product/01 | 5-up headphone masonry | NODAL mark + emboss; masonry density largely kept | Soft: still Lovart-adjacent 5-up (allowed under subtle lock). **PASS lean** |
| banner/02 | SOLARIS aerosol · SUMMER 50% OFF | HELIO tube+stick; promo punch + layout 1:1 | Strong name+form dodge. **PASS** |
| interior/02 | SOLSTICE + cairn · deep green drama | HALCYON book; ceramic/branch on plinth; drama kept | **RETRY 13:27 CST (t296u):** Ashley rejected prior wash as scaled-down/letterboxed vs 900×1200. Cause: SBS used featured-v1 thumb 600×800 vs wash thumb 450×600 with pad→fake letterbox. Regenerated i2i taskId `7a42785e61a241f3a149780209497816`; prompt locked EXACT framing / fill-frame / no bars; SBS now scale-to-height (no pad). ffprobe/PIL **900×1200**. **PASS lean — await Ashley** |
| social/02 | Golden Hours / Summer Notes dense scrapbook | Tide Ledger; both sides content-rich; garbled body→short hierarchy | Density kept. **PASS** |
| packaging/01 | SOLA spray+tube beach | HELIO; scene 1:1 | Soft: spray form still present (1:1 kept twin silhouette). **PASS lean** |

**Executor recommendation:** Ashley OK'd pin. wash-v2 soft PASS → product then fullstack FEED_V1.

## Hygiene

- No API keys in ledger/STATUS/manifest/log
- Pinned to review-assets branch; issue COMMENT calls product
- Banana path not used for wash-v2 deliverables

## Pin (Ashley OK — 2026-11-02 ~13:40 Asia/Shanghai CST)

- Branch: `assets/590-featured-wash-v2`
- Parent: `b85f38cdd52006715114f70e68f1b35fc4f52c32` (wash-v1 / prior FEED pin)
- Overwrote `580/featured-v1/` 8 slots from `590/wash-v2/` (incl. fixed interior/02)
- Supersedes wash-v1 pin `b85f38cd` / COMMENT `6568407413`
- No app tip merge; wait product PASS then fullstack FEED_V1 wire
