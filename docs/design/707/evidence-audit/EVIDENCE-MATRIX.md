# #707 历史对照证据矩阵

日期：2026-11-08。只读已有文件，没有出图调用，没有改默认值，没有改应用代码。

四张板都是 **PENDING / HOLD**。缺的是当前 tip 运行时证据。这不是功能 FAIL。没有证据不等于功能失败。

板上固定句：`HISTORICAL REFERENCE ONLY / NOT CURRENT CHAIN OUTPUT; current runtime commit and same-input proof NOT VERIFIED`

文件落地 commit 不是运行时 commit。下面凡写 unknown 或 missing，都是仓库记录里没有，不补写。

## 状态

| 技能 | 状态 | 本轮目标像素 | 板上历史文件像素 | 与目标 |
|---|---|---|---|---|
| before-after | PENDING/HOLD | 1024×1280 | 金标 cover 1600×1200 | 不相等 |
| pose-fission | PENDING/HOLD | 1536×2048 | 金标 cover 1600×1200；pro_01 1792×2400 | 都不相等 |
| game-art | PENDING/HOLD | 1024×1824 | wash UI 01 1536×2736 | 不相等 |
| linkedin-banner | PENDING/HOLD | 1584×396 | RIGHT.png 1584×396；design-LR.png 3200×450 | RIGHT 像素与文档目标一致，不是当前链路证明；design-LR 不相等 |

## before-after

| 字段 | 结果 |
|---|---|
| 输入/参考身份 | 缺失。MANIFEST `tip_right` 只有金标 cover。LEFT 没有锁定路径。`STATUS.txt` 只写了外部目录 `ComfyArt-review-assets/phase3/bc-refs/before-after/`，该树不在本仓库，不能当成已核验输入图。 |
| 请求 | 缺失。`wash-manifest.before-after-strong.json` 的厨房重绘 prompt 属于另一张洗图，不是这张金标的生成请求。 |
| 运行时 commit | 缺失。文件落地 commit `206fca8fc33c302ff8ef347337e7063480d8affc`（2026-11-02 +0800，#640 Phase3-S1）不是当前运行时 commit。 |
| 图像尺寸 | 已核验文件头 1600×1200。目标 1024×1280。不相等。板上按原比例缩小显示，没有改写成目标比例。 |
| done | 缺失 |
| step | 缺失 |
| time | 缺失 |
| sha256 | `df04c9ddbb2c7c2da07b3e28dd5da6ee2ff5268e29ebe8fb5773ed20e961d8f8`，与 MANIFEST 一致 |
| 未使用 | 作废 Qwen `704-lr/before-after/fixed-input-v1/RIGHT.png`（工作区不存在）；`643/wash/before-after/cover.webp` sha `196264b7c740a49ca57d392f330205ed0d5925125247012dc20b31ed89365bf9`；`docs/design/643/lr/new19/before-after-lr.webp` sha `97b275adc1b2578a8e96e64a6123e54962817db9a76a1ec76873600939abc4be` |

旧金标在。当前同输入、当前运行时、done/step/time 都不在。

## pose-fission

| 字段 | 结果 |
|---|---|
| 输入/参考身份 | 历史参考图路径：log 未写文件名，标 unknown。`docs/qa/posepro/ref_single.jpg` 不在 tip_right，未上板，也不把它当成那 4 次调用的输入。金标 cover 与 `pro_01.jpg` 是两个锁定文件，同输入未核验。 |
| 历史 4 次调用 | 已核验存在于 `docs/qa/posepro/log.json`：`run_id` `posepro-run2-20261104150505`，4 条 `status=completed`，记录尺寸字符串 `1792x2400`，模型 `google/nano-banana-pro/edit`。log 没有路径、没有 sha。文件头与记录尺寸一致，不等于已经证明 `pro_01.jpg` 就是 task `715f185cc8b9475e85568d726d2f6531`。任务绑定：缺失。 |
| 请求 | 历史 prompt 在 log 的 4 条 `prompt` 里。当前 tip 请求：缺失。 |
| 运行时 commit | 当前运行时 commit：缺失。`pro_01.jpg` 落地 commit `96b149ffdfa6875cdebff6ed24425f5a271926d7`（2026-11-04 +0800）。金标落地 commit `206fca8fc33c302ff8ef347337e7063480d8affc`。都不是当前运行时 commit。 |
| 图像尺寸 | 金标 1600×1200；`pro_01.jpg` 1792×2400。目标 1536×2048。都不相等。未改写成目标比例。 |
| done | 当前 agent done：缺失。log 里的 provider `completed` 不是本轮 done。 |
| step | 缺失。log 没有步骤数。 |
| time | 缺失。log 没有耗时。有余额差 `spent_usd` 0.504，那不是 ≤3 分钟的完成证明。 |
| sha256 | 金标 `b1af2a31f9750eb711ac21ed5a0ae45a38ad853b3dacbab062f93e9cdacef77a`；`pro_01.jpg` `b53fa86597dee739712660ca5aa812727e888b5b7b02f542591f235ddee8475e`。都与 MANIFEST 一致。 |
| 未贴的混合包 | `docs/qa/posepro/compare_posepro.jpg` 3684×640，sha `7c98789b5ce1486804dfa169cdf78be3415c0e660c48b4eaa244d84c5b032497`。目视是参考图、多张全身和脸部裁切拼在一条里。整包未贴。`pro_02`–`pro_04` 仍是锁定单文件，未拼上板。金标 cover 目视是多格联系表，作为这一个锁定文件整张按原比例显示，没有拆格。 |

