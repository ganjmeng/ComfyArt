# #873 masked Flare trial (live)

- Branch: `qa/873-flare-trial`
- Model: `openai/gpt-image-2.6-flare/edit` · resolution `1k` · aspect `3:4` · crop-only (no `mask_image`)
- Mask box (full-res base): `(88,485)-(248,818)` — no nudge (can fully inside; carrier excluded)
- Prompt: sage-green finish; keep KOIRA / AMBER ROAST OOLONG / sun+koi / rim / highlights / floor shadow

## Live
| | |
|--|--|
| prediction id | `6ac1b24c9bb04b728f30985ace4bad5a` |
| balance before | $31.120199 |
| balance after | $31.061699 |
| actual $ | **$0.0585** (est $0.065, cap $0.1) |

## Diffs (result vs base)
| region | max abs Δ | n differing px |
|--|--|--|
| outside mask (`edit < 0.5`) | 38 | 5101 (feather half) |
| **outside feather** (`edit == 0`) | **0** | **0** |
| feather band | 242 | 16597 |
| inside selection | 251 | 52540 |

## Seam (#869-style)
- `seam_jump_mean`: **9.35**
- luma 3px inside / outside: 219.2 / 223.6 (Δ −4.4)

## Visual (Read)
- Can → matte sage-green; shape + logo layout unchanged
- KOIRA wordmark and AMBER ROAST OOLONG readable, not garbled
- Sun / koi line art preserved; silver rim + floor shadow kept
- Carrier above and other packs unchanged; bg patch outside selection pixel-identical
