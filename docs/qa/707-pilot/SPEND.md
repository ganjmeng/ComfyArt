# Spend table — #707 1k pilot on #889

Asia/Shanghai (UTC+8), 2026-11-10. Template tip `891a0119ad9764e9ca37014fa1eefbf430b00ada`.

Approved scope: 5 predictions from the #889 / #707 plan. Unpinned skills at 1k via Auto routing (Seedream for people, Flare for poster/text). pose-fission keeps `google/nano-banana-pro/edit` @ 2K. Cap $3, floor $20. One at a time; same image failing twice stops the run. before-after, game-art, and LinkedIn were not rerun in the pose-fission continuation.

## Balances

- Pilot start (before-after / game-art / LinkedIn attempt): **$30.765899**
- After the LinkedIn stop (before pose-fission): **$30.666899**
- After pose-fission (pilot end): **$30.414899**
- Total spend (full-pilot balance delta): **$0.351000**
- pose-fission segment: $30.666899 → $30.414899 = **$0.252000**
- Floor stayed above $20. Total is under the ~$0.455 quote and the $3 cap.

Live discounted quotes going in: Seedream $0.0405 + Flare $0.045 ×2 + Banana Pro $0.126 ×2 = **$0.3825** (list $0.425). Flare game-art actually debited $0.0585; LinkedIn was $0.

| Skill | Model | Resolution / ratio (requested) | Output px | Prediction id | Quote list / disc. | Cost USD | Status |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| before-after | `bytedance/seedream-v5.0-pro/edit` | 1k · 4:5 | 915×1144 | `bfb3daf0f5b148f4bc11db076e00f767` | $0.045 / $0.0405 | **$0.0405** | completed, attempt 1 |
| game-art | `openai/gpt-image-2.6-flare/edit` | 1k · 9:16 | 768×1360 | `16f615d83d814b3cb0da8936dc154a44` | $0.050 / $0.045 | **$0.0585** | completed, attempt 1 |
| linkedin-banner | `openai/gpt-image-2.6-flare/edit` | 1k · 4:1 (1584:396 family) | — | — | $0.050 / $0.045 | **$0.000** | submit failed twice (HTTP 400); not rerun |
| pose-fission 侧脸 | `google/nano-banana-pro/edit` | 2k · 3:4 | 1792×2400 | `c4903a74e972468b949b759aad45a910` | $0.140 / $0.126 | **$0.126** | completed, attempt 1 |
| pose-fission 回头 | `google/nano-banana-pro/edit` | 2k · 3:4 | 1792×2400 | `125aa37871f644218c44439c0167c878` | $0.140 / $0.126 | **$0.126** | completed, attempt 1 |

**Sum of per-call costs:** $0.3510 (matches the full-pilot balance delta).

## LinkedIn stop (unchanged; not rerun)

The generate API rejected `aspect_ratio=4:1` on `openai/gpt-image-2.6-flare/edit` (HTTP 400): the field must be one of `1:1`, `1:2`, `2:1`, `1:3`, `3:1`, `2:3`, `3:2`, `3:4`, and others in the schema — **no 4:1**. Closest enum value is `3:1`. The free `/model/price` endpoint had accepted `4:1` and quoted $0.045, but the predict endpoint did not. Both attempts were the same 4:1 request from the approved plan; neither was charged. pose-fission was later resumed under a separate tech-lead decision, still inside the original 5-image / $3 approval. LinkedIn was not retried here.

Refs:

- before-after: `docs/design/640/78/gold/before-after/cover.webp`
- game-art typifying UI (not the 640 cover KV): `643/wash/game-art/examples/01.webp`
- linkedin-banner family cover (upload only): `docs/design/640/78/gold/linkedin-banner/cover.webp`
- pose-fission base (both shots): `643/wash/pose-fission/examples/01.webp`

Outputs and gold|output L/R (no text overlays; gold/base on the left) are in this folder as png + webp. `calls.jsonl` has submit/done events with no keys. pose-fission L/R uses ex-01 as the left frame (same person / outfit / scene).

## Visual read (no resubmit)

- **before-after:** One 4:5 comparison card (not a 4:3 card-on-dark-board). Title / split / bottom labels match the lock. Headline is exactly “Gently replenished. Clearly more even.” Disclaimer is exactly “For illustration only.” BEFORE / AFTER labels are present. Same woman, near-frontal close-up on both sides (not a 45° or 90° profile). Gold slogan is gone. Ratio 915:1144 ≈ 4:5.

- **game-art:** Still a 9:16 home/list UI (title bar, list cards, a primary button, bottom nav). Maple / moonlight / ink-wash decoration kept. Brand came out as **「听潮奔社」**, not the requested **「听潮弈社」** — the 奔 from 奔秋 leaked into the new name. Gold title 「奔秋围棋」 is otherwise gone. UI labels were rewritten (全部活动 / 进行中 / 已结束; 弈友对局赛, 清风围棋赛, 牌缘竞技场, 棋艺交流赛; 首页 / 赛事 / 排行 / 我的). Topic drift: the first thumbnail mixes 帅/将 (xiangqi) onto a board, and the third card is a playing-card “牌缘竞技场”, so the list is no longer a clean Go-only UI. Ratio 768:1360 ≈ 9:16. Flare actual debit was $0.0585 vs the pre-run discounted quote of $0.045 (same $0.0585 actual seen on earlier 2.6-family edits).

- **pose-fission 侧脸:** Strict 90° side profile, far eye not visible, full-length with headroom and both feet in frame. Same woman, camel belted blazer, black shorts, gold sandals, same hard side light and dappled tree shadows on the jacket, street still readable. Identity / outfit / location locked. Output 1792×2400 (2K, 3:4 family).

- **pose-fission 回头:** Body turned away, head looking back over the shoulder toward camera, chin past the shoulder line, full-length, same outfit / person / street / hard dappled light. The body is slightly 3/4-away rather than a fully squared back-to-camera stance, but it reads as the requested look-back. Output 1792×2400.
