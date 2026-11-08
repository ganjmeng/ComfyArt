# #707 / #704 只读证据盘点

盘点时间：2026-11-08 21:05–21:09（北京时间 UTC+8；以实际工具读取为准）。范围：内建 GitHub 只读卡/评论/main；已有本机证据；未 checkout、未改仓库、未生成图片、未调用供应商、未付费、未发布。

## 结论
- 当前 GitHub main：`fe342cea4b34c095285e90edc4b13da77d89a315`。
- #707 **OPEN**；模板/尺寸层 #827 已合 `14506db3`；历史 QA 82 passed @ `4c99019` 只证明单测/假接口门。当前四技能真实 UI 全链路均 **HOLD（证据待验，非功能 FAIL）**。
- #704 当前 API 状态 **CLOSED**，但 #707 仍 open，不能因旧资产入库或父卡已关宣称全链路完成。
- #837 QA @ `4642064e` 是四槽 SoT 字节/路径签（1 passed），不是当前 tip 重新跑 UI、模型路由和生成的证明。PR 中“tip RIGHT”应解释为复用资产登记，不是新生成。
- 最新撤回优先：三技能 fixed-input Qwen RIGHT 虽有 manifest 和旧 design-review PASS，已在 #704 撤销，不能复活签字；LinkedIn 已验 RIGHT 保留。

## 先给可直接挂群的真实本机图（本盘点不发布）
|技能|真实对照图路径|图内身份/来源/版本检查及使用限制|
|---|---|---|
|pose|`/workspace/ComfyArt/docs/qa/posepro/compare_posepro.jpg`|可见 Lovart/gold 与 nano-banana-pro edit 分组标签；历史金标/posepro 对照。无当前 main SHA、请求/任务 ID、运行时间，不能标为当前输出。|
|pose 补充包|`/workspace/704-lr/owner-review/01-pose-fission-LR-pack.jpg`|已打开；含多组旧图，部分文字太小/中文缺字；不足以独立证明每组来源/版本。建议优先上面单幅 compare，并附明确来源说明。|
|before-after|`/workspace/704-lr/owner-review/02-before-after-LR-pack.jpg`|已打开；有 cover.webp / before-after-exXX-lr.webp 文件名，含金标与旧 batch1/new19 材料；不是当前输出。每组系统身份及版本不足，且夹杂已弃 wash/new19，不作为整包有效签图。|
|before-after 旧板|`/workspace/704-lr/old-best-lr/02-before-after-LR-board.jpg`|文件存在，未独立打开核图内标签；仅历史对照候选，非当前输出。有效 SoT 只认金标 cover。|
|game-art 优先|`/workspace/704-lr/old-best-lr/game-art-correct-ui/COMPARE-wrong-poster-vs-UI.jpg`|已打开；图内标明错海报 cover、UI wash ex01 `643/wash/.../01.webp`、batch3-ex01 L=gold R=wash、wash ex02。来源比只写 L/R 明确，但中文有缺字且无当前 tip/运行版本。它是排错/来源板，不是当前链路通过图。|
|game-art 不宜整包签|`/workspace/704-lr/owner-review/03-game-art-LR-pack.jpg`|已打开；混有弃用海报 cover 与多组 UI；仅文件名、不足以代表锁定 SoT。不能拿整包顶有效当前输出。|
|linkedin 优先|`/workspace/704-lr/linkedin-banner/fixed-input-v1/QA-LR.png`|已打开；上栏 LEFT-Lovart，下栏 RIGHT-explicit Qwen candidate，身份明确。缺当前 SHA/时间/任务 ID 图内标注；是已验旧候选，非自动链路输出。|
|linkedin 挂群缩略包|`/workspace/704-lr/owner-review/04-linkedin-QA-LR.jpg`|已打开，同样保留上述身份标签；标题中文部分缺字。|

所有“可挂群”仅指真实文件存在可供设计选择，不代表已发布、完整 L/R 验收或当前链路 PASS。未新增/修图；缺来源版本标签处列为证据缺项。

