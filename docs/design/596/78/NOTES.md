# #596 soft FU → #78 visual review

Home soft FU (parent #589 / #580): tab row py→11 (row ≈44), chips sticky top 44, inactive tab/chip/skilltabs fg `.55` light+dark — scoped; do **not** bump global `--ca-muted`.

Mocks / harness shots only. Tip-pin via PR body `raw.githubusercontent.com` URLs to **branch HEAD**. Do not embed a tip SHA here (avoids fighting HEAD after follow-up tips).

## LEFT = ours (relative under `docs/design/596/78/left-ours/`)

| File | Locale / theme | Shows |
|------|----------------|-------|
| `01-explore-zh-light.png` | zh / light | Explore top — tabs + chips |
| `01-explore-en-dark.png` | en / dark | Explore top — tabs + chips |
| `07-sticky-zh-light.png` | zh / light | Sticky tabs (top 0) + chips (top 44) after scroll |
| `07-sticky-en-dark.png` | en / dark | Sticky tabs + chips |
| `02-masonry-zh-light.png` | zh / light | optional — masonry + floating composer |
| `02-masonry-en-dark.png` | en / dark | optional — masonry + floating composer |

Minimum pack design asked: explore top + sticky chips × zh-light + en-dark (the four `01-*` / `07-*` rows).

## L/R composites (relative under `docs/design/596/78/lr-pairs/`)

| File | Pair |
|------|------|
| `LR-01-explore-zh-light.png` | ours explore vs Lovart H2-01 |
| `LR-01-explore-en-dark.png` | ours explore (dark) vs Lovart |
| `LR-07-sticky-zh-light.png` | ours sticky vs Lovart H3-02 |
| `LR-07-sticky-en-dark.png` | ours sticky (dark) vs Lovart |

RIGHT (Lovart) originals stay on review-assets (589 pack); not duplicated here.

## Soft-FU TARGET checklist (design L/R soft PASS)

| Target | Expected | Result |
|--------|----------|--------|
| Tab row height | ∈ 43–45 (`--ca-tabs-py: 11`) | PASS |
| Chip sticky top | 44 (`--ca-homechips-top: 44px`) | PASS |
| Inactive fg light | `rgba(0,0,0,.55)` on tabs/chip/skilltabs | PASS |
| Inactive fg dark | `:root[data-theme="dark"]` → `rgba(255,255,255,.55)` | PASS |
| Global `--ca-muted` | untouched | PASS |

#589 hard locks (14/22 · gap 24 · weight 600 · no underline · chip 30 / 5×12 / gap 8) stay PASS.

Mutation lock: `tests/test_home_soft_596.py` asserts the token values above (revert → RED).

## Out of scope / residual (non-blocking)

- Chip outer pad / asymmetric tab pad (optional soft; not #596 AC)
- Featured / wash assets (#594)
