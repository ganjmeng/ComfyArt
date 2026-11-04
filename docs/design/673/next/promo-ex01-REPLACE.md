# promo ex01（六宫格）逐格替换表 + 付费编辑 prompt（未运行）

状态：promo ex01 @ `42f10060` 判 FAIL/HOLD（Angela 23:3x：字效被降级成灰色半透明框 + 普通黑体，小字被删）。
方案变更（23:34）：**停止本地排字**，6 格全部改用模型编辑：以**金标对应格**为底图，逐行「A 换成 B，字体效果不变」。
本文档只有替换表和 prompt，**没有发起任何付费调用**。

- 模型：WaveSpeed `google/nano-banana-2.1/edit`，1K，$0.0378/次；输出本地放大到 2K（按金标宽高比），然后拼回 2560×2214
- 预算：6 格 × 1 次 = $0.2268；同一格失败 2 次就停；总上限 ≈ $0.45
- 顺序：p4（焕新了！我的家）先试跑 → UIUX设计师 确认 prompt → 技术经理 批预算 → Angela 看 p4 L/R → 再跑其余 5 格
- 金标底图：`/workspace/next673/gold_ex01.png`（2560×2214）；按 3×2 网格切，每格约 853×1107：
  p1 x0-853/y0-1107，p2 x853-1706/y0-1107，p3 x1706-2560/y0-1107，p4 x0-853/y1107-2214，p5 x853-1706/y1107-2214，p6 x1706-2560/y1107-2214
- 保留（Angela 豁免）：双11、天猫、淘宝 logo 与角标、价签框形状、11.11 / 11月1日0点 这类大促时间节点
- 必须改：金标品牌名（VANT/LENO/glossa/LYSEN 丽森/LUMVEX/BONBUN）、具体卖点文案、具体金额；不能用近义词，双向 OCR 不得命中
- 金标文字来源：RapidOCR（`/workspace/ocrvenv`）对 `gold_ex01.png` 的全量识别，坐标为 2560×2214 原图像素
- 验收：每格字体风格、字重、颜色、描边/投影、倾斜、叠层、位置与金标一致；**禁止灰色底框**；金标每处小字我们都有同尺寸、同位置的小字；测试逐块数小字，少一处 FAIL

## 逐格替换表

### p1 服装（VANT → ORVA）
| 金标（坐标） | 我们 | 字效（照金标） |
|---|---|---|
| VANT (35,38) | ORVA | 左上白色细衬线 logo |
| AUTUMN NEW COLLECTION (34,76) | FALL FIRST DROP | 白色极小字距宽 caps |
| 双11 logo (679,31) | 保留 | 原样 |
| 秋日新章 (249,749) | 秋序上新 | 白色细宋体大字，直接压画面，无底框 |
| 新季廓形丨松弛质感丨自在成章 (247,893) | 柔软针织丨层叠穿搭丨轻暖入秋 | 白色小字，竖线分隔 |
| 上天猫搜索VANT官方旗舰店 (281,928) | 上天猫搜索ORVA官方旗舰店 | 白色小字 + 放大镜图标（平台句式按豁免保留，只换品牌） |
| 10.15 - 11.14 (330,966) | 10.18 - 11.11 | 白色小字 |
| LIMITED TIME SALE (331,994) | SEASON PRESALE | 白色极小 caps |

### p2 牛仔（LENO → MIRO）
| 金标 | 我们 | 字效 |
|---|---|---|
| LENO丨双11 (1137,25) | MIRO丨双11 | 黑色顶栏，双11 红色保留 |
| LENO (1132,601) | MIRO | 大号粗黑，居中 |
| 单宁季 (1118,682) | 轻衫季 | 大号粗黑，第二行，行距照金标 |
| 预售10.24开启 (1152,825) | 预售10.20开抢 | 中号黑色细体 |
| 付定立减88元 (1159,871) | 定金抵扣60元 | 中号黑色细体 |
| LENO官方旗舰店 (1159,973) | MIRO官方旗舰店 | 黑色小字 |
| （卡片底） | 照金标的米白卡片，不加灰框 | |

