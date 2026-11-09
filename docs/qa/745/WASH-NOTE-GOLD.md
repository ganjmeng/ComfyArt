# #745 金标底两段 2K

- 底图：LR 金标左栏 ×2。
- SoT：[#817](https://github.com/ganjmeng/ComfyArt/pull/817) `docs/design/673/PROMO01-REPLACE.md`（换 78 / 留 49）。本目录不改该文件。
- tip≈25 作废，勿按它验。
- 跑法：WaveSpeed `gpt-image-2.6-flare/edit` · 2k · 两段（A–E → F–H）。花费 ≈ $0.207。
- 第一次定点修补 ≈ $0.1035：`爆款价`→`人气价`，以及 EN 印章。账见 [`fix-ledger.json`](fix-ledger.json)。`人气价` 仍 **PASS**。
- 第二次定点只修英文 ≈ $0.1035。账见 [`enfix-ledger.json`](enfix-ledger.json)。
- 英文：`WINTER GLOW` + `NUVO PICKS` **PASS**；`WARM CARE` / `SOFT WARM` 仍碎裂（OCR 见 `CARE|WARM`）；`BOUBLE` / `ELVEN` 已消失。
- 请产品看英文残留是 **ACCEPT**，还是再开一轮。核对 78 处对齐，KEEP 无回退。不关闭 #745。

| 文件 | 角色 |
|---|---|
| [`docs/design/673/wash/promo-ecommerce/examples/01-washed-gold-2k.webp`](../../design/673/wash/promo-ecommerce/examples/01-washed-gold-2k.webp) | EN 修补后终图 1568×2352 |
| [`LR-gold-vs-washed.jpg`](LR-gold-vs-washed.jpg) | 金标左 \| 当前右 |
| [`LR-fix-D.jpg`](LR-fix-D.jpg) | D 区修补对照（人气价） |
| [`LR-fix-FH.jpg`](LR-fix-FH.jpg) | 第一次 F–H 英文对照 |
| [`LR-enfix-FH.jpg`](LR-enfix-FH.jpg) | 第二次 EN-only F–H 对照 |
| [`pass1-AE-gold.webp`](pass1-AE-gold.webp) | 第 1 段 A–E，1568×2352 |
| [`wash-ledger-gold.json`](wash-ledger-gold.json) | 两段账 |
| [`fix-ledger.json`](fix-ledger.json) | 第一次定点账 |
| [`enfix-ledger.json`](enfix-ledger.json) | EN-only 账 |
| [`ocr_spots-gold.json`](ocr_spots-gold.json) | 修补前 OCR 抽点 |

## pctfix (2026-11-07 22:51 Asia/Shanghai) — Related to #745

Targeted single WaveSpeed `openai/gpt-image-2.6-flare/edit` pass (tid `fb11c452b02943bead819a586c6da6bb`):

| Spot | Before (wrong tip) | After |
|------|--------------------|-------|
| Black outline bag icon | `UP TO 人气% OFF` (mis-wash) | **`UP TO 20% OFF`** |
| Red 3D bag label | `人气价` | **`惊爆价`** (owner SoT lock; 人气价 cancelled) |
| Price on red bag | ¥1899 | ¥1899 (unchanged) |

- Spend ≈ **0.1035** (bal 34.6790 → 34.5755)
- Tip: `docs/design/673/wash/promo-ecommerce/examples/01-washed-gold-2k.webp`
- L/R: [`LR-pctfix-D.jpg`](./LR-pctfix-D.jpg) · ledger [`pctfix-ledger.json`](./pctfix-ledger.json)
- Do NOT full re-wash; design/QA please re-sign this tip.
