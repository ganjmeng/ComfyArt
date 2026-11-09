# #825 paid comparison plan (draft only — not run)

**Status:** pending approval. Do **not** run until prompts are posted on [#825](https://github.com/ganjmeng/ComfyArt/issues/825) and spend is approved.  
**Cap:** **$0.40** total · **7** images · **1K** · WaveSpeed schema default quality (**medium**, not pinned — #189).  
**Catalog prices** from `tests/fixtures/wavespeed_catalog_subset.json` `base_price` (real charge may differ slightly).

Per-task Auto routing in this PR is **our #133 table**, not Lovart parity. Lovart only verified that an ordinary coffee prompt went to Flare ([#133 EL comment](https://github.com/ganjmeng/ComfyArt/issues/133#issuecomment-6357414006)).

Person-row Auto changes are **out of scope** for the routing PR; the person trio below is evidence-only for product.

## Reference image (person row)

| Field | Value |
|---|---|
| Path | `643/wash/portrait-studio/examples/01.webp` |
| Why | Washed portrait-studio gold example already in-repo (non-celebrity, license-safe wash output). |

## Matrix (7 images)

### A. Poster / text (2) — t2i Flare vs Sunburst

Same prompt; only the model id changes.

| # | Model | Size | Params | Est. USD |
|---|---|---|---|---|
| A1 | `openai/gpt-image-2.6-flare/text-to-image` | 1K | medium (unpinned) | **$0.05** |
| A2 | `openai/gpt-image-2.6-sunburst/text-to-image` | 1K | medium (unpinned) | **$0.05** |

**Prompt (exact):**

```
Double-eleven furniture poster, bold Chinese headline 「焕新了！我的家」, subhead 「换个心情 / 过冬！」, white italic offer line 「先领3000元暖家补贴」 and 「11月1日0点 / 低至6折！」, light-blue velvet sofa hero, clean retail layout, readable typography
```

### B. Masked / region edit (2) — 2.5 Sunburst vs 2.6 Sunburst

**Pair choice:** `openai/gpt-image-2.5-sunburst/edit` (pre-PR table) vs `openai/gpt-image-2.6-sunburst/edit` (this PR).  
**Why not Flare vs Sunburst:** the masked row change is same-family precision (Sunburst) across 2.5→2.6; Flare would confound version with variant. Flare edit stays the unmatched-edit / GIF default and is not what this row moved.

Same base crop + mask + prompt for both.

| # | Model | Size | Params | Est. USD |
|---|---|---|---|---|
| B1 | `openai/gpt-image-2.5-sunburst/edit` | 1K | medium (unpinned), masked crop | **$0.039** |
| B2 | `openai/gpt-image-2.6-sunburst/edit` | 1K | medium (unpinned), masked crop | **$0.065** |

**Prompt (exact):**

```
Replace only the sky in the selection with a soft peach sunset, keep the building and window frames unchanged
```

**Inputs:** one base still + one selection/brush mask (to be attached when running; same bytes for B1 and B2). Prefer a simple indoor window crop from an in-repo still if available at run time.

### C. Photoreal person consistency (3) — evidence only (no Auto table change)

Same reference person + identical edit prompt on three edit models.

| # | Model | Size | Params | Est. USD |
|---|---|---|---|---|
| C1 | `google/nano-banana-2.1/edit` | 1K | medium (unpinned), 1 ref | **$0.04** |
| C2 | `openai/gpt-image-2.6-sunburst/edit` | 1K | medium (unpinned), 1 ref | **$0.065** |
| C3 | `bytedance/seedream-v5.0-pro/edit` | 1K | medium (unpinned), 1 ref | **$0.045** |

**Reference:** `643/wash/portrait-studio/examples/01.webp`  
**Prompt (exact):**

```
Keep the same person and face identity from the reference. Change only the background to a bright sunlit living room with a light-blue sofa; keep clothing, pose, and framing
```

## Budget

| Group | Images | Est. sum |
|---|---|---|
| A poster t2i | 2 | $0.10 |
| B masked edit | 2 | $0.104 |
| C person edit | 3 | $0.15 |
| **Total** | **7** | **≈ $0.354** (under **$0.40**) |

Record every WaveSpeed prediction id against #97 when run. Stop if spend would exceed $0.40.
