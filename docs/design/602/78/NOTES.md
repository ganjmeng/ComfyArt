# #602 soft FU → #78 visual review

Home soft FU (parent design comment 6559584299 / Ashley 2026-11-01 gaps): landing section mt **64→24**, composer float **pill↔expand** (r **28→24**, compact ~52), skillcard cover **dual fit** (`data-fit="cover"|"contain"`). Gold = lovart.ai measure pack; **do not** put competitor brand strings in `src/`.

Mocks / harness shots only. Tip-pin via PR body `raw.githubusercontent.com` URLs to **branch HEAD**. Do not embed a tip SHA here (avoids fighting HEAD after follow-up tips).

**Out of scope (product lock):** hover video / Ken Burns / focus scale-mask = P1 soft on **#575**, not #602.

## LEFT = ours

| File | Notes |
|------|-------|
| `left-ours/BEFORE-skills-to-featured-gap-annotated.png` | Pre-#602 measure — section mt 64 annotated (from 600 ashley pack @ tip-42 / 6e67b0cb lineage) |
| `left-ours/BEFORE-composer-floating-full-chrome.png` | Pre-#602 floating composer always-full ~130×758 r28 |

Live AFTER left-ours (skills→精选 24, compact pill ~52, expand ~114 r24, optional `data-fit=contain` letterbox) — shoot on tip when design re-signs; not blocking tip land of mutation locks.

## RIGHT refs (relative under `docs/design/602/78/refs-right/`)

Copied from `ComfyArt-review-assets/600/ashley-home-gap-2026-11-01/` for offline review (not duplicated into lr-pairs until AFTER left exists):

| File | Shows |
|------|-------|
| `RIGHT-lovart-skills-to-featured-gap-annotated.png` | skills→精选 gap (prefer JSON **24**) |
| `RIGHT-lovart-explore-welcome.png` | welcome composer ≈114 / r24 |
| `RIGHT-lovart-sticky-bottom.png` | scrolled compact float pill ~48–56 |
| `RIGHT-lovart-m1-bottom.png` | masonry bottom compact pill |

## Soft-FU TARGET checklist (design L/R soft PASS)

| Target | Expected | Result |
|--------|----------|--------|
| `--ca-landing-section-mt` | **24px** on `.ca-landing__section` (skills→精选 + chips→快速开始 + tools) | CODE PASS — live L/R pending |
| Composer radius | `--ca-homebox-radius: **24px**` (was 28) | CODE PASS |
| Compact float pill | `[data-floating][data-compact]` height **52** (`--ca-homebox-compact-h`); toolbar hidden; placeholder+send | CODE PASS — interaction wired |
| Expand / welcome | full chrome; blur/Escape → compact when floating; focus/click → expand | CODE PASS |
| Skillcard dual fit | default `cover`; `data-fit="contain"` → `object-fit: contain` on `--ca-field` plate; `Skill.quickStartCoverFit` + `skillQuickStartCoverFit()` | CODE PASS — builtins default cover until #594 wash marks contain |
| No force-fill | CSS must not require all covers crop-fill | CODE PASS |
| Competitor brand in src | absent | CODE PASS |

Mutation lock: `tests/test_home_soft_602.py` (revert → RED). #596 locks remain via `tests/test_home_soft_596.py`.

## Out of scope / residual (non-blocking)

- Marking specific builtins `quickStartCoverFit: 'contain'` (#594 wash)
- Featured waterfall ratio pack (#588)
- #575 hover video / Ken Burns / focus scale-mask