### p3 彩妆（glossa → velle）
| 金标 | 我们 | 字效 |
|---|---|---|
| glossa / glossa (1966,46)/(2110,230) | velle / velle | 酒红粗衬线大字上下错位叠排，字重与金标相同（不能变细） |
| 水润/丰唇 (1866,505) | 柔光/嘟感 | 左侧竖排小字 |
| 持久/显色 (2381,504) | 不粘/轻薄 | 右侧竖排小字 |
| PEPTIDE LIP GLAZE (2369,749) | VELVET LIP TINT | 产品上极小字 |
| 双11限时立减20 (1915,962) | 双11限时直降15 | 红色胶囊价签白字（无灰框） |
| *天猫生意参谋2026年双11彩妆品类唇釉商品交易总量排名 (1964,1024) | *数据来源：velle品牌内部统计，2026年秋冬唇部新品 | 底部极小注释字 |
| 产品瓶身 glossa 字样 | velle | 瓶身印字 |

### p4 家居（LYSEN 丽森 → ARDEN 雅登家居）
| 金标 | 我们 | 字效 |
|---|---|---|
| LYSEN (36,1167) | ARDEN | 白色小 logo |
| 丽森家居丨双11狂欢购 (127,1166) | 雅登家居丨双11狂欢购 | 白色小字，双11狂欢购保留 |
| 焕新了！(18,1266) | 换个心情 | 白色粗斜体 + 深色描边，大字 |
| 我的家 (81,1392) | 过冬！ | 同上，第二行，错位缩进照金标 |
| 立抢5000元大额津贴 (56,1913) | 先领3000元暖家补贴 | 白色/黄色小字 |
| 11月1日0点 (52,1952) | 11月1日0点 | 黄色大斜体（时间节点保留） |
| 抢半价！(112,2026) | 低至6折！ | 黄色大斜体 |

### p5 相机（LUMVEX → KORAX）
| 金标 | 我们 | 字效 |
|---|---|---|
| LUMVEX (1001,1266) × 双11 (1417,1239) | KORAX × 双11 | 白色宽体 + 红色双11 logo |
| 全画幅旗舰 (1035,1355) | 无反新标杆 | 白色中字 |
| 定格光影 (1326,1356) | 捕捉每一刻 | 渐变金色二级标语（UIUX：必须补回） |
| 镜头 LUMVEX / Asph. / APO / 2/23 | KORAX / Asph. / APO / 2/23（只换品牌，光学参数是通用标识） | 镜头印字 |
| 天猫 / 淘宝 icon (1101,2085) | 保留 | 原样 |
| 爱在心选礼 (1302,2095) | 好物送心意 | 白色小字 |

### p6 饼干（BONBUN → CRUMBO）
| 金标 | 我们 | 字效 |
|---|---|---|
| 黄油曲奇 (1827,1206) | 黄油小饼 | 深棕粗黑大字 |
| BONBUN COOKIES 叠层 (1827,1336)/(2020,1430) | CRUMBO BISCUITS | 描边叠层大字，颜色与描边同金标 |
| 竖排 BONBUN (2441,1205) | CRUMBO | 右侧竖排小字 |
| 双11必买 / 满300减50 (2309,1271) | 双11必买 / 满199减30 | 红色爆炸角标，双11必买保留 |
| 包装上 BONBUN / MILK / COOCKIES | CRUMBO / CREAM / BISCUITS | 包装印字 |
| 1盒解锁6款口味 (1854,2011) | 一盒尝遍8种风味 | 底部要点小字 1 |
| 进口黄油香浓酥脆 (1859,2051) | 新西兰乳脂现烤松脆 | 要点小字 2 |
| 买2盒加赠新品试吃 (1858,2091) | 下单再送限定小包装 | 要点小字 3 |
| 背景 | 照金标黄色底（不要薄荷绿），不加灰框 | |

## 通用 prompt 模板
```
Edit this poster panel. Keep EVERYTHING identical to the input image — layout, photo, product, colours, background, lighting, and every font's typeface, weight, size, colour, stroke/outline, shadow, italic tilt, stacking and exact position. Only change the text content, line by line:
<逐行 "A" -> "B">
Keep these exactly as they are: <保留项>.
Every replaced line must stay at the same size and position as the original line; do not delete any text, do not add boxes, panels, or grey/translucent backgrounds behind text, do not add any new text.
```
负向要求写在正文里（nano-banana edit 无 negative 参数）。

