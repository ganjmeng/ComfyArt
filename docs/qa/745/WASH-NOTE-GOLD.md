# promo 01 金底两遍 2K（#745）

只归档已生成的金底洗图。本目录不重洗、不改产品代码、不改 `docs/design/673/PROMO01-REPLACE.md`（#817 拥有 SoT）。

| 项 | 值 |
|---|---|
| 底 | LR 金标左栏 ×2（1702×2560） |
| SoT | #817 换 78 / 留 49 |
| 作废 | tip≈25 操作表不是 SoT；分支 `cursor/745-promo01-wash-2k` 已删 |
| 模型 | WaveSpeed `gpt-image-2.6-flare/edit`，2K，A–E → F–H |
| 成片 | 1568×2352（模型输出，不是底图 1702×2560） |
| 两段花费 | ≈ $0.207 |
| 定点 fix | 爆款价→人气价 已做；EN 部分叠上。再花 ≈ $0.1035。合计 ≈ $0.311 |

开 PR 前修正件已到，入库的 `01-washed-gold-2k.webp` 与 `LR-gold-vs-washed.jpg` 是 fix 之后的版本。

## 文件

- 终稿（fix 后）：`docs/design/673/wash/promo-ecommerce/examples/01-washed-gold-2k.webp`
- pass1 A–E：`docs/qa/745/pass1-AE-gold.webp`
- 两段账：`docs/qa/745/wash-ledger-gold.json`
- fix 账：`docs/qa/745/fix-ledger.json`
- 全图 L/R（左金标 / 右 fix 后）：`docs/qa/745/LR-gold-vs-washed.jpg`
- D 区 fix 裁切：`docs/qa/745/LR-fix-D.jpg`
- F–H fix 裁切：`docs/qa/745/LR-fix-FH.jpg`
- pass1 OCR（fix 前）：`docs/qa/745/ocr_spots-gold.json`

## OCR

pass1：78折 / 羽绒服 / 怕冷星 PASS；爆款价 FAIL；EN SoT WEAK。

fix 后：爆款价→人气价 已落到 D 袋；EN（WARM CARE / WINTER GLOW / NUVO PICKS / SOFT WARM）只是部分叠在原圈上，底圈 NUVO DOUBLE ELEVEN 仍在。`ocr_spots-gold.json` 不含这次 fix。

请 @QA 对 L/R 做 78 对齐，并确认 KEEP 无回退。请同时看 `LR-fix-D.jpg`：黑袋原文「UP TO 20% OFF」在 fix 后画面上像变成了「入气% OFF」。
