# #687 local fixes (fix/687-local), no paid calls

Each fix has an L/R before/after image in this folder (`lr-*.jpg`).

| item | change |
|------|--------|
| clothing-swap | `coverPos: 'center 8%'` (crop only) |
| premium-website | `coverPos: '15% center'` (crop only; keeps the title and the candle) |
| youtube-channel-banner | **crop does not work**: the cover is 4:3, the same as the card, so object-position does nothing. It still has the gold "FAMILY FIRST" copy and still looks empty/floating on white. Logged only; it needs a re-wash. |
| motion | featured 03 removed (competitor original face) |
| product | featured set removed (all 4 off-topic and multi-brand), so it falls back to presets |
| brand | featured keeps only 01 ARC RIDE (02 ARC LABS, 03 MERIDIAN and 04 AUTUMN EDIT are other brands) |
| banner | featured keeps only 01 Lumo (HELIO, HEARTH KITCHEN and DESIGN WEEK are other brands) |
| character | featured keeps only 03 AVENTYR sheet (01 lineup, 02 VALOUR, 04 AURA poster) |
| packaging | Both LUMIERE ARTISAN labels were erased with PIL and re-set as BOTANICA LAB. The image is on branch `assets/687-local` @ b84a0579 at `687/local/packaging.webp`. RapidOCR at 3x and 6x finds no LUMIERE/ARTISAN. |

## Known issues
- The packaging cover is still low-res (462px). The relabel is a stopgap; the 2K re-wash is on the morning paid list (PAID-LIST row 1).

## 交接
- **Done so far:** all of the items above, each committed and pushed separately. PAID-LIST.md is written. Gate: `GATE_WT=/workspace/wt687l scripts/gate.sh packaging` at b36f6216 gave GATE_EXIT=0 (tsc, full unit suite and 129 e2e all pass). gate.sh runs the whole suite and does not filter by slug, so this one run covers every affected slug. The first run failed: the word "Lovart" in a comment tripped the brand-scan tests, and the pin tests had to change on purpose (test_home_cut2_580, test_skill_cover_494, e2e cut1 FEATURED_DIRS + character 03). Both are fixed in b36f6216.
- **Next step:** Angela reviews PAID-LIST.md ($1.4742 / 39 images), and design reviews PROMPTS.md for social+character. After that come the paid re-wash, the youtube-channel-banner re-wash, and the PR. `assets/687-local` needs to merge into review-assets so the packaging pin stays reachable.
- **Spend:** $0 (no paid calls, no cloud agents).
- **Balance:** $44.285449 (last known value; not re-queried, because querying is free but was not needed).