## 逐格 prompt

### p1
```
Edit this poster panel. Keep everything identical — photo, model, clothing, colours, layout, and every font's typeface, weight, size, colour, shadow and exact position. Only change the text content, line by line:
"VANT" -> "ORVA" (top-left white thin serif logo)
"AUTUMN NEW COLLECTION" -> "FALL FIRST DROP"
"秋日新章" -> "秋序上新" (same large thin white Song/serif style, directly on the photo)
"新季廓形丨松弛质感丨自在成章" -> "柔软针织丨层叠穿搭丨轻暖入秋"
"上天猫搜索VANT官方旗舰店" -> "上天猫搜索ORVA官方旗舰店" (keep the search icon)
"10.15 - 11.14" -> "10.18 - 11.11"
"LIMITED TIME SALE" -> "SEASON PRESALE"
Keep the red "双11" logo at the top exactly as it is.
Each replaced line keeps the same size and position; do not delete any text, do not add boxes or grey/translucent backgrounds behind text, do not add new text.
```
### p2
```
Edit this poster panel. Keep everything identical — photo, model, the off-white card, colours, layout, and every font's typeface, weight, size, colour and exact position. Only change the text content, line by line:
"LENO丨双11" -> "MIRO丨双11" (keep "双11" red)
"LENO" -> "MIRO" (same huge bold black type)
"单宁季" -> "轻衫季" (same huge bold black type, same line spacing)
"预售10.24开启" -> "预售10.20开抢"
"付定立减88元" -> "定金抵扣60元"
"LENO官方旗舰店" -> "MIRO官方旗舰店"
Each replaced line keeps the same size and position; do not delete any text, do not add grey boxes or translucent panels, do not add new text.
```
### p3
```
Edit this poster panel. Keep everything identical — product photo, colours, layout, and every font's typeface, weight, size, colour and exact position. Only change the text content, line by line:
"glossa" (top, large wine-red heavy serif) -> "velle", same weight and size
"glossa" (second, offset stacked line) -> "velle", same weight, size and offset
"水润 / 丰唇" (left vertical small text) -> "柔光 / 嘟感"
"持久 / 显色" (right vertical small text) -> "不粘 / 轻薄"
"PEPTIDE LIP GLAZE" -> "VELVET LIP TINT"
"双11限时立减20" -> "双11限时直降15" (keep the red capsule price tag with white text)
"*天猫生意参谋2026年双11彩妆品类唇釉商品交易总量排名" -> "*数据来源：velle品牌内部统计，2026年秋冬唇部新品"
Any "glossa" printed on the product -> "velle".
Each replaced line keeps the same size and position; do not delete any text, do not add grey boxes or translucent panels, do not add new text.
```
### p4（试跑格；UIUX 已批 3 处修改，技术经理批上限 $0.45；底图 gold_ex01.png crop (0,1107)-(853,2214)）
```
Edit this poster panel. Keep the room photo, layout, lighting and colours identical, except recolour the leather sofa to a light dusty-blue velvet sofa (same shape, same position). Keep every font's typeface, weight, size, colour, dark outline stroke, italic slant and exact position. Only change the text content, line by line:
"LYSEN" -> "ARDEN"
"丽森家居丨双11狂欢购" -> "雅登家居丨双11狂欢购"
"焕新了！" -> "换个心情" (same white bold italic with dark stroke)
"我的家" -> "过冬！" (same white bold italic with dark stroke, same indent)
"立抢5000元大额津贴" -> "先领3000元暖家补贴"
"11月1日0点" -> keep as is
"抢半价！" -> "低至6折！" (same big yellow italic)
Each replaced line keeps the same size and position; do not delete any text, do not add grey boxes or translucent panels, do not add new text. All Chinese characters must be correct and crisp; no garbled or extra characters.
```
### p5
```
Edit this poster panel. Keep everything identical — camera and lens photo, colours, layout, and every font's typeface, weight, size, colour, gradient and exact position. Only change the text content, line by line:
"LUMVEX" (headline, next to the red 双11 logo) -> "KORAX"
"全画幅旗舰" -> "无反新标杆"
"定格光影" -> "捕捉每一刻" (same gold gradient secondary slogan)
"LUMVEX" printed on the lens -> "KORAX" (keep "Asph.", "APO", "2/23")
"爱在心选礼" -> "好物送心意"
Keep the red "双11" logo and the 天猫 / 淘宝 icons exactly as they are.
Each replaced line keeps the same size and position; do not delete any text, do not add grey boxes or translucent panels, do not add new text.
```

