# Spend table — #707 1k pilot on #889

Asia/Shanghai (UTC+8), 2026-11-10, tip base `891a0119ad9764e9ca37014fa1eefbf430b00ada`.

Approved scope: 5 predictions from the #889 / #707 plan. Unpinned skills at 1k via Auto routing (Seedream for people, Flare for poster/text). pose-fission keeps `google/nano-banana-pro/edit` @ 2K. Cap $3, floor $20. One at a time; same image failing twice stops the run.

- Balance before: **$30.765899** (above the $20 floor)
- Balance after the stop: **$30.666899**
- Total spend (balance delta): **$0.099000**
- Catalog quote going in (discounted): Seedream $0.0405 + Flare $0.045 ×2 + Banana Pro $0.126 ×2 = **$0.3825** (list $0.425). Far under $3.

The run stopped after linkedin-banner was rejected twice. pose-fission (both shots) was **not started**.

| Skill | Model | Resolution / ratio (requested) | Output px | Prediction id | Quote list / disc. | Cost USD | Status |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| before-after | `bytedance/seedream-v5.0-pro/edit` | 1k · 4:5 | 915×1144 | `bfb3daf0f5b148f4bc11db076e00f767` | $0.045 / $0.0405 | **$0.0405** | completed, attempt 1 |
| game-art | `openai/gpt-image-2.6-flare/edit` | 1k · 9:16 | 768×1360 | `16f615d83d814b3cb0da8936dc154a44` | $0.050 / $0.045 | **$0.0585** | completed, attempt 1 |
| linkedin-banner | `openai/gpt-image-2.6-flare/edit` | 1k · 4:1 (1584:396 family) | — | — | $0.050 / $0.045 | **$0.000** | submit failed twice (HTTP 400) |
| pose-fission 侧脸 | `google/nano-banana-pro/edit` | 2k · 3:4 | — | — | $0.140 / $0.126 | **$0.000** | not started (run stopped) |
| pose-fission 回头 | `google/nano-banana-pro/edit` | 2k · 3:4 | — | — | $0.140 / $0.126 | **$0.000** | not started (run stopped) |

**Sum of per-call costs:** $0.0990 (matches the balance delta).

## LinkedIn stop

The generate API rejected `aspect_ratio=4:1` on `openai/gpt-image-2.6-flare/edit` (HTTP 400): the field must be one of `1:1`, `1:2`, `2:1`, `1:3`, `3:1`, `2:3`, `3:2`, `3:4`, and others in the schema — **no 4:1**. Closest enum value is `3:1`. The free `/model/price` endpoint had accepted `4:1` and quoted $0.045, but the predict endpoint did not. Both attempts were the same 4:1 request from the approved plan; neither was charged. Per the rule (same image fails twice → stop the run), pose-fission was not submitted. No third attempt and no switch to `3:1` or another model.

Refs used (uploaded once each, before the first predict of that skill):

- before-after: `docs/design/640/78/gold/before-after/cover.webp`
- game-art typifying UI (not the 640 cover KV): `643/wash/game-art/examples/01.webp`
- linkedin-banner family cover (upload succeeded; predict did not): `docs/design/640/78/gold/linkedin-banner/cover.webp`

Outputs and gold\|output L/R (no text overlays; gold on the left) are in this folder as png + webp. `calls.jsonl` has submit/done events with no keys.

## Visual read (no resubmit)

- **before-after:** One 4:5 comparison card (not a 4:3 card-on-dark-board). Title / split / bottom labels match the lock. Headline is exactly “Gently replenished. Clearly more even.” Disclaimer is exactly “For illustration only.” BEFORE / AFTER labels are present. Same woman, near-frontal close-up on both sides (not a 45° or 90° profile). Gold slogan is gone. Ratio 915:1144 ≈ 4:5.

- **game-art:** Still a 9:16 home/list UI (title bar, list cards, a primary button, bottom nav). Maple / moonlight / ink-wash decoration kept. Brand came out as **「听潮奔社」**, not the requested **「听潮弈社」** — the 奔 from 奔秋 leaked into the new name. Gold title 「奔秋围棋」 is otherwise gone. UI labels were rewritten (全部活动 / 进行中 / 已结束; 弈友对局赛, 清风围棋赛, 牌缘竞技场, 棋艺交流赛; 首页 / 赛事 / 排行 / 我的). Topic drift: the first thumbnail mixes 帅/将 (xiangqi) onto a board, and the third card is a playing-card “牌缘竞技场”, so the list is no longer a clean Go-only UI. Ratio 768:1360 ≈ 9:16. Flare actual debit was $0.0585 vs the pre-run discounted quote of $0.045 (same $0.0585 actual seen on earlier 2.6-family edits).
