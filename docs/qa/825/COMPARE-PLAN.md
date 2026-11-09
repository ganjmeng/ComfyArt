# #825 paid comparison plan (draft only — not run)

**Status:** **RAN** 2026-11-10 Asia/Shanghai. See `SPEND.md`, `OCR-A-REPORT.md`, `lr/` collages, `out/`. Total actual spend **$0.5493** (cap $0.65).  
**Cap:** **$0.65** total · **10** images.  
**Quality:** WaveSpeed schema default (**medium**), not pinned (#189).  
**Prices:** cited from repo sources below (not hand-waved estimates). Real charge = balance delta; abort if cumulative would exceed **$0.65**.

Per-task Auto routing in PR #869 is **our #133 table**, not Lovart parity. Lovart only verified that an ordinary coffee prompt went to Flare ([#133 EL comment](https://github.com/ganjmeng/ComfyArt/issues/133#issuecomment-6357414006)).

**Brand note:** 「ARDEN雅登家居」 is **our own replacement brand** from the #673 p4 wash (not gold text). All poster copy in this plan is **ours**. The gold headline 「焕新了！我的家」 **must not appear**.

**Product note:** anime / illustration / cartoon characters stay on nano-banana. Only **photoreal real people** are candidates for a later Auto change. **Person-row Auto change is a separate PR** — groups C/D are evidence only.

## Price sources

| Model / tier | USD | Source |
|---|---|---|
| GPT Image **2.6** flare/sunburst **t2i** medium **2k** | **$0.10** | `api/gif_image.py` `TABLE_26[("medium","2k")]` (lines 35–42); same table for flare and sunburst; cites https://wavespeed.ai/models/openai/gpt-image-2.6-flare/text-to-image |
| GPT Image **2.6** sunburst **t2i** medium **1k** | **$0.05** | same `TABLE_26[("medium","1k")]`; fixture `base_price` 0.05 |
| GPT Image **2.5** sunburst **edit** (1k catalog base) | **$0.039** | `tests/fixtures/wavespeed_catalog_subset.json` → `openai/gpt-image-2.5-sunburst/edit` `base_price` |
| GPT Image **2.6** sunburst **edit** (1k catalog base) | **$0.065** | same fixture → `openai/gpt-image-2.6-sunburst/edit` `base_price` |
| nano-banana-2.1 t2i / edit | **$0.04** | fixture `base_price` |
| seedream-v5.0-pro t2i / edit | **$0.045** | fixture `base_price` |

## Stop rules (mandatory)

1. **Serial only** — never overlap WaveSpeed calls.
2. Before each call: log **balance**. After each call: log **prediction id**, **balance**, and **delta**.
3. Stop a group after **2 failures** in that group; do not start the next image in the group.
4. Abort the whole run if **WaveSpeed balance < $20** before a call.
5. Abort if **cumulative spend would exceed $0.65** (or already has).
6. Record every prediction id against [#97](https://github.com/ganjmeng/ComfyArt/issues/97).

## Inputs committed for group B

| Role | Path |
|---|---|
| Base (window + sky, 768×1024) | `docs/qa/825/inputs/base-window-sky.png` |
| Mask (sky band α=0, rest opaque white; ComfyArt mask convention) | `docs/qa/825/inputs/mask-sky-top.png` |

Both B runs use **these exact files**.

## Group A — Poster / text t2i (2) @ **2K**

Same dense prompt; Flare vs Sunburst. Size: **resolution=2k**, **aspect_ratio=3:4** (poster), quality medium unpinned.

| # | Model | Size | Params | Catalog USD |
|---|---|---|---|---|
| A1 | `openai/gpt-image-2.6-flare/text-to-image` | 2K · 3:4 | medium (unpinned) | **$0.10** |
| A2 | `openai/gpt-image-2.6-sunburst/text-to-image` | 2K · 3:4 | medium (unpinned) | **$0.10** |

**Prompt (exact) — our copy only; never gold 「焕新了！我的家」:**

```
Furniture retail poster, light-blue velvet sofa hero on a warm wood floor.
Brand line: 「ARDEN雅登家居丨双11狂欢购」.
Small date line: 「10.24 20:00 - 11.11 23:59」.
Headline (exact): 「换个心情 / 过冬！」.
Offer lines: 「先领3000元暖家补贴」; 「11月1日0点开抢」; 「低至6折！」; 「沙发卧室客厅同场」.
Footer price chips in our words: 「预估到手 ¥2199」 and 「叠加会员券再减」.
White bold italic Chinese type with dark outline, readable small text, clean e-commerce layout, no watermark.
```

**Collage:** A1 | A2 (side-by-side L\|R). Label each panel: model · prompt summary · 2K 3:4 · $0.10.

## Group B — Masked / region edit (2) @ **1K**

Same base + mask + prompt. **2.5 Sunburst edit vs 2.6 Sunburst edit** (table before/after for the masked row).

| # | Model | Size | Params | Catalog USD |
|---|---|---|---|---|
| B1 | `openai/gpt-image-2.5-sunburst/edit` | 1K | medium (unpinned); images=[crop of base]; mask as above | **$0.039** |
| B2 | `openai/gpt-image-2.6-sunburst/edit` | 1K | medium (unpinned); same files | **$0.065** |

**Prompt (exact):**

```
Replace only the sky in the selection with a soft peach sunset, keep the building and window frames unchanged
```

**Files:** `docs/qa/825/inputs/base-window-sky.png` + `docs/qa/825/inputs/mask-sky-top.png` (identical for B1 and B2).

**Collage:** B1 | B2 (side-by-side L\|R). Label: model · prompt summary · 1K · cost.

## Group C — Person edit, identity keep (3) @ **1K** — evidence only

**Ref:** `643/wash/portrait-studio/examples/01.webp`

| # | Model | Size | Params | Catalog USD |
|---|---|---|---|---|
| C1 | `google/nano-banana-2.1/edit` | 1K | medium (unpinned), 1 ref | **$0.04** |
| C2 | `bytedance/seedream-v5.0-pro/edit` | 1K | medium (unpinned), 1 ref | **$0.045** |
| C3 | `openai/gpt-image-2.6-sunburst/edit` | 1K | medium (unpinned), 1 ref | **$0.065** |

**Prompt (exact):**

```
Keep the same person and face identity from the reference. Turn her to a 3/4 profile with a natural smile. Move her to a bright living room by the window with natural light. Outfit unchanged. Real skin texture, no AI face, no watermark.
```

**Collage order:** **reference | banana | Seedream | Sunburst** (C-ref | C1 | C2 | C3). Label each: model · prompt summary · 1K · cost.

## Group D — Person t2i (3) @ **1K** — evidence only

No reference image. First collage panel = **prompt text card** (not a generation).

| # | Model | Size | Params | Catalog USD |
|---|---|---|---|---|
| D1 | `google/nano-banana-2.1/text-to-image` | 1K | medium (unpinned) | **$0.04** |
| D2 | `bytedance/seedream-v5.0-pro` | 1K | medium (unpinned) | **$0.045** |
| D3 | `openai/gpt-image-2.6-sunburst/text-to-image` | 1K | medium (unpinned) | **$0.05** |

**Prompt (exact):**

```
Photoreal portrait of an attractive young East Asian woman, beauty-campaign grade, natural makeup, real skin texture with fine pores, soft daylight, 35mm photography look, 非网红脸, no logo, no watermark.
```

**Collage order:** **prompt card | banana | Seedream | Sunburst** (text | D1 | D2 | D3). Label each generation: model · prompt summary · 1K · cost.

## Budget

| Group | Name | Images | Catalog sum |
|---|---|---|---|
| A | Poster / text t2i @ 2K | 2 | **$0.20** |
| B | Masked edit @ 1K | 2 | **$0.104** |
| C | Person edit @ 1K | 3 | **$0.15** |
| D | Person t2i @ 1K | 3 | **$0.135** |
| | **Total** | **10** | **≈ $0.589** (under **$0.65**) |

## Out of scope
- Running any paid call without #825 approval
- Changing Auto rows for photoreal / consistency / person (separate PR)
- Anime / illustration / cartoon Auto (stays nano-banana)
- Using gold headline 「焕新了！我的家」 anywhere in A
