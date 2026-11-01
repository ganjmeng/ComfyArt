# #602 soft FU → #78 visual review

Home soft FU (parent design comment 6559584299 / Ashley 2026-11-01 gaps): landing section mt **64→24**, composer float **pill↔expand** (r **28→24**, compact ~52), skillcard cover **dual fit** (`data-fit="cover"|"contain"`). Gold = lovart.ai measure pack; **do not** put competitor brand strings in `src/`.

Mocks / harness shots only. Tip-pin via PR body `raw.githubusercontent.com` URLs to **branch HEAD tip SHA**. Do not embed a tip SHA here (avoids fighting HEAD after follow-up tips).

**Out of scope (product lock):** hover video / Ken Burns / focus scale-mask = P1 soft on **#575**, not #602.

## LEFT = ours (BEFORE)

| File | Notes |
|------|-------|
| `left-ours/BEFORE-skills-to-featured-gap-annotated.png` | Pre-#602 — section mt 64 annotated (600 ashley / tip-42 lineage) |
| `left-ours/BEFORE-composer-floating-full-chrome.png` | Pre-#602 floating composer always-full ~130×758 r28 |

## LEFT = ours (AFTER) — tip preview measure 2026-11-01 Asia/Shanghai

Live Playwright @1280×800 zh-light on tip `f0492865` lineage (docs tip-pin commit follows):

| File | Shows | Measured |
|------|-------|----------|
| `left-ours/AFTER-skills-to-featured-gap-annotated.png` | skills→精选 gap | **mt 24px** (`cardsBottom→featTitleTop` = 24; CSS `--ca-landing-section-mt: 24px`) |
| `left-ours/AFTER-skills-to-featured-gap-crop.png` | gap crop | same |
| `left-ours/AFTER-composer-floating-compact-pill.png` | scrolled float compact | **h 52** / **r24** / `data-compact` (placeholder + slot; toolbar hidden) |
| `left-ours/AFTER-composer-expanded.png` | float expanded | **h 114** / **r24** / full chrome (+ · Loomi · prefs · slot) |
| `left-ours/AFTER-composer-welcome-inflow.png` | welcome in-flow | **h 114** / **r24** |
| `left-ours/AFTER-skillcard-letterbox-contain.png` | dual-fit proof | forced `data-fit=contain` → `object-fit: contain` on `--ca-field` plate `rgba(0,0,0,.04)` |

Optional full-viewport: `AFTER-composer-floating-compact-pill-full.png`, `AFTER-composer-expanded-full.png`, `AFTER-skills-to-featured-gap.png`.

## L/R composites (`lr-pairs/`)

| File | Pair |
|------|------|
| `LR-skills-to-featured-gap.png` | AFTER gap crop vs Lovart annotated |
| `LR-composer-float-compact.png` | AFTER compact pill vs Lovart sticky bottom |
| `LR-composer-welcome.png` | AFTER welcome vs Lovart explore welcome |
| `LR-composer-expanded-vs-lovart-pill.png` | AFTER expanded crop vs Lovart masonry pill |

## RIGHT refs (`refs-right/`)

| File | Shows |
|------|-------|
| `RIGHT-lovart-skills-to-featured-gap-annotated.png` | skills→精选 (prefer JSON **24**) |
| `RIGHT-lovart-explore-welcome.png` | welcome ≈114 / r24 |
| `RIGHT-lovart-sticky-bottom.png` | scrolled compact float ~48–56 |
| `RIGHT-lovart-m1-bottom.png` | masonry bottom compact pill |

## Soft-FU TARGET checklist (design L/R soft PASS)

| Target | Expected | Result |
|--------|----------|--------|
| `--ca-landing-section-mt` | **24px** | **PASS** live 24 + CSS |
| Composer radius | `--ca-homebox-radius: **24px**` | **PASS** measured borderRadius 24px |
| Compact float pill | `[data-floating][data-compact]` **52** | **PASS** h=52px compact=true |
| Expand / welcome | full chrome ~114; focus expands | **PASS** h=114 expanded |
| Skillcard dual fit | cover default; contain+letterbox plate | **PASS** CSS + forced-contain demo (builtins still default cover until #594 marks contain) |
| No force-fill | CSS dual path | **PASS** |
| Competitor brand in src | absent | **PASS** |

Mutation lock: `tests/test_home_soft_602.py`. #596 locks via `tests/test_home_soft_596.py`.

## Soft residual (non-blocking)

- Builtin skills not yet marked `quickStartCoverFit: 'contain'` (#594 wash) — letterbox shot is CSS proof via attr force.
- Compact slot icon may show voice when empty (send-forward density still met at 52/r24).

## Out of scope

- #575 hover video / Ken Burns / focus scale-mask
- Featured waterfall (#588)
