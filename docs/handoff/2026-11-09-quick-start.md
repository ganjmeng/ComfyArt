# ComfyArt 交接快照（2026-11-09 08:24 Asia/Shanghai）

本文件是新会话的中文入口，由产品维护的唯一交接稿。相对路径：`docs/handoff/2026-11-09-quick-start.md`。仓库：<https://github.com/ganjmeng/ComfyArt>。不要再另写一份交接文档。

它只交接事实、验收边界和下一步。它不是新功能授权，不是预算授权，不是合并授权，不是部署授权，也不是供应商切换或付费生成授权。

快照时点：**2026-11-09 08:24 Asia/Shanghai**（08:24 群消息纠正 08:22 稿里「#848 仍在复验」的写法）。快照不是永远真相。新会话先查远端最新 head、issue 状态和证据正文，再决定动作。

## 来源怎么读

两类事实分开记。后文每节标题写明属于哪一类。

| 标记 | 含义 |
|---|---|
| 团队报告 | 2026-11-09 交接任务与 **08:24 群消息**。08:24 的 #848 限定范围 PASS、整卡 HOLD、#845、Replicate 直连已有 GIF 产物、Lovart 交验时刻，均来自该群消息。本文件作者没有复跑测试、没有重放账单、没有打开证据正文、没有复核供应商文档原文，也没有在 08:24 之后再次查询 GitHub。 |
| 只读核对 | 本会话在 **2026-11-09 08:23:20 Asia/Shanghai**（`2026-11-09T00:23:20Z`）用 `git fetch origin main`、`git rev-parse`、`gh pr view`、`gh issue view` 读取的 GitHub 元数据。未改任何已有分支，未跑产品测试，未启动应用。 |

本地 `main` 工作区在核对时不含 `#846` 索引和 `#848` 三态说明；那些文件在对应 PR 分支上。不要把本地 `main` 缺文件理解成证据不存在。

## 1. 项目入口

来源：本地 `main` 的 `README.md`、`package.json`，提交 `fe342cea4b34c095285e90edc4b13da77d89a315`，阅读时刻 2026-11-09 08:23 Asia/Shanghai。该提交与当时 `origin/main` 相同。提交说明时间为 2026-11-08 20:26:19 +0800，说明为 `#805 animated-poster hover video (wash first-frame remake) (#840)`。

- 仓库名保持 ComfyArt。产品对外名称是 Loomi。路由和 `COMFYART_*` 设置仍用 ComfyArt。
- 英文说明：<https://github.com/ganjmeng/ComfyArt/blob/main/README.md>
- 中文说明：<https://github.com/ganjmeng/ComfyArt/blob/main/README.zh.md>
- 功能文档站：<https://comfyart.org>
- 无 GPU 启动：`./scripts/start.sh`，页面在 `http://127.0.0.1:8188/comfyart/`。
- 已有 ComfyUI：放到 `ComfyUI/custom_nodes/`，安装 `requirements.txt` 后重启，打开同一路径。
- 前端脚本：`npm run dev`，`npm run typecheck`（`tsc --noEmit`），`npm run build`（`tsc --noEmit && vite build`）。
- 生成走 WaveSpeed。密钥只在服务端环境变量 `WAVESPEED_API_KEY`，不写入仓库。

本交接会话没有启动应用，没有部署。

## 2. 团队报告快照（时点 2026-11-09 08:24 Asia/Shanghai）

### 主线与明确不要重做的项

