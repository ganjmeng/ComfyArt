# PR #843 历史证据板只读复核

时间：2026-11-08 21:34 起（北京时间 UTC+8）。
PR：https://github.com/ganjmeng/ComfyArt/pull/843
准确 head：`10f740f9d465e944a1881b6db76850f0e7aaa394`；base：`fe342cea4b34c095285e90edc4b13da77d89a315`；读取时 OPEN。

## 总结
**历史图源选择与图内标注四项 PASS；当前真实链路四项全部 HOLD（缺证据待验，非功能 FAIL）。** 这不是合并批准、真实链路签字或关卡建议。

内建 GitHub 读取 metadata/files、#707正文/完整一页评论；5个变更仅 EVIDENCE-MATRIX.md 和四张 PNG。未查代码行为、未 checkout、未改仓库、未评论/发送/合并/关卡/付费。远程固定 head 四 PNG 已下载，并分别用 Read 打开核视觉；源图本机文件另核尺寸及 sha 与矩阵一致。未执行测试，未生成图片。

四板顶部均清晰写 HISTORICAL REFERENCE ONLY / NOT CURRENT CHAIN OUTPUT；当前 runtime commit 与 same-input proof NOT VERIFIED。均标 PENDING/HOLD、缺证据不等于功能失败。图中历史文件落地 commit 有明确“not a runtime commit”标签，未冒充当前运行版本。三技能废 Qwen RIGHT、game-art 海报均未上板。

## 四图复核
|技能|来源/历史尺寸 vs 目标|来源/标注判定|真实链路及缺项|
|---|---|---|---|
|before-after|左留空，注明来源未知/未锁；右 `docs/design/640/78/gold/before-after/cover.webp`，1600×1200 ≠ 1024×1280。来源落地版本 `206fca8fc33c302ff8ef347337e7063480d8affc`。|**PASS（历史标注）**。视觉确为金标单张对比卡；保留原比例。内在 BEFORE/AFTER 两半被明确说明不是本次系统来源对照。无废Qwen、弃wash/new19。|**HOLD**：左侧锁定来源、同输入参考绑定、当前请求/runtime、predictionID→产物绑定、done/step/time缺。现图不证明目标尺寸。|
|pose-fission|左 `docs/design/640/78/gold/pose-fission/cover.webp` 1600×1200（完整锁定多格金标文件），版本 `206fca8fc33c302ff8ef347337e7063480d8affc`；右 `docs/qa/posepro/pro_01.jpg` 1792×2400，版本 `96b149ffdfa6875cdebff6ed24425f5a271926d7`。均 ≠ 1536×2048。|**PASS（历史标注）**。只用锁定金标/posepro；明确左是历史联系表单文件，右是历史单张，未拆格伪造同输入。记录旧log四次completed，但明示未绑图片sha/任务。compare混合包未贴，废Qwen未贴。|**HOLD**：同人衣景光只改姿态的当前同次输入→调用→输出核验、参考路径/sha/任务绑定、当前runtime/request/done/step/time缺；旧provider completed不能顶Agent done。|
|game-art|左留空，说明batch3-ex01混合包仅检查未上板，原始输入未提交；右仅 `643/wash/game-art/examples/01.webp` 奔秋围棋UI 1536×2736 ≠ 1024×1824，落地版本 `876b573fad779846ecf78acd8dd53f3aa535b95a`。|**PASS（历史标注）**。视觉有标题、列表卡片/棋盘缩略、按钮与底栏，确为锁定UI01而非海报；废Qwen及两种海报cover明确排除。|**HOLD**：原始输入文件/身份缺；旧wash请求不是当前#707请求；当前runtime/request/predictionID/目标输出/done/step/time缺。|
|linkedin-banner|左为锁定完整历史 `704-lr/linkedin-banner/fixed-input-v1/design-LR.png` 3200×450，内部Lovart Spec Reference / explicit Qwen candidate标签；右为同目录旧 RIGHT.png 1584×396 = 目标。落地版本 `3dc069605e3f533bf2254c1ab98ab259083b996e`。|**PASS（历史标注）**。两侧额外覆盖 explicit candidate image only, auto/UI chain unverified；未把合成板拉为1584×396；RIGHT确为已验旧字节，不是三废Qwen之一。|**HOLD**：当前UI canvas、自动路由、一次生成、≤10步、≤3分钟到done及当前运行绑定缺。右像素一致不等于真实链路通过。|

## 与先前 inventory 的一致性/需保留的范围修正
对照 `/workspace/qa-707-evidence-inventory.md`：四槽锁定旧优一致。此前 owner-review 混合包的来源/版本缺陷，本PR通过留空未知侧、单独锁定有效源、明确落地版本和缺项改善；没有复活三废Qwen签字。

**LinkedIn 矩阵“请求缺失/旁边没有prompt”只适用于其仓库证据范围，不能扩成全局不存在。** 先前已盘点本机 `/workspace/704-lr/linkedin-banner/fixed-input-v1/request.json`、manifest.json、submit-response.json、provider-result.json、poll-001/002.json；旧taskID `567b91c978c8468cbcad615403d14171`、Qwen t2i、历史一次submission已知。它们不能补当前UI链路，建议后续文档将“缺失”限定为“本PR仓库未附历史请求，机内另有旧候选记录”。此为文档范围提醒，不影响图源/标注PASS。

pose的旧log有4个任务，不含文件路径/sha；不可由排列顺序推断pro_01就是首task。先前inventory的旧log与文件并列记录不作绑定保证。