历史参考记录加 4 次调用在。当前同输入和当前运行时不在。尺寸也不等于本轮 1536×2048。

## game-art

| 字段 | 结果 |
|---|---|
| 输入/参考身份 | wash manifest 写 `source_path: <lovart-gold, not committed>`。输入文件不在仓库，身份缺失。 |
| 请求 | 历史请求在 `docs/design/643/wash-manifest.game-art.json` examples index 1（品牌锁定洗图，`aspect_ratio` auto，`resolution` 2K）。不是当前 #707 运行时请求。 |
| 运行时 commit | 缺失。文件落地 commit `876b573fad779846ecf78acd8dd53f3aa535b95a`（2026-11-04 +0800，#643 game-art example true-wash）不是当前运行时 commit。 |
| 图像尺寸 | 锁定 UI `643/wash/game-art/examples/01.webp` 文件头 1536×2736。目标 1024×1824。不相等。未改写成 9:16 目标框。 |
| done | 缺失 |
| step | 缺失 |
| time | 缺失 |
| sha256 | `05caf4132406b661e583a05b2e00b17fb003f540de74eb9ed8a7210a651f6615`，与 MANIFEST 一致 |
| 混合包未贴 | `docs/design/643/lr/batch3/game-art-ex01-lr.webp` 不在 tip_right。文件头 585×540。sha `372943fbbb4ddd5788e5a202d50f8dffd279afbc7f87e6509594c9741a134664`。落地 commit 与 wash 01 相同。目视内嵌字是 `ex01 L=gold R=wash`。左半是 UI，不是海报；但左半没有单独锁定文件。整包未贴。 |
| 海报未用 | `docs/design/640/78/gold/game-art/cover.webp` 1254×1254，sha `c4f63258f3ea65eb700e2055da9e91e3c8771c6f82761c4c93f21c390d5744c6`。`643/wash/game-art/cover.webp` 2048×2048，sha `733dc5ffe7356da5b305e72a9a78ce526c2c89155ff688bbfeb101ec9ebc4ef5`。 |
| 作废 Qwen | `704-lr/game-art/fixed-input-v1/RIGHT.png` 工作区不存在，未用。 |

旧 UI 在。当前运行时不在。像素不等于 1024×1824。

## linkedin-banner

| 字段 | 结果 |
|---|---|
| 输入/参考身份 | 没有单独的已核验输入文件。`design-LR.png` 目视内嵌字：左 `LEFT | Lovart Spec Reference`，右 `RIGHT | explicit Qwen candidate for preprocessing`。两张不同的图在一个文件里。同输入未核验。 |
| 请求 | 缺失。旁边没有 prompt 记录。NOTES 只说按已验收原字节拷入，不重新生成。 |
| 运行时 commit | 缺失。落地 commit `3dc069605e3f533bf2254c1ab98ab259083b996e`（2026-11-08 +0800，#704 SoT 锁定）不是生成运行时 commit。 |
| 图像尺寸 | `RIGHT.png` 1584×396，与文档目标像素一致（文件头已核验）。`design-LR.png` 3200×450，不等于 1584×396。都按原比例显示，没有把 design-LR 拉成 1584×396。 |
| 当前 UI canvas | 缺失 |
| step ≤ 10 | 缺失 |
| done ≤ 3 分钟 | 缺失 |
| done / step / time | 都缺失 |
| sha256 | RIGHT `52150b070e4c05cfd6d614fd2ae60793a90c61b30d1c6835ba4adccb42eb0c20`；design-LR `576ba4292afe42a2575a46ad339032f07f4fc2b470ac094340532af21d873df9`。都与 MANIFEST 一致。 |
| 板上声明 | 两张图都盖了 `explicit candidate image only, auto/UI chain unverified`。像素一致不是当前链路证明。 |
| 未用 | `805/reuse/linkedin-banner/featured.png`。三张作废 Qwen RIGHT（pose-fission、before-after、game-art）未用，工作区里也没有这些文件。 |

旧 RIGHT 是一张 1584×396。当前 UI 画布、≤10 步、≤3 分钟 done 都没有。

## 板文件

显示用的缩小只发生在对照板里，源文件没有改。

| 板 | sha256 |
|---|---|
| `before-after.png` | `a0320e4972ce0b53a950772e0a6601033261366524138dd53410e1ed75f25694` |
| `pose-fission.png` | `16fdc23a77b729701260cfafa7c34519bcace1faf99a97b9f6479f9583a84019` |
| `game-art.png` | `0461ea6f9513241fb49c6fb60a40d1e7988023f0bd9c71b540b5cba41afa0d8a` |
| `linkedin-banner.png` | `26887c9bb0fb0cabd1979e141402605d8ae77697f23d19563275c216610d8ba5` |