- 主线需求：[#825](https://github.com/ganjmeng/ComfyArt/issues/825) GPT Image 2.6 默认/Auto 与 GIF；[#826](https://github.com/ganjmeng/ComfyArt/issues/826) SVG；[#707](https://github.com/ganjmeng/ComfyArt/issues/707) / [#704](https://github.com/ganjmeng/ComfyArt/issues/704) 四技能当前真实链路仍是 **HOLD**。
- [#805](https://github.com/ganjmeng/ComfyArt/issues/805) hover 已收口。[#839](https://github.com/ganjmeng/ComfyArt/pull/839)、[#841](https://github.com/ganjmeng/ComfyArt/pull/841)、[#840](https://github.com/ganjmeng/ComfyArt/pull/840) 先前已合入。不要重做。

### #842 GPT Image 2.6 默认/Auto 与 GIF 确认

- PR：<https://github.com/ganjmeng/ComfyArt/pull/842>
- 团队所述 head：`69223e84763a9e02d24e87281da3e005d50a0842`
- 行为：默认/Auto 走到 2.6-flare；显式 2.5 保留；`quality` 缺席；专用尺寸路由保留。
- 确认界面把帧数夹到 2–16，每帧 20–2000ms。输入 99/5 显示为 16/20。确认、估价、请求一致。
- QA：67 passed / 0 skipped，`tsc` 通过；设计确认文案 mock PASS。
- 这不是真实供应商验收，也不是视觉改版验收。界面上的 7 积分来自 mock，不是实时报价。
- 静图转 GIF 的原验收标准未完成。拒绝保护通过，不能据此判该项完成。

### 唯一真实 WaveSpeed 编辑 GIF 请求

- 11 月 8 日 22:33，带参考图。HTTP 400，响应明确只接受 png/jpeg/webp。无任务 ID，无产物。未重试。时刻的时区以团队报告原文为准，本会话未改写成 UTC。
- 11 月 8 日 22:37，只读账单 HTTP 200，筛选为空。账单可能有延迟。费用记 **UNKNOWN**，不能记 0。
- [#825](https://github.com/ganjmeng/ComfyArt/issues/825) 原 $2 预算的余额未知。
- 不自动重试，不自动换供应商，不新增付费。
- 团队所述：OpenAI 官方文档支持 edits 参考图直接出 GIF；fal.ai 编辑 API 是备选，未实测，未选定。本会话未复核这两份供应商文档原文。
- Lovart 真正的 GIF 调用链未核实。不能写成必须经过视频。
- 静图转 GIF 的要求保留。

### #844 SVG

- PR：<https://github.com/ganjmeng/ComfyArt/pull/844>
- 旧测试提交：`40b446002da7fec41ecc992fa8af4cad1995470c`。范围只在云测试主机。
- 该提交覆盖的结论：危险 SVG 拒绝且无下载；真实网络文件隔离；隔离创建失败时不绘制、无残留。
- 3 秒 alarm 只在读输入阶段触发，不证明绘制超时。
- 待验：768MiB 绘制内存、CPU/输出上限、目标部署环境。
- 当前输入的完整 head：`b00d0b3a38932456f0f43f05ec3262f895117be6`。

### #848 集成候选

- PR：<https://github.com/ganjmeng/ComfyArt/pull/848>
- head：`eca055b522d2f10ca2b3993f9af1f75f338ff8bc`
- 合入 #842 与 #844 的内容，包含失败占位和透明棋盘显示。
- 下载须保留原 SVG 字节。棋盘只用于显示，不写入原件。
- **08:24 群消息：该 head 的独立 QA 已完成。** 限定范围 PASS：286 passed，`tsc` 通过。不要再写成仍在复验。
- **整卡 HOLD。** 真实绘制的 CPU、内存、输出超限，目标部署，静图转 GIF 的产品成功链路，以及实价，都未完成。
- 固定报告：<https://github.com/ganjmeng/ComfyArt/blob/532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7/docs/qa/2026-11-08-842-844/848-eca055b5/REPORT.md>
- 归档在 #846，证据 SHA：`532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7`
- 三态截图与说明：<https://github.com/ganjmeng/ComfyArt/blob/eca055b522d2f10ca2b3993f9af1f75f338ff8bc/docs/qa/integrate-842-844/README.md>

### #845 默认路由

- PR：<https://github.com/ganjmeng/ComfyArt/pull/845>
- 完整 SHA：`90073499fc82c49a3d9d16573c803e80bd34e2ad`
- 来源：08:24 群消息。Tech 报告负责人已授权默认路由变更。
- GIF 2.6 默认 Replicate。LLM 默认 DeepSeek 官方。已有显式配置保留。
- 16 项契约/CI 通过。未合并，未上线。完整产品点击验收未完成。
- 此前 Replicate 直连已经有 GIF 产物。不要写成从未成功。这不代表产品内链路通过，也不授权新增付费。
- WaveSpeed HTTP 400 仍是 11 月 8 日 22:33 那次独立失败，与这次 Replicate 直连产物不是同一件事。

### 独立视觉改版（Lovart 风格可复用组件）

- 2026-11-09 08:07，用户要求 Lovart 风格可复用组件，并指出按钮太简陋。
- 范围：先做确认弹窗、按钮、生成卡片/工具条、SVG 预览下载错误态。统一字体、间距、圆角、层级，以及 hover / focus / loading / disabled / error。优先复用已有组件。
- 约束：不照搬品牌；不改路由、计费、安全和下载逻辑。
- 设计首版目标：**08:30 北京时间**。设计工作流已 finished，云端 PR：<https://github.com/ganjmeng/ComfyArt/pull/849>。最新 SHA 与验收未核。
- 组件工程首版交验目标：**09:00 北京时间**。工程工作流已 finished，云端 PR：<https://github.com/ganjmeng/ComfyArt/pull/850>。最新 SHA 与验收未核。
- 两份都已有云端 PR。不要写成没有提交。#848 不是 Lovart 新版。
- 已有工程工作流：<https://cursor.com/agents/bc-7d87ed9e-6e60-53a0-93f3-848ddd9a862c>
- 已有设计工作流：<https://cursor.com/agents/bc-0b32ce40-9b33-564d-a357-0cb3c8e316c8>
- 设计追溯：<https://github.com/ganjmeng/ComfyArt/pull/842#issuecomment-6729072118> ，<https://github.com/ganjmeng/ComfyArt/pull/844#issuecomment-6729013403>
- 不要为同一事项再开一套并行开发。先核这两条工作流和对应分支。

### 历史图证与 QA 云端证据

- 历史图证 PR：<https://github.com/ganjmeng/ComfyArt/pull/843>，head `320949dc129da0ad47e86f0d1f356a0e4038e1de`。QA 只表示历史文档 PASS，不证明四技能当前链路。
- 四图：<https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6721987448>
- 新版 LinkedIn：<https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6722223485>
- QA 云端证据 PR：<https://github.com/ganjmeng/ComfyArt/pull/846>。08:22 任务稿里的 head 是 `d4be80122df597ff5a2b9b118c89b081f02a406c`。08:24 归档新证据的 SHA 是 `532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7`。索引路径：`docs/qa/2026-11-08-842-844/INDEX.md`（在该 PR 分支上）。
- 确认 mock：<https://github.com/ganjmeng/ComfyArt/pull/847>，head `3155770d58a02446f139031ec2286cbd30211233`，含确认 mock 截图和报告。

## 3. 只读核对（2026-11-09 08:23:20 Asia/Shanghai）

`origin/main` 与本地 `main` 同为 `fe342cea4b34c095285e90edc4b13da77d89a315`。

### PR

| PR | 状态 | 分支 | 核对到的 head | `updatedAt`（GitHub） | 与团队快照 |
|---|---|---|---|---|---|
| [#842](https://github.com/ganjmeng/ComfyArt/pull/842) | OPEN | `cursor/gpt-image-26-default-e355` | `69223e84763a9e02d24e87281da3e005d50a0842` | 2026-11-09T00:06:25Z | 一致 |
| [#844](https://github.com/ganjmeng/ComfyArt/pull/844) | OPEN | `cursor/svg-826-t2i-b424` | `b00d0b3a38932456f0f43f05ec3262f895117be6` | 2026-11-09T00:01:18Z | 前缀 `b00d0b3a` 一致 |
| [#848](https://github.com/ganjmeng/ComfyArt/pull/848) | OPEN | `cursor/integrate-842-844-b424` | `eca055b522d2f10ca2b3993f9af1f75f338ff8bc` | 2026-11-09T00:11:15Z | 一致 |
| [#843](https://github.com/ganjmeng/ComfyArt/pull/843) | OPEN | `cursor/707-historical-evidence-boards-27e6` | `320949dc129da0ad47e86f0d1f356a0e4038e1de` | 2026-11-08T13:40:47Z | 一致 |
| [#846](https://github.com/ganjmeng/ComfyArt/pull/846) | OPEN | `cursor/qa-evidence-2026-11-08-92ad` | `532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7` | 2026-11-09T00:22:00Z | **已前移** |
| [#847](https://github.com/ganjmeng/ComfyArt/pull/847) | OPEN | `cursor/qa-842-confirm-69223e84-1e94` | `3155770d58a02446f139031ec2286cbd30211233` | 2026-11-09T00:05:04Z | 一致 |

#846 的提交列表在核对时为：

1. `d4be80122df597ff5a2b9b118c89b081f02a406c`（2026-11-08T23:58:39Z）`docs(qa): archive 2026-11-08 evidence for 842, 843, 844, and 707`。这是 08:22 任务稿里的 head，仍在历史中。
2. `532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7`（2026-11-09T00:21:51Z，约 08:21 Asia/Shanghai）`docs(qa): add #848 integration evidence at eca055b5`。这是 08:23 核对时的 head，也是 08:24 群消息指定的 #846 新证据 SHA。

08:23 只读了提交说明，没有打开证据正文。08:24 群消息已把该 head 的独立 QA 定为限定范围 PASS，见第 2 节；以 08:24 为准，不要再写成仍在复验。#845 不在 08:23 的查询里，SHA 与结论只来自 08:24 群消息。

#844 提交列表含 `40b446002da7fec41ecc992fa8af4cad1995470c`（`fix(#826): render SVG only after netns and Landlock succeed`）。它不是当前 head。当前 head 是其后的 `b00d0b3a38932456f0f43f05ec3262f895117be6`。#848 历史里也能看到 `40b44600` 和 `69223e84`，当前 head `eca055b522d2f10ca2b3993f9af1f75f338ff8bc` 的提交说明是 `fix(#826): show SVG failure placeholder and a display-only checker`。这只说明提交说明与团队描述的占位/棋盘方向一致，不是新的验收签字。

### Issue 与已合入 PR

| 对象 | 核对到的状态 | 时间字段 | 说明 |
|---|---|---|---|
| [#825](https://github.com/ganjmeng/ComfyArt/issues/825) | OPEN | `updatedAt` 2026-11-08T11:59:40Z | 标题仍是先选项 + 直出 GIF，齐签后再切默认 |
| [#826](https://github.com/ganjmeng/ComfyArt/issues/826) | OPEN | `updatedAt` 2026-11-07T16:55:08Z | SVG t2i |
| [#707](https://github.com/ganjmeng/ComfyArt/issues/707) | OPEN | `updatedAt` 2026-11-08T13:41:41Z | 四技能版式/比例 |
| [#704](https://github.com/ganjmeng/ComfyArt/issues/704) | CLOSED | `updatedAt` 2026-11-08T11:08:44Z | GitHub 关闭状态不等于四技能真实链路验收。团队报告仍将当前真实链路标为 HOLD |
| [#805](https://github.com/ganjmeng/ComfyArt/issues/805) | CLOSED | `closedAt` 2026-11-08T12:26:21Z | 与「hover 已收口」的团队报告方向一致。本会话未重看视觉 |
| [#839](https://github.com/ganjmeng/ComfyArt/pull/839) | MERGED | `mergedAt` 2026-11-08T12:16:22Z | head `20f2c86042639266243e2963d39868a50e3037a5` |
| [#840](https://github.com/ganjmeng/ComfyArt/pull/840) | MERGED | `mergedAt` 2026-11-08T12:26:19Z | head `bc8685f9be31b58cd9cf3a3f2d5e3bfd7f4ee154` |
| [#841](https://github.com/ganjmeng/ComfyArt/pull/841) | MERGED | `mergedAt` 2026-11-08T12:23:27Z | head `f696e4d76e96cd3121b7e59d394b0aaa97b8c494` |

#805 不是 PR。`gh pr view 805` 在核对时返回无法解析为 Pull Request。对应实现在已合入的 #839/#840/#841。

## 4. 验收边界

下列边界同时采用团队报告和上一节的只读元数据。测试通过与否除上一节写明的 Git 对象外，均来自团队报告，本会话未复跑。

已记录、但还不是当前真实集成验收：

- #842 的 67 passed / 0 skipped、`tsc`、确认文案 mock PASS，只覆盖该分支上的确认夹紧和文案 mock。7 积分是 mock。真实供应商出图、实时报价、视觉改版都不在这项签字里。
- #847 是 #842 确认 mock 的云端截图和报告，head `3155770d58a02446f139031ec2286cbd30211233`。
- #844 的 `40b446002da7fec41ecc992fa8af4cad1995470c` 只说明云测试主机上的危险 SVG 拒绝、网络文件隔离、隔离失败不绘制。它不证明绘制超时，也不证明 768MiB、CPU/输出上限和目标部署环境。
- #843 的历史文档 PASS 只证明历史对照板文档。四技能当前真实链路仍按 HOLD 处理。
- #848 head `eca055b522d2f10ca2b3993f9af1f75f338ff8bc`：08:24 群消息确认独立 QA 已完成，限定范围 PASS（286 passed，`tsc` 通过）。这不等于整卡通过。
- #846 证据 SHA `532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7`。固定报告：<https://github.com/ganjmeng/ComfyArt/blob/532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7/docs/qa/2026-11-08-842-844/848-eca055b5/REPORT.md>
- #845 head `90073499fc82c49a3d9d16573c803e80bd34e2ad`：16 项契约/CI 通过。未合并，未上线，完整产品点击验收未完成。Replicate 直连已有 GIF 产物，不代表产品内链路通过。

整卡 HOLD，下列未完成：

- 真实绘制的 CPU、内存、输出超限，以及目标部署。
- 静图转 GIF 的产品成功链路和实价。WaveSpeed 编辑 GIF 那次独立失败仍是 11 月 8 日 22:33 的 HTTP 400，无任务 ID、无产物、未重试。费用 UNKNOWN。Replicate 直连已有 GIF 产物，不要写成从未成功。
- 四技能 #707/#704 的当前真实出图链路。
- Lovart 风格可复用组件的验收。设计已 finished，PR <https://github.com/ganjmeng/ComfyArt/pull/849>；工程已 finished，PR <https://github.com/ganjmeng/ComfyArt/pull/850>。最新 SHA 与验收未核。不要写成没有提交。

明确守住的行为：

- 下载 SVG 时保留原字节。透明棋盘只作为显示，不写回原件。
- 默认/Auto 与显式 2.5、`quality` 缺席、专用尺寸路由，以 #842 / #848 最新 head 的代码为准，先读再改。
- #845 已获授权的只是默认路由：GIF 2.6 默认 Replicate，LLM 默认 DeepSeek 官方，已有显式配置保留。未获进一步授权时：不合并，不部署，不自动改供应商，不发起新的付费生成，不把费用 UNKNOWN 写成 0，不自动重试那次 WaveSpeed 请求。

## 5. 已完成、待做、阻塞、下一步

### 已完成（按上面的边界理解）

- hover：#805 已关闭，#839/#840/#841 已合入 `main`。不要重做。
- #842、#844、#848、#843、#846、#847 在 08:23 核对时均为 OPEN，head 见第 3 节。#845 的 SHA 来自 08:24 群消息，当时未再查询。
- #848 `eca055b522d2f10ca2b3993f9af1f75f338ff8bc` 独立 QA 已完成：限定范围 286 passed，`tsc` 通过。整卡仍 HOLD。
- GIF 确认界面的夹紧和 mock 文案，有 #842/#847 的团队 QA 记录。Replicate 直连已有 GIF 产物。
- SVG 危险输入与隔离的云测试主机记录，停在 `40b44600` 所覆盖的范围。
- 历史四图和新版 LinkedIn 评论已有永久链接，见第 2 节。

### 待做

- #848 限定范围 QA 已完成，不要重开复验。整卡剩余项：真实绘制 CPU/内存/输出超限、目标部署、静图转 GIF 产品成功链路、实价。报告：<https://github.com/ganjmeng/ComfyArt/blob/532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7/docs/qa/2026-11-08-842-844/848-eca055b5/REPORT.md>
- #845 未合并、未上线，完整产品点击验收未完成。不授权新增付费。
- 设计 PR <https://github.com/ganjmeng/ComfyArt/pull/849>、工程 PR <https://github.com/ganjmeng/ComfyArt/pull/850> 已在云端。先读这两份最新 head。最新 SHA 与验收未核，不要重开，不要写成没有提交。
- 静图转 GIF 的产品内成功链路仍待完成。在新的明确授权出现之前，不做付费重试，不换供应商。
- 四技能真实链路保持 HOLD，直到有当前链路证据。#843 不能充当该证据。
- 代码和文档按小批次提交并推送。每批给出 PR 或文件链接、完整 SHA、测试状态。秘密不入库；日志和文档里的密钥打码。

### 阻塞

- 整卡 HOLD：真实绘制 CPU/内存/输出超限、目标部署、静图转 GIF 产品成功链路、实价。
- GIF：WaveSpeed 11 月 8 日 22:33 编辑请求仍是 HTTP 400。费用 UNKNOWN。$2 预算余额未知。Replicate 直连已有产物，产品内链路未通过。OpenAI 文档路径和 fal.ai 备选都还不是已选定、已实测的实现。Lovart 是否必须经过视频，尚未核实。
- 视觉改版：设计 #849、工程 #850 已有云端 PR，工作流均已 finished。最新 SHA 与验收未核。#848 不是 Lovart 新版。

### 下一步

1. 新会话先 `git fetch`，重读 #842/#844/#845/#848/#843/#846/#847 和两条已有 agent 的最新进度。沿用本文件，不要再开一份交接稿。
2. 用最新 head 更新「已完成 / 待做 / 阻塞 / 下一步」，并标明每一项的证据链接和完整 SHA。
3. 集成整卡剩余项与视觉两条线并行，接已有分支和已有 agent。#848 限定范围 QA 不重开。
4. 产品改动仍走小批次推送。本交接文件本身不授权改产品代码，也不授权新增付费。

## 6. 新会话提示词

把下面整段复制到新会话。

```text
用中文接续 ComfyArt（仓库 https://github.com/ganjmeng/ComfyArt ，产品名 Loomi）。只维护这一份交接稿：docs/handoff/2026-11-09-quick-start.md（入口：https://github.com/ganjmeng/ComfyArt/blob/cursor/handoff-2026-11-09-quick-start-7a29/docs/handoff/2026-11-09-quick-start.md ，若该分支已更新则改读该文件最新提交）。不要再生成另一份交接文档。先读本文，再只读核对相关 PR/issue 的远端最新 head、状态和证据正文。快照时点是 2026-11-09 08:24 Asia/Shanghai。08:23:20 的只读复核只覆盖当时已查对象。快照不是永远真相，以你当时的远端为准。

08:24 群消息（未在 08:24 之后再次查询）：#848 eca055b522d2f10ca2b3993f9af1f75f338ff8bc 独立 QA 已完成，限定范围 PASS，286 passed，tsc 通过。不要写成仍在复验。整卡 HOLD：真实绘制 CPU/内存/输出超限、目标部署、静图转 GIF 产品成功链路和实价都未完成。固定报告 https://github.com/ganjmeng/ComfyArt/blob/532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7/docs/qa/2026-11-08-842-844/848-eca055b5/REPORT.md ，归档在 #846 证据 SHA 532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7。#844 完整 head b00d0b3a38932456f0f43f05ec3262f895117be6。#845 https://github.com/ganjmeng/ComfyArt/pull/845 完整 SHA 90073499fc82c49a3d9d16573c803e80bd34e2ad：Tech 报告负责人已授权默认路由变更，GIF 2.6 默认 Replicate，LLM 默认 DeepSeek 官方，已有显式配置保留；16 项契约/CI 通过；未合并、未上线，完整产品点击验收未完成。此前 Replicate 直连已有 GIF 产物，不要写从未成功；这不代表产品内链路通过，也不授权新增付费。WaveSpeed HTTP 400 仍是 11 月 8 日 22:33 那次独立失败。

08:23 核对时与当时快照一致的 head：#842 69223e84763a9e02d24e87281da3e005d50a0842、#843 320949dc129da0ad47e86f0d1f356a0e4038e1de、#847 3155770d58a02446f139031ec2286cbd30211233。#846 当时 head 已是 532a1aa2cb7bd3829946bd19f6a1c5f0bbc179d7（更早的 d4be80122df597ff5a2b9b118c89b081f02a406c 仍在历史中）。这些都要重新查询。

先报告已完成、待做、阻塞、下一步。每一项写来源、时间和完整 SHA 或永久链接。不要把历史图、mock、单分支签字当成整卡验收。#843 只证明历史文档。#842 的 67 passed/0 skipped、tsc 和确认文案 mock 不是真实供应商验收，也不是视觉改版验收；7 积分来自 mock。#848 限定范围 PASS 不是整卡 PASS。#704 即使 GitHub 为 CLOSED，四技能当前真实链路仍按 HOLD。#707/#704 当前真实链路未完成。

并行推进已有工作，不要重开、不要重烧，也不要重开 #848 限定范围 QA：
- 集成整卡剩余项：https://github.com/ganjmeng/ComfyArt/pull/848 与工程工作流 https://cursor.com/agents/bc-7d87ed9e-6e60-53a0-93f3-848ddd9a862c 。下载须保留原 SVG 字节，棋盘不写入原件。静图转 GIF 的产品成功链路仍保留。
- 默认路由：https://github.com/ganjmeng/ComfyArt/pull/845 。未授权则不合并、不上线、不新增付费。
- 视觉：设计已 finished，PR https://github.com/ganjmeng/ComfyArt/pull/849 ，工作流 https://cursor.com/agents/bc-0b32ce40-9b33-564d-a357-0cb3c8e316c8 。工程已 finished，PR https://github.com/ganjmeng/ComfyArt/pull/850 ，工作流 https://cursor.com/agents/bc-7d87ed9e-6e60-53a0-93f3-848ddd9a862c 。两份都已有云端 PR，不要写成没有提交。最新 SHA 与验收未核，先读最新 head，不要重开。设计追溯 https://github.com/ganjmeng/ComfyArt/pull/842#issuecomment-6729072118 和 https://github.com/ganjmeng/ComfyArt/pull/844#issuecomment-6729013403 。不照搬 Lovart 品牌。不改路由、计费、安全和下载逻辑。#848 不是 Lovart 新版。

不要重做已收口的 #805 hover，以及已合入的 #839、#840、#841。不要改其他现有分支的历史。

代码和文档素材按小批次提交并推送云端。每批给出可点击链接、完整提交 SHA 和测试状态。排除密钥并脱敏。未获明确授权：不合并，不部署，不自动更换供应商，不发起任何付费生成，不自动重试。2026-11-08 22:33 那次带参考图的 WaveSpeed 编辑 GIF 请求返回 HTTP 400（只接受 png/jpeg/webp），无任务 ID，无产物，未重试；22:37 只读账单筛选为空但可能延迟，费用记 UNKNOWN，不能记 0。#825 原 $2 预算余额未知。OpenAI 官方文档所述 edits 直接 GIF、fal.ai 编辑 API 都还不是已实测已选定方案。Lovart 真正 GIF 调用链未核实，不能写成必经视频。

docs/handoff/2026-11-09-quick-start.md 只是交接，不是新的功能授权或预算授权。
```