## #707 嵌图/群图核验
#707读取时 OPEN。正文仍为旧问题与AC，**四张新图已嵌在评论**：
https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6721987448
该评论用4个 `![...](https://raw.githubusercontent.com/.../10f740f9.../docs/design/707/evidence-audit/<skill>.png)` 对应本次四板，明确不是生成runtime、不是合格当前链路L/R。评论链接目标已逐个下载成功并Read查看；确认Markdown嵌图，不声称浏览器页面渲染检查。
**群图是否已贴：未知，本次未读取/验证群消息，不以Issue嵌图代替群图完成。**

## 可直接作为附件的本机文件（下载原字节，未生成/改图）
- `/workspace/qa-843/before-after.png`（2300×1821）
- `/workspace/qa-843/pose-fission.png`（2360×2282）
- `/workspace/qa-843/game-art.png`（2300×2368）
- `/workspace/qa-843/linkedin-banner.png`（2500×1454）
上述是证据板像素，不是各技能输出像素。

固定远程图前缀：
`https://raw.githubusercontent.com/ganjmeng/ComfyArt/10f740f9d465e944a1881b6db76850f0e7aaa394/docs/design/707/evidence-audit/`
后接上述四个文件名。

下载板 SHA256（均与PR矩阵一致）：
- before-after `a0320e4972ce0b53a950772e0a6601033261366524138dd53410e1ed75f25694`
- pose-fission `16fdc23a77b729701260cfafa7c34519bcace1faf99a97b9f6479f9583a84019`
- game-art `0461ea6f9513241fb49c6fb60a40d1e7988023f0bd9c71b540b5cba41afa0d8a`
- linkedin-banner `26887c9bb0fb0cabd1979e141402605d8ae77697f23d19563275c216610d8ba5`

源图本机hash复验：金标before-after、金标pose、posepro pro_01、game-art UI01、LinkedIn RIGHT/design-LR的尺寸与SHA均与本PR矩阵一致。文件落地版本由板/矩阵记录；本次未另查提交历史来独立证明“首次落地版本”，不将该版本标签视为运行时凭据。

结论边界：只读历史图证审核完成；不签真实链路，不合并，不关#707/#704，不发布。


---
## 指定 tip 320949dc 增量跟签（2026-11-08，北京时间；22:50前）
准确 head：`320949dc129da0ad47e86f0d1f356a0e4038e1de`，内建 GitHub PR metadata 与 compare 双核一致，PR读取时 OPEN。
比较基线：`10f740f9d465e944a1881b6db76850f0e7aaa394`。
远程 compare 显示 ahead 一提交，只改 `EVIDENCE-MATRIX.md` 和 `linkedin-banner.png`；未查应用代码行为、未运行代码、未 checkout。

### 历史文档/标注结论：PASS @ 320949dc
- LinkedIn 图和矩阵已将历史请求缺失准确限缩为 **historical request not attached in this PR repository**。
- 图中承认 QA 报告的本地历史 request.json、manifest.json、submission/poll，task `567b91c978c8468cbcad615403d14171`、一次提交、无图像参考参数；说明本PR未独立核验这些本地文件，不证明当前 auto/UI、运行commit、step/time。此前唯一措辞提醒已修正。
- 新图经固定完整SHA下载并Read实看，标注清楚；左design-LR历史3200×450≠目标1584×396，右旧RIGHT为1584×396=像素目标，但明确非当前链路。来源路径、落地版本及explicit candidate边界保留。
- 另外三张按指定完整SHA重新下载，逐字节与已实看10f740f9版本相同：before-after、pose、game-art来源/标注PASS保持，历史尺寸与目标不等/未知来源留空标注均未变。
- 三废Qwen RIGHT及game-art海报仍排除。没有将历史来源PASS升级为功能/当前链路PASS。

### #707 嵌图：版本化更新一致 PASS
- 原四图评论 `6721987448` 仍钉 `10f740f9...`，并未冒充新tip。
- 修订评论 https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6722223485 明确“替代上一评论中的LinkedIn板”，嵌图钉完整 `320949dc129da0ad47e86f0d1f356a0e4038e1de`。
- 前三图旧SHA字节与新tip一致，LinkedIn采用新评论新图。因此跨两评论可得到与新tip一致四图；不是说原评论已全部换成新SHA。群图仍未知。

### 当前链路：四技能全部 HOLD（证据待验，非功能FAIL）
仍缺当前运行commit、实际请求、同次输入/参考→任务→产物→UI绑定、done/steps/time。before-after左来源未锁；pose同输入及任务/图片sha绑定缺；game-art原输入文件缺；LinkedIn当前UI画框、一次生成全链路、≤10步/≤3分钟到done缺。历史本机调用不能替代。

新tip本机附件路径：
- `/workspace/qa-843/320949dc/before-after.png`
- `/workspace/qa-843/320949dc/pose-fission.png`
- `/workspace/qa-843/320949dc/game-art.png`
- `/workspace/qa-843/320949dc/linkedin-banner.png`
LinkedIn新板sha256：`17e18b7f5ea3324722e44c9aa81048a30a0722b4e411bc1241aa55e8fd5a4998`，与矩阵一致；前三图sha沿用上节。

本轮仅内建GitHub只读+固定远程PNG读取/本地审计追加；未评论、发送、改仓库、合并、关卡或付费。历史文档PASS不是合并许可。