## 逐技能证据
### 1. before-after — 目标 1024×1280
- 锁定旧优：`/workspace/ComfyArt/docs/design/640/78/gold/before-after/cover.webp`，本机实测 **1600×1200**，是历史金标，不等于目标尺寸新产物。单张对比卡视觉参考；不是当前实际请求尺寸证明。
- 对照图：上述 owner-review/02 与 old-best-lr/02；前者实看包含旧 cover、batch1、new19，必须按来源区分，不能将整包都写已签。
- 历史候选记录：`/workspace/704-lr/before-after/fixed-input-v1/` 中 request.json、prompt.txt、prompt.right.txt、manifest.json、submit-response.json、poll-001..003.json、provider-result.json、provider-original、RIGHT.png、design-LR.png 均存在。taskID `d13a692c071c419989a11cb4a67d1018`；Qwen t2i；manifest/本机 RIGHT 均为 1024×1280，1 submission。
- 该 request 只有 prompt+size；参考 LEFT 仅供 prompt 视觉族参考，没有作为 edit 图片入参。**RIGHT 已作废**（#704 6720262943/6720646566），旧 design-review PASS 不再有效。
- 缺：当前 tip 原样用户输入/参考图对应、实际 Agent→generate_image 参数及上传图片凭据、当前 predictionID/输出、单张同人同光合成视觉证据、同参来源清楚的有效对照图及目标尺寸。真实链路 **HOLD**。

### 2. pose-fission — 目标 1536×2048
- 锁定旧优：posepro + 643 金标；`/workspace/ComfyArt/docs/qa/posepro/{ref_single.jpg,pro_01.jpg,pro_02.jpg,pro_03.jpg,pro_04.jpg,compare_posepro.jpg,face_crops_posepro.jpg,log.json}`。
- 本机尺寸：ref_single 700×1200；pro_01–04 均 **1792×2400**；compare 3684×640。不是 1536×2048 当前产物，不裁图冒充目标。
- 历史 log：run_id `posepro-run2-20261104150505`，四次 google/nano-banana-pro/edit completed；task IDs：`715f185cc8b9475e85568d726d2f6531`、`7949868d37b94bc9868ec8db86d4fd9e`、`96c275de895e499c87d5df1f485f8bfc`、`848a63a013044f7e9723f6095b6daf62`。prompt 明确同人衣景光、改变角度/构图；这是旧调用日志，不能当当前 tip 请求参考图已上传证明。
- 643 对照：`/workspace/ComfyArt/docs/design/643/lr/670/pose-fission-ex01-lr.webp` … `ex04-lr.webp`（本机均 728×508）；锁定旧优 `643/wash/pose-fission/examples/01..04.webp`；金标 `docs/design/640/78/gold/pose-fission/cover.webp`。
- 已废 Qwen 候选：`/workspace/704-lr/pose-fission/fixed-input-v1/`，taskID `9d8403805b7c40fdb35407cf2dc611b4`，1536×2048，1 submission；request 无图片入参，只 t2i 文字描述。不能证明参考图传入/同脸，旧 PASS_SOFT 已撤。
- 缺：当前 tip 冻结同输入+同参考图真实上传与 generate_image/edit 调用、current predictionID、1536×2048 输出、同人衣景光且只变姿态核验、带来源和版本有效对照。真实链路 **HOLD**，旧尺寸差异是证据范围差异，不直接判功能 FAIL。

### 3. game-art — 目标 1024×1824
- 锁定旧优：`/workspace/ComfyArt/643/wash/game-art/examples/01.webp`（奔秋围棋 UI），本机 **1536×2736**。是旧 UI SoT，不是当前 1024×1824 请求产物。
- 首选来源图见 game-art-correct-ui/COMPARE-wrong-poster-vs-UI.jpg；单图同目录 `REF-wash-from-batch3-ex01-RIGHT.jpg`、`KEEP-gold-UI-from-batch3-ex01-LEFT.jpg` 存在，但文件名 RIGHT/LEFT 仅其原 batch3 来源，不代表当前系统左右。
- 旧对照 `/workspace/ComfyArt/docs/design/643/lr/batch3/game-art-ex01-lr.webp` 本机 585×540。
- 明确排除金标/洗图海报 cover，以及 owner-review/03 中混入海报的部分，不以“金标”二字替代正确 UI 来源。
- 已废 Qwen 候选 `/workspace/704-lr/game-art/fixed-input-v1/`：request 为文字+size，没有 edit 图片；taskID `4f1d23b0bb234faa858375114cdae6e7`，1024×1824，1 submission；候选 design-review 虽称 UI PASS，后续已撤，不能收口。
- #707 原始输入“角色立绘/商店封面”与 UI AC 本身不一致，见 6619784811；不得沿用旧跑题输入冒充同参 UI 回归。
- 缺：当前 tip 冻结的 UI 用户输入、可追溯参考/无参考声明、实际调用/模型路由/predictionID/1024×1824输出、标题栏列表卡片按钮底部导航视觉证据、同参对照来源版本。真实链路 **HOLD**。

