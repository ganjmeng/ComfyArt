# #595 → #78 tip-pin — Phase1-S5 mount (hot order + website chip)

**Tip:** `b61484001ec3f26c81a3e6a7543d9dd1e6145127` · **Asia/Shanghai** · branch `feat/595-skills-phase1-mount`  
**Raw tip-pin:** https://raw.githubusercontent.com/ganjmeng/ComfyArt/b61484001ec3f26c81a3e6a7543d9dd1e6145127/docs/design/595/78/NOTES.md  
**Base:** `feat/594-skills-phase1-wash-static` @ `42051d6f` (PR #606 wash; that tip also carries #604/#602 soft)  
**Issue:** #595

## Mount (Phase1 15 hot order)

| # | id | surface |
|---:|---|---|
| 1 | product | home quick-start #1 + featured lead |
| 2 | multi-angle | quick-start #2 |
| 3 | brand | quick-start #3 |
| 4 | character | quick-start #4 |
| 5 | logo-material | quick-start #5 |
| 6 | packaging | quick-start #6 |
| 7–15 | motion · meta-ads · poster · thumbnail · mobile-ui · social · marketing-campaign · web-product · banner | Explore forYou + featured waterfall |
| — | interior · custom-workflow | after Phase1 (untouched; not Phase1 slots) |

`PHASE1_SKILL_IDS` + `orderBuiltins` in `src/skills.ts`. Home / Skills Explore both `loadSkills()` → same source. `website` chip lit by `mobile-ui` + `web-product`.

## Dialog / regression
- Left: examples filmstrip (`SkillExamples`) and/or presets; right: inputs; CTA → Agent (`mode=agent`)
- e2e: multi-angle carousel present; brand dialog → new project (`test_e2e_skills_phase1_595`)
- No demo / placeholder media; no competitor CDN or name in `src/`

## left-ours
- Mount is data-order wiring on existing cut2 chrome (no new chrome tokens). Visual delta = quick-start card order + website chip occupancy + new6 in featured-v2.
- Design walk on tip: home forYou quick-start (6) + `home-chip-website` + Skills Explore website wall.

## @design
Please re-sign after visual check on tip (hot quick-start order + website chip + featured includes new6). Soft: #605 hover video not required for this mount.
