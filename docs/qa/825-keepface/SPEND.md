# Spend table — #825 keep-face office-suit compare

One comparison set, serial, no retries. Asia/Shanghai (UTC+8), 2026-11-10.

- Reference: `docs/qa/825/inputs/portrait-studio-01.webp` on `6bc58dabcd236159a1911b654fa4ec33986ee3e9` (1152×1536). Uploaded via WaveSpeed `/media/upload/binary` (same path as the C set in `docs/qa/825/run_compare.py`).
- Prompt (identical, verbatim): 「保留同一个人，脸、发型和坐姿都不变，只把衣服换成深色西装、背景换成办公室，去掉画面上所有文字」
- Params: `resolution=1k`, `aspect_ratio=3:4`, `output_format=png`. Order: Seedream edit first, then Banana 2.1 edit.
- Cap **$0.10**. Live POST `/api/v3/model/price` before any submit: Seedream list **$0.045** / discounted **$0.0405**; Banana list **$0.040** / discounted **$0.036**. Catalog sum discounted **$0.0765**, list **$0.085** — both under the cap, so the set ran.
- Balance before the set: **$30.958199** (above the $20 floor)
- Balance after Seedream: **$30.917699**
- Balance after Banana / after the set: **$30.879899**
- Total spend (balance delta): **$0.078300**
- Failures: **none** (both completed on the single attempt)

| # | Model | Prediction id | Bal in | Bal out | Catalog (list / discounted) | Cost USD | Latency s |
|---|-------|---------------|--------|---------|-----------------------------|----------|-----------|
| 1 | `bytedance/seedream-v5.0-pro/edit` | `d0e72871cc254bad96e989fb76f26fc3` | 30.958199 | 30.917699 | $0.045 / $0.0405 | **$0.0405** | 41.718 |
| 2 | `google/nano-banana-2.1/edit` | `6f24fa27a7cb40ca825a245e4f93d971` | 30.917699 | 30.879899 | $0.040 / $0.0360 | **$0.0378** | 18.887 |

**Sum of per-call costs:** $0.0783 (Banana's debit was $0.0378 vs the pre-run discounted quote of $0.036; still under the $0.10 cap).

Outputs and labeled triptychs (left 原图, middle Seedream, right Banana) live in this folder. Face close-up uses the same relative crop on every frame: `(0.28, 0.32, 0.80, 0.60)` of width/height.

## Visual read (one pass, no resubmit)

- **Seedream 5.0 Pro:** Same person. Face, hairline, mole, eye spacing and expression stay very close to the reference; the seated pose (knee tucked, one hand on the knee, one on the floor, rings) is almost locked. Clothes became a dark suit and the background an office. All poster typography (「潮流级」, CREATIVE, 「视觉STYLE」, the sweater 「UNION」, the corner 「IN」) is gone. Sneakers became dress shoes.
- **Nano Banana 2.1:** Still recognizable as the same person, but with more beautifying drift (slightly larger/glossier eyes, a bit more smile, hair volume shifted on one side). The sit opened up and the leg angle changed, so “坐姿都不变” is weaker than Seedream. Suit + office change succeeded. The same overlay and sweater text is gone; no leftover 潮流级 / STYLE / UNION / IN is visible.