### 4. linkedin-banner — 目标 1584×396
- 保留已验旧 RIGHT：`/workspace/704-lr/linkedin-banner/fixed-input-v1/RIGHT.png`，本机 1584×396；SHA256 `52150b070e4c05cfd6d614fd2ae60793a90c61b30d1c6835ba4adccb42eb0c20`（manifest 与历史 QA 记录）。
- 输入：同目录 request.json，海军蓝/青绿专业产品设计师横幅、头像安全区、准确英文 PRODUCT DESIGNER / Clarity · Craft · Collaboration；size 1584*396，无图像参考参数。
- 模型 Qwen t2i，taskID `567b91c978c8468cbcad615403d14171`；manifest 为 completed、generation_submissions=1、无后处理；submit-response/provider-result/poll-001..002/provider-original 存在。
- QA-review.json：PASS_EXPLICIT_CANDIDATE_IMAGE_ONLY；两句英文完整、无额外文字/logo、安全区存在；design-review 同边界。QA-LR.png 图内分别标 Lovart 与 explicit Qwen candidate，不是同模型/同 seed 承诺，Lovart 图还有额外 UX/logic 标签，不能当逐字金标。
- 已签资产 design-LR.png 在 #837 记录为 3200×450，勿将对照板尺寸当输出尺寸。
- 缺：当前 main 自动选模/真实技能 UI 链路、实际画框1584×396一致性/头像叠加、从开始到 done 的状态与时间线 **≤10步、≤3分钟**、无 list_models/扩图/再建画框、最多一次生成的全链路记录。旧一次供应商提交只证明候选调用一次，不证明 UI 完成。真实链路 **HOLD**。

## 输入与左右方向冲突
- #707 正文开头写左=金标/右=我们，第二轮却写左=我们/右=Lovart；#704 后续写 LEFT=Lovart/RIGHT=Loomi。故本清单永远优先“来源路径+系统+历史版本”，不推定裸 L/R。
- #704 6692377721 明确 R1 原始 submit/quote 与原始参考图不可找回；R2 为重建包，非 R1 原件。其冻结输入主要 studio/taobao，不能直接顶四技能当前同参输入包。
- 四技能 fixed-input-v1 的 request/manifest 为显式候选记录，不是当前应用自动路由/同参考图上传记录。

## 在线核对来源（均内建 GitHub 只读）
- https://github.com/ganjmeng/ComfyArt/issues/707
- https://github.com/ganjmeng/ComfyArt/issues/704
- LinkedIn 全链路 AC：https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6621359128
- 单测 PASS/视觉 HOLD：https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6710512621
- 模板层已合但不关卡：https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6710688906
- R1 原件丢失/R2 重建：https://github.com/ganjmeng/ComfyArt/issues/704#issuecomment-6692377721
- 视觉债：https://github.com/ganjmeng/ComfyArt/issues/704#issuecomment-6710688714
- 三候选旧签（已撤）：https://github.com/ganjmeng/ComfyArt/issues/704#issuecomment-6720255500
- 撤回：https://github.com/ganjmeng/ComfyArt/issues/704#issuecomment-6720262943
- 锁旧优/禁烧：https://github.com/ganjmeng/ComfyArt/issues/704#issuecomment-6720646566
- 设计 SoT 字节签：https://github.com/ganjmeng/ComfyArt/issues/704#issuecomment-6720728797
- #837 资产清单与嵌图：https://github.com/ganjmeng/ComfyArt/pull/837
- #837 QA 字节签：https://github.com/ganjmeng/ComfyArt/pull/837#issuecomment-6720723796
- 固定版本源图统一前缀：https://raw.githubusercontent.com/ganjmeng/ComfyArt/4642064e7393285c22d8ed1be2b05eb974c12cdd/ （后接上文仓库路径；LinkedIn 后接 704-lr/linkedin-banner/fixed-input-v1/RIGHT.png 或 design-LR.png）。

## 后续待验（不在本盘点执行）
由设计选择有效来源对照图并补图内来源/版本说明；需要新真实链路证据的四槽继续 HOLD，禁烧边界不变。不得用旧签图当当前链路、不得因缺证据判当前功能 FAIL。本次仅保存内部清单，不贴 Issue、不联系他人。
