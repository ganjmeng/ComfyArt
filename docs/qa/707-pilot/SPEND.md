# Spend table — #707 1k pilot on #889

Asia/Shanghai (UTC+8), 2026-11-10. Template tip `891a0119ad9764e9ca37014fa1eefbf430b00ada`.

Approved scope: 5 predictions from the #889 / #707 plan. Unpinned skills were run at 1k on the models named in the #889 plan table (see below). pose-fission keeps `google/nano-banana-pro/edit` @ 2K. Cap $3, floor $20. One at a time; same image failing twice stops the run. before-after, game-art, and LinkedIn were not rerun in the pose-fission continuation.

## Balances

- Pilot start (before-after / game-art / LinkedIn attempt): **$30.765899**
- After the LinkedIn stop (before pose-fission): **$30.666899**
- After pose-fission (pilot end): **$30.414899**
- Total spend (full-pilot balance delta): **$0.351000**
- pose-fission segment: $30.666899 → $30.414899 = **$0.252000**
- Floor stayed above $20. Total is under the ~$0.455 quote and the $3 cap.
- **Product-path LinkedIn attempt (2026-11-10 22:59–23:00 Asia/Shanghai, tip `7c38f0e3e5dc5d9ee2f9b00bf75d417a1de7e388`):** balance stayed **$30.414899**. Cost **$0.000**. Nothing was submitted.

## Product-path LinkedIn run (stopped before submit)

Tech approved one linkedin-banner image through the real product path (`api/mcp_tools/canvas.py` `generate_image` → `apply_generate` → `linkedin_decision`), with no model named in the script, same gold ref as the earlier pilot (`docs/design/640/78/gold/linkedin-banner/cover.webp`). Expected route: `wavespeed-ai/qwen-image-2.0/edit` at `size=1584*396`, about $0.03, inside the approved 5 images and the $3 cap.

The live WaveSpeed catalog was used (not the test fixture). `linkedin_decision` **blocked before any predict POST**. The handler error was: no listed image-edit model can submit size `1584*396`; a ratio-only model was not substituted. Balance before and after: **$30.414899**. No prediction id. No output file.

Cause: live `wavespeed-ai/qwen-image-2.0/edit` still has a `size` string field (`width*height`, min 256, max 4096), but that field is marked **`x-hidden: true`**. `provider_submit` and `build_payload` skip x-hidden fields, so `accepts_exact_pixels` is false and the Auto path refuses. The same model's text-to-image id, `wavespeed-ai/qwen-image-2.0/text-to-image`, has a visible `size` field and would submit `1584*396`; it was not used, because a reference image was supplied and the product path is `image_edit`. The `/model/price` endpoint does quote `wavespeed-ai/qwen-image-2.0/edit` at `size=1584*396` for $0.03, but the product path never reached submit, and this run did not bypass that gate.

The unit tests and the earlier $0 dry-run still pass because `tests/fixtures/wavespeed_catalog_subset.json` has `size: {}` on the edit model with no `x-hidden`. That fixture does not match the live catalog.

This is not a pin change and not a model substitution. The Flare 4:1 failures from the first segment are unchanged.

Live discounted quotes going in: `bytedance/seedream-v5.0-pro/edit` $0.0405 + `openai/gpt-image-2.6-flare/edit` $0.045 ×2 + `google/nano-banana-pro/edit` $0.126 ×2 = **$0.3825** (list $0.425). `openai/gpt-image-2.6-flare/edit` on game-art actually debited $0.0585; the linkedin-banner attempts were $0.

| Skill | Model | Resolution / ratio (requested) | Output px | Prediction id | Quote list / disc. | Cost USD | Status |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| before-after | `bytedance/seedream-v5.0-pro/edit` | 1k · 4:5 | 915×1144 | `bfb3daf0f5b148f4bc11db076e00f767` | $0.045 / $0.0405 | **$0.0405** | completed, attempt 1 |
| game-art | `openai/gpt-image-2.6-flare/edit` | 1k · 9:16 | 768×1360 | `16f615d83d814b3cb0da8936dc154a44` | $0.050 / $0.045 | **$0.0585** | completed, attempt 1 |
| linkedin-banner | `openai/gpt-image-2.6-flare/edit` | 1k · 4:1 (1584:396 family) | — | — | $0.050 / $0.045 | **$0.000** | submit failed twice (HTTP 400); not rerun |
| linkedin-banner (product path) | expected `wavespeed-ai/qwen-image-2.0/edit` | exact `1584*396` | — | — | $0.030 / $0.030 | **$0.000** | blocked before submit: live edit `size` is `x-hidden` |
| pose-fission 侧脸 | `google/nano-banana-pro/edit` | 2k · 3:4 | 1792×2400 | `c4903a74e972468b949b759aad45a910` | $0.140 / $0.126 | **$0.126** | completed, attempt 1 |
| pose-fission 回头 | `google/nano-banana-pro/edit` | 2k · 3:4 | 1792×2400 | `125aa37871f644218c44439c0167c878` | $0.140 / $0.126 | **$0.126** | completed, attempt 1 |

