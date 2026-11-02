# #595 → #78 tip-pin — Phase1-S5 mount (hot order + website chip)

**Branch:** `feat/595-skills-phase1-mount` · **Asia/Shanghai** · Issue #595  
**Tip-pin:** absolute `raw.githubusercontent.com` URLs live in PR #609 body (exact tip SHA). Do not treat an older tip in chat history as current.  
**Absorbed:** `main` @ `#605` / `#575` skill-cover hover video (merge tip) + Phase1-S5 mount.

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
- Soft: #605 hover video absorbed from main (stills + muted loop when `skill.video` set)

## LEFT = ours (AFTER) — live dist zh-light 1280×800

Harness: `harness/shoot.py` + `tests/test_design_595_78_shots.py` (Playwright vs `app_url`, mock $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-home-quickstart-order-zh-light.png` | Home「用 Skill 快速开始」 first 6 = product → multi-angle → brand → character → logo-material → packaging |
| `left-ours/AFTER-home-chip-website-zh-light.png` | Home chips: **网站** lit; filtered quick-start = mobile-ui + web-product |
| `left-ours/AFTER-skills-explore-website-chip-zh-light.png` | Skills Explore: **网站** chip lit; wall = mobile-ui + web-product |
| `left-ours/AFTER-home-featured-waterfall-zh-light.png` | Explore forYou featured waterfall (Phase1 15 + interior; website chip present) |
| `left-ours/AFTER-skill-modal-brand-dualcol-zh-light.png` | SkillRun dual-col: brand presets left + inputs right |
| `left-ours/AFTER-skill-modal-multi-angle-dualcol-zh-light.png` | SkillRun dual-col: multi-angle examples carousel left + inputs right |

## @design
Please re-sign after visual check on tip (hot quick-start order + website chip + featured Phase1 + dual-col modal). Hover video from #605 is on tip (soft for mount AC).
