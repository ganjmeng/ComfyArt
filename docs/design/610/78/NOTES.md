# #610 soft P1 → #78 visual review

Home category pills 1:1 gold order + **inline starter card** click (retire prompt-fill primary). Product lock: `/workspace/lovart-home-tools-nov1/PRODUCT-LOCK-HOME-QUICK.md` + prep `CLICK-BEHAVIOR.md` / `TARGETS.md`. Gold measure pack only in docs — **do not** put competitor brand strings in `src/`.

Mocks / CSS-class harness shots (zh-light). Tip-pin via PR body `raw.githubusercontent.com` URLs to **branch HEAD tip SHA**. Do not embed a tip SHA here.

**Non-blocking** vs #606 / #604 / #594 / #595 / #575.

## Product lock (implemented)

| Item | Lock | Ours |
|------|------|------|
| Order L→R ZH | 电商 → 社交媒体 → 品牌 → 创意 → 网站 | `QUICK` ids ecommerce→social→brand→creative→website |
| Order L→R EN | E-commerce → Social media → Brand → Creative → Website | locales `home.quick*` |
| Click | replace pills with inline starter (5 icon toggles + Close + 3 suggests) | `setStarter(q.id)` → `.ca-landing__starter` |
| Close | restores pills | `data-testid=home-v3-starter-back` / `aria-label=Close` |
| Composer | stays empty; rotating placeholder continues | no `setText(prompt)` on pill click |
| URL / chrome | stay on home; no modal; no Explore tab switch | state-only under composer |
| Five pills only | no 拆解图片 in the 1:1 row | breakdown removed from quick row |
| Tools | #537/#540 untouched | `HOME_TOOL_CARDS` / `MORE_HOME_TOOLS` unchanged |
| character | forYou-only | not in starter suggests |

## Phase1 suggestion mapping (3 per pill)

| Pill | skillIds |
|------|----------|
| 电商 | `product`, `packaging`, `multi-angle` |
| 社交媒体 | `social`, `thumbnail`, soft 3rd = second `social` (`socialAlt`) |
| 品牌 | `brand`, `logo-material`, soft 3rd = second `brand` (`brandAlt`) |
| 创意 | `poster`, `banner`, `meta-ads` (from poster/banner/motion/meta-ads/marketing-campaign) |
| 网站 | `mobile-ui`, `web-product`, soft 3rd = second `web-product` (`webProductAlt`) |

Suggestion click → existing `trySkill` (SkillRunDialog path). Composer not filled as primary.

## LEFT = ours (AFTER) — CSS-class mock 2026-11-01 Asia/Shanghai

Harness uses production classnames / testids from `home.css` + `Home.tsx` (not live ComfyUI serve — soft $0).

| File | Shows |
|------|-------|
| `left-ours/AFTER-pills-order-zh-light.png` | welcome pills L→R 电商→… + empty composer placeholder |
| `left-ours/AFTER-pills-row-crop.png` | pills row crop |
| `left-ours/AFTER-starter-ecommerce-zh-light.png` | starter after 电商; icon `aria-pressed=true`; Close; 3 suggests |
| `left-ours/AFTER-starter-social.png` | starter after 社交媒体; pressed icon + 3 Phase1 suggests |
| `left-ours/AFTER-starter-brand.png` | starter after 品牌 |
| `left-ours/AFTER-starter-creative.png` | starter after 创意 |
| `left-ours/AFTER-starter-website.png` | starter after 网站 |
| `left-ours/AFTER-starter-close-pills.png` | Close → pills row restored (电商→…→网站) |
| `left-ours/AFTER-starter-card-crop.png` | starter card crop (电商) |
| `harness/mock.html` + `harness/shoot.py` | Playwright CSS-class harness (prod classnames/testids) |

## L/R composites (`lr-pairs/`)

| File | Pair |
|------|------|
| `LR-pills-order.png` | ours pills vs gold home-before |
| `LR-starter-ecommerce.png` | ours starter vs gold ecommerce-after |

## RIGHT refs (`refs-right/`)

Copied from box prep `ComfyArt-review-assets/610/prep/right-lovart/` (gold signed-in home click pack).

| File | Shows |
|------|-------|
| `00-home-before-any-pill.png` | gold pills before click |
| `01-ecommerce-{before,after}.png` | ecommerce click |
| `02-social-{before,after}.png` | social |
| `03-brand-{before,after}.png` | brand |
| `04-creative-{before,after}.png` | creative |
| `05-website-{before,after}.png` | website |

## Soft TARGET checklist

| Target | Expected | Result |
|--------|----------|--------|
| Pill order ZH/EN | ecommerce-first 1:1 | **PASS** source + locales + soft test |
| Chip chrome | h32 / gap8 / r9999 | **PASS** `.ca-landing__chip` |
| Starter on click | 5 icons + Close + 3 suggests | **PASS** markup + CSS |
| Close restores | `home-v3-starter-back` | **PASS** |
| No prompt-fill primary | composer empty | **PASS** (`setText(prompt)` absent) |
| Phase1 skill ids | table above | **PASS** |
| Tools segregation | #537/#540 intact | **PASS** `test_home_tools_537` |
| Competitor brand in src | absent | **PASS** |

Mutation lock: `tests/test_home_soft_610.py`. Prior soft locks `#602` / `#596` still green.

## Soft residual (non-blocking)

- Soft 3rd suggestions for social/brand/website reuse family skill id with alt locale (map has only 2 builtins) — prefer unique ids when Phase1 grows.
- Live Playwright against running ComfyArt custom-node serve deferred (mock CSS harness for tip-bound #78).
- Full 5-pill starter matrix + Close-restored filmed on CSS harness (2026-11-01 Asia/Shanghai).
- Merged `origin/main` @ `c4fb9dc` (#606) for MERGEABLE; tip SHA in PR body.

## Out of scope

- `+` → Skills Explore parity
- Featured waterfall / #575 hover video
- Changing Tools cards (#537/#540)
