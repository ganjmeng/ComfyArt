# #727 / #736 洗图小字审计（$0）

**规则**：金标上每个文字块都必须在我们的图上找到对应位置的文字。平台/大促元素（双11、11.11、天猫、淘宝、抖音、京东、618 等）原样保留；金标品牌名和具体卖点文案**原位改写**，不得删除。块数少于金标、或者区域被擦空，都判 FAIL。

**方法**：RapidOCR 跑两遍，1× 和 3× 放大（3× 按 1600px 分块），只取置信度 >0.6 的块，再按坐标去重。金标坐标缩放到我们的尺寸后，允许 4% 的位移，范围内没有我们的块就记为丢失；文字相似度在 0.6 到 1 之间的记为疑似错字。排版有偏移，所以另外做了人工目检：promo 01 以目检结果为准（`dropped.jpg`、`drops.json`），ppt-visual 两张是并排看过的。每张图丢失位置的对照在 `sheets/`（左金标、右我们）。脚本：`audit.py`、`two.py`。

| 图片 | PR | 丢失块 | 疑似错字 | 结论 |
|---|---|---|---|---|
| ppt-visual/examples/01 | #727+#736 | 64 / 108 | 0 | FAIL：版面是重新设计的，统计格、旅程块、品牌支柱的文字大量缺失 |
| ppt-visual/cover | #727 | 24 / 55 | 0 | FAIL：重新设计（山野栖居），金标的特性栏全部没有 |
| promo-ecommerce/examples/01 | #727+#736 | 12（目检） | 2（预旋到手价、新人礼糊字） | FAIL |
| logo-abstract/examples/01 | #727 | 2（TOWEF、PEARL） | 0 | FAIL（待设计确认是不是品牌名，品牌名应改写） |
| naive-illustration/examples/02、cover | #727 | 1（A+） | 0/1 | FAIL（小字，待设计确认） |
| naive-illustration/examples/04 | #727 | 1（333） | 0 | FAIL（待设计确认） |
| photo-split-poster/cover、examples/01 | #727 | 0 | 0/1 | PASS（残留金标原文 2026年 等另外跟踪） |
| logo-abstract cover/02/03/04、naive 01/03、promo cover | #727 | 0 | 0 | PASS |
| taobao-product/examples/07 | #736 | 0 | 4（OCR 抖动，目检文字正确） | PASS（卖点原文残留另外跟踪） |
| taobao-product/cover | #736 | – | – | 未审：仓库里没有金标 |
| */featured/* | #727 | – | – | 未审：没有对应的金标 |

## 交接
- tip：见本分支 HEAD
- 已完成：两个 PR 涉及的 18 张有金标的图，都做了 OCR 1×+3× 和目检；csv、各图对照、脚本已提交
- 下一步：设计确认 logo/naive 里那几处小字；开发在本地补字，promo 01 的 12 处、ppt-visual 两张；补完复测
- 花费：$0
