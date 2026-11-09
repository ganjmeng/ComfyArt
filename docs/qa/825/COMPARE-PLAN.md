# #825 paid comparison plan (draft only — not run)

**Status:** pending approval. Do **not** run until prompts are posted on [#825](https://github.com/ganjmeng/ComfyArt/issues/825) and spend is approved.  
**Cap:** **$0.55** total · **10** images · **1K** · WaveSpeed schema default quality (**medium**, not pinned — #189).  
**Catalog prices** from `tests/fixtures/wavespeed_catalog_subset.json` `base_price` (real charge may differ slightly; use balance delta as truth).

Per-task Auto routing in PR #869 is **our #133 table**, not Lovart parity. Lovart only verified that an ordinary coffee prompt went to Flare ([#133 EL comment](https://github.com/ganjmeng/ComfyArt/issues/133#issuecomment-6357414006)).

**Product note:** anime / illustration / cartoon characters stay on nano-banana. Only **photoreal real people** are candidates for a later Auto change. **Person-row Auto change is a separate PR** — groups C/D are evidence only.

## Stop rules (mandatory)

1. **Serial only** — never overlap WaveSpeed calls.
2. Before each call: log **balance**. After each call: log **prediction id**, **balance**, and **delta**.
3. Stop a group after **2 failures** in that group; do not start the next image in the group.
4. Abort the whole run if **WaveSpeed balance < $20** before a call.
5. Abort if **cumulative spend would exceed $0.55** (or already has).
6. Record every prediction id against [#97](https://github.com/ganjmeng/ComfyArt/issues/97).

## Reference image (group D only)

| Field | Value |
|---|---|
| Path | `643/wash/portrait-studio/examples/01.webp` |
| Why | Washed portrait-studio gold example already in-repo (non-celebrity, license-safe wash output). |

## Matrix (10 images)

### A. Poster / text t2i (2) — Flare vs Sunburst

Same prompt; only the model id changes.

| # | Model | Size | Params | Est. USD |
|---|---|---|---|---|
| A1 | `openai/gpt-image-2.6-flare/text-to-image` | 1K | medium (unpinned) | **$0.05** |
| A2 | `openai/gpt-image-2.6-sunburst/text-to-image` | 1K | medium (unpinned) | **$0.05** |

**Prompt (exact):**

```
Double-eleven furniture poster, bold Chinese headline 「焕新了！我的家」, subhead 「换个心情 / 过冬！」, white italic offer line 「先领3000元暖家补贴」 and 「11月1日0点 / 低至6折！」, light-blue velvet sofa hero, clean retail layout, readable typography
```

### B. Masked / region edit (2) — 2.6 Flare edit vs 2.6 Sunburst edit

**Pair choice:** `openai/gpt-image-2.6-flare/edit` vs `openai/gpt-image-2.6-sunburst/edit` (same generation, Flare vs Sunburst).  
Replaces the earlier 2.5-vs-2.6 Sunburst pairing so the A/B contrast is **variant** (speed/draft vs precision), matching #825 product wording.

Same base crop + mask + prompt for both.

| # | Model | Size | Params | Est. USD |
|---|---|---|---|---|
| B1 | `openai/gpt-image-2.6-flare/edit` | 1K | medium (unpinned), masked crop | **$0.065** |
| B2 | `openai/gpt-image-2.6-sunburst/edit` | 1K | medium (unpinned), masked crop | **$0.065** |

**Prompt (exact):**

```
Replace only the sky in the selection with a soft peach sunset, keep the building and window frames unchanged
```

**Inputs:** one base still + one selection/brush mask (attached at run time; same bytes for B1 and B2).

### C. Photoreal person t2i (3) — evidence only (no Auto table change)

Same prompt on three text-to-image models. Beauty-campaign grade, real skin texture, non-celebrity.

| # | Model | Size | Params | Est. USD |
|---|---|---|---|---|
| C1 | `google/nano-banana-2.1/text-to-image` | 1K | medium (unpinned) | **$0.04** |
| C2 | `bytedance/seedream-v5.0-pro` | 1K | medium (unpinned) | **$0.045** |
| C3 | `openai/gpt-image-2.6-sunburst/text-to-image` | 1K | medium (unpinned) | **$0.05** |

**Prompt (exact):**

```
Photoreal portrait of an attractive young East Asian woman, beauty-campaign grade, natural makeup, real skin texture with fine pores, soft daylight from a window, shallow depth of field, 85mm look, non-celebrity, no logo, no watermark
```

### D. Photoreal person edit — identity keep (3) — evidence only (no Auto table change)

Same reference + identical edit prompt on three edit models.

| # | Model | Size | Params | Est. USD |
|---|---|---|---|---|
| D1 | `google/nano-banana-2.1/edit` | 1K | medium (unpinned), 1 ref | **$0.04** |
| D2 | `bytedance/seedream-v5.0-pro/edit` | 1K | medium (unpinned), 1 ref | **$0.045** |
| D3 | `openai/gpt-image-2.6-sunburst/edit` | 1K | medium (unpinned), 1 ref | **$0.065** |

**Reference:** `643/wash/portrait-studio/examples/01.webp`  
**Prompt (exact):**

```
Keep the same person and face identity from the reference. Change only the background to a bright sunlit living room with a light-blue sofa; keep clothing, pose, and framing; photoreal, real skin texture
```

## Budget

| Group | Images | Est. sum |
|---|---|---|
| A poster t2i | 2 | $0.10 |
| B masked edit (2.6 flare vs sunburst) | 2 | $0.13 |
| C person t2i | 3 | $0.135 |
| D person edit | 3 | $0.15 |
| **Total** | **10** | **≈ $0.515** (under **$0.55**) |

## Out of scope
- Running any paid call from this plan without #825 approval
- Changing Auto rows for photoreal / consistency / person (separate PR)
- Anime / illustration / cartoon Auto (stays nano-banana)