### p6
底图：金标 p6 格 `gold_ex01.png` crop (1706,1107)-(2560,2214)，1K。
```
Edit this poster panel. Keep everything identical — the yellow background, cookies, packaging boxes, crumbs, colours, layout, and every font's typeface, weight, size, colour, outline stroke, shadow, stacking and exact position. Only change the text content, line by line:
"黄油曲奇" -> "黄油小饼" (same heavy dark-brown bold type)
"BONBUN" (large outlined stacked word) -> "CRUMBO" (same outline and stacking)
"COOKIES" (large outlined stacked word) -> "BISCUITS" (same outline and stacking)
"BONBUN" (small vertical text on the right edge) -> "CRUMBO"
"满300减50" -> "满199减30" (inside the red starburst badge; keep "双11必买" as it is)
On the packaging: "BONBUN" -> "CRUMBO", "MILK" -> "CREAM", "COOCKIES" -> "BISCUITS"
"1盒解锁6款口味" -> "一盒尝遍8种风味"
"进口黄油香浓酥脆" -> "新西兰乳脂现烤松脆"
"买2盒加赠新品试吃" -> "下单再送限定小包装"
Keep the yellow background and the red corner badge. Each replaced line keeps the same size and position; do not delete any text, do not add boxes, mint/green backgrounds, or grey/translucent panels behind text, do not add any new text.
```
试跑（p4）后验收：双向 OCR（金标原文不得命中）+ 小字计数（p4 金标 logo、顶栏小字、津贴小字共 3 处必须都在）+ 字效 2× L/R。

## 交接
- 分支 `docs/673-audit`；本文件是 promo ex01 返工的唯一依据，表内金标坐标来自 RapidOCR 全图识别
- 金标底图 `/workspace/next673/gold_ex01.png`（不在仓库，交接时按 `docs/design/673/batch/pulled/` 同源路径重新拉取）
- **尚未花费任何钱**；下一步：UIUX 确认 p4 prompt → 技术经理批 $0.45 上限 → 跑 p4（1 次 $0.0378）→ Angela 看 L/R → 其余 5 格
- 每次调用按 prediction id 记入 PAID-LIST；余额 < $20 停；同格失败 2 次停
- 本地排字方案（promo_type.py）已废弃，不要再用灰框

## p4 试跑结果（2026-11-04 23:4x UTC+8，1 次调用）
- prediction `080985f535a44cb18e0a3bbee733bafc`，$0.0378，余额 $43.673706 → $43.635906；原图 `raw/p4_pilot_raw.png`（896×1200），本地 LANCZOS 缩放到 853×1107，无任何本地叠字
- L/R：`lr/p4pilot/p4_LR_full.jpg`、`p4_LR_title_2x.jpg`、`p4_LR_bottom_2x.jpg`；OCR：`lr/p4pilot/ocr_both_ways.txt`
- 字效：白色粗斜体 + 深色描边、斜向白条、顶栏、底部斜体都与金标一致，无灰框；沙发改成浅雾蓝丝绒，茶几、矮凳、地毯没有串色
- 双向 OCR：金标品牌名和卖点原文 0 命中（只剩豁免的「双11狂欢购」「11月1日0点」）；小字 3 处都在
- **错字 3 处（判 FAIL，第 1 次）**：「过冬！」写成了「被冬！」；「暖家补贴」写成了「暖家减贴」；「低至6折！」写成了「抢6折！」（漏掉「低至」，留了金标的「抢」）
- 另外：沙发款式略有变化（扶手更方），不只是换了颜色
- 按指令只跑 1 次，未重试；该格还剩 1 次重试机会