**Sum of per-call costs:** $0.3510 (matches the full-pilot balance delta). The product-path LinkedIn attempt added $0.

## LinkedIn Flare stop (first segment, unchanged)

The generate API rejected `aspect_ratio=4:1` on `openai/gpt-image-2.6-flare/edit` (HTTP 400): the field must be one of `1:1`, `1:2`, `2:1`, `1:3`, `3:1`, `2:3`, `3:2`, `3:4`, and others in the schema — **no 4:1**. Closest enum value is `3:1`. The free `/model/price` endpoint had accepted `4:1` and quoted $0.045, but the predict endpoint did not. Both attempts were the same 4:1 request from the (then) plan table; neither was charged. The pilot script had hand-picked `openai/gpt-image-2.6-flare/edit`; it did not go through the product Auto path in `api/skill_size.py` (#828), which for linkedin-banner submits `wavespeed-ai/qwen-image-2.0/edit` or `wavespeed-ai/qwen-image-2.0/text-to-image` at native `1584*396`. LinkedIn was not retried here. pose-fission was later resumed under a separate tech-lead decision, still inside the original 5-image / $3 approval.

Refs:

- before-after: `docs/design/640/78/gold/before-after/cover.webp`
- game-art typifying UI (not the 640 cover KV): `643/wash/game-art/examples/01.webp`
- linkedin-banner family cover (upload only): `docs/design/640/78/gold/linkedin-banner/cover.webp`
- pose-fission base (both shots): `643/wash/pose-fission/examples/01.webp`

Outputs and gold|output L/R (no text overlays; gold/base on the left) are in this folder as png + webp. `calls.jsonl` has submit/done events with no keys. pose-fission L/R uses ex-01 as the left frame (same person / outfit / scene).

## Visual read (no resubmit)

- **before-after:** One 4:5 comparison card (not a 4:3 card-on-dark-board). Title / split / bottom labels match the lock. Headline is exactly “Gently replenished. Clearly more even.” Disclaimer is exactly “For illustration only.” BEFORE / AFTER labels are present. Same woman, near-frontal close-up on both sides (not a 45° or 90° profile). Gold slogan is gone. Ratio 915:1144 ≈ 4:5.

- **game-art:** Still a 9:16 home/list UI (title bar, list cards, a primary button, bottom nav). Maple / moonlight / ink-wash decoration kept. Brand came out as **「听潮奔社」**, not the requested **「听潮弈社」** — the 奔 from 奔秋 leaked into the new name. Gold title 「奔秋围棋」 is otherwise gone. UI labels were rewritten (全部活动 / 进行中 / 已结束; 弈友对局赛, 清风围棋赛, 牌缘竞技场, 棋艺交流赛; 首页 / 赛事 / 排行 / 我的). Topic drift: the first thumbnail mixes 帅/将 (xiangqi) onto a board, and the third card is a playing-card “牌缘竞技场”, so the list is no longer a clean Go-only UI. Ratio 768:1360 ≈ 9:16. `openai/gpt-image-2.6-flare/edit` actual debit was $0.0585 vs the pre-run discounted quote of $0.045 (same $0.0585 actual seen on earlier `openai/gpt-image-2.6-sunburst/edit` records).

- **pose-fission 侧脸:** Strict 90° side profile, far eye not visible, full-length with headroom and both feet in frame. Same woman, camel belted blazer, black shorts, gold sandals, same hard side light and dappled tree shadows on the jacket, street still readable. Identity / outfit / location locked. Output 1792×2400 (2K, 3:4 family).

- **pose-fission 回头:** Body turned away, head looking back over the shoulder toward camera, chin past the shoulder line, full-length, same outfit / person / street / hard dappled light. The body is slightly 3/4-away rather than a fully squared back-to-camera stance, but it reads as the requested look-back. Output 1792×2400.
