# #594 → #78 tip-pin — Phase1 new6 wash static + dual-fit

**Tip:** `42051d6fcce8c560c79f58c8754ace1299c76ef6` · **Asia/Shanghai** · branch `feat/594-skills-phase1-wash-static`  
**review-assets pin:** `cc76d743d416c3d9a9a6852d811a7a80caf40319`  
**Eye:** design soft → **6/6 PASS** after `mobile-ui/cover` overnight harden regen (EYE-CHECK.md).

## Completeness (new6)

| skill | cover (covers-v4) | featured×4 (featured-v2) | examples×4 (594/wash) | dual-fit | video |
|---|---|---|---|---|---|
| multi-angle | PASS | PASS | PASS | contain | none (#575) |
| logo-material | PASS | PASS | PASS | contain | none |
| meta-ads | PASS | PASS | PASS | contain | none |
| mobile-ui | PASS (regen) | PASS | PASS | contain | none |
| web-product | PASS | PASS | PASS | contain | none |
| marketing-campaign | PASS | PASS | PASS | contain | none |

## Dual-fit
- Home quick-start + Skills wall: `quickStartCoverFit: 'contain'` → `data-fit=contain` letterbox on `--ca-field` plate (#602 API).
- Featured masonry: native AR full-bleed (unchanged).
- No Lovart CDN / no competitor name in `src/`.

## left-ours
- `cover-<id>.webp` — the six covers-v4 stills pinned in src.
- `AFTER-mobile-ui-cover-regen.webp` — Lumen Habit 3-phone cover that cleared prior SOFT garble.

## @design
Please re-sign after visual check on tip (Skills wall contain letterbox + home featured for new6). Soft PASS already recorded overnight; mobile-ui cover harden is the delta.
