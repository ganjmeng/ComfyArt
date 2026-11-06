# Lovart 金标清单（L/R 对照，下一批卡用）

口径：金标只认 **lovart.ai 国际站**（不用 lovart.art）；L/R = **左 Lovart 金标｜右我们 main 3c71d5f**。
本机网络对 www.lovart.ai 做 SNI 阻断（见 `lovart-access.md`），本轮**无法新抓**；金标全部来自仓库既有、按 **pinned sha** 引用。
右图本轮用 QA mock 环境（main `3c71d5f` 真实 dist，:8392，$0）现截。

pinned raw 链接格式：`https://raw.githubusercontent.com/ganjmeng/ComfyArt/<sha>/<path>`

## 一、金标来源登记（4 组，全部可按 sha 引用）

### A. `docs/qa/lovart-ui/` @ sha `821762885248abef007feb308e09d5132ade7fe1` —— **#710 主金标（唯一全状态 Lovart 原图）**
> 注意：该目录**不在当前 main**（main 上 404），只能按此 sha 引用，勿用 main 路径。

| 文件 | 尺寸 | 内容 | #710 状态 |
|---|---|---|---|
| `skill_dialog_default.png` | 1920×1072 | Skills 页 + Lovart 技能弹框默认态（左 Examples 轮播 / 右 Start Creating：Upload Files 虚线上传框 / Additional Details / Start making；浅色，EN） | 状态 1 默认 |
| `skill_dialog_filled_with_upload.png` | 1920×1072 | 同上 + 已上传缩略图 + Additional Details 已填（中文），示例轮播正常 | 状态 2 已上传+填写 |
| `run_loading_outputting.png` | 1920×1072 | 对话页：用户消息带技能 chip + `image-1` chip，下方 `Outputting…` 状态行（无正文） | 状态 3 运行中 |
| `followup_question_card.png` | 1920×1072 | 全页：技能 chip 用户消息 + `Skill ready` 状态行 + Question 卡（4 张方案逐段分行、A Start generating / B Generate another set / C Other、Skip + Submit 置灰） | 状态 4 追问卡未选 |
| `followup_card_selected.png` | 760×280 | **追问卡已选态裁图**（A 选中高亮）—— #710 评论 11-04 曾写「05 选中态仍待补」，此文件即后续补齐的 05 | 状态 5 追问卡已选 |
| `followup_card_submitted.png` | 1920×1072 | 提交后：卡片折叠为灰色用户气泡（4 条规划 + 问题句 + 所选答案），右下复制图标，选项/高亮隐藏 | 状态 6 提交后 |
| `lovart_pose_sheet.jpg` | 3920×900 | 4 姿态参考拼板（补充素材） | 辅助 |

### B. `review-assets` 分支 @ sha `f2dfd0671fb7b1789bb70ea5c645321ca1c38bd4`（左 Lovart / 对照素材）
| 路径 | 尺寸 | 用途 |
|---|---|---|
| `790/left/lovart-dialog-en-top.png` | 1200×820 | Lovart “Logo Material Explorer” 弹框默认态（EN 浅色，整洁单弹框）→ #790 logo-material 对照 |
| `792/left/lovart-dialog-left.png` / `-more.png` | 1200×820 | Lovart “Mobile APP Visual Design” 弹框（默认 / 更多示例）→ #792 mobile-ui 对照 |
| `794/left/lovart-dialog-left.png` / `-more.png` | 1200×820 | Lovart web-product 类弹框 → #794 对照 |
| `687/lovart-skill-detail/r1/lovart-01-grid.png` | 1280×717 | Lovart Skills 页网格（Phase1 卡片逐卡复核基准） |
| `687/lovart-skill-detail/r1/lovart-02-packaging-modal.png` | 1280×717 | Lovart packaging 弹框（右侧逐张字段基准） |
| `687/lovart-skill-detail/r1/lovart-03-motion-poster-modal.png` | 1280×717 | **Lovart 动态海报弹框**（`当前模板` 行 + 模板卡片 + 静态原稿/动态要求/视觉呈现方式 字段）→ #687 motion 对照 |
| `687/lovart-skill-detail/r1/lovart-04-cover-design-director-modal.png` | 1280×717 | Lovart cover design director 弹框 |
| `337/lovart-live/00..07-*.png` | ~719×440 | Lovart 追问卡交互 8 态（空 / Submit 置灰 / 选 B / 输入 other 取消 B / only-other 可提交 / 点 A 保留文字 / 点 A）— 早期 #337 金标，可与 A 组 followup 图互证 |
| `430/lovart/`（38 张） | 多种 | Arti / memory / onboarding / chat streaming 实测金标（430 系列） |
| `783/qa/d54b3eb1-r2/04-lovart-home-authed-masked.jpg` | 1280×? | Lovart **登录态**首页（已打码），#783 用 |
| `783/qa/d54b3eb1-r2/03-lovart-LEFT-blocker-no-frozen-ref.jpg` | ? | #783 LEFT 阻塞证据（同输入拿不到冻结参考图） |
| `lovart-raw/2026-11-05/INDEX.md`（54.9KB）+ `anim/measurements.md` | 文本 | Lovart 实测参数/动画测量账本（帧序列 masked PNG），设计数值可查 |
| `lovart-raw/2026-11-05/anim/frames/*.masked.png`、`anim/*.mp4` | 1280×1072 等 | 堆叠卡片展开动画帧（已打码），motion 类参考 |

### C. main `docs/qa/687-fields/` @ sha `3c71d5f055bbd6998a63e6928c165d3afa11918a`（#687 字段 L/R，现役）
- `lr-motion-lovart-vs-ours-en-light.png`（554KB）—— **motion 弹框字段 L/R（左 Lovart｜右我们）**
- `lr-12-right-pane-lovart-vs-ours-en-light.png`（242KB）—— 右栏逐张字段 L/R
- `skill-fields-<skill>-{en-dark,zh-light}.png` —— 12 个技能的弹框字段实拍（banner/brand/character/interior/logo-material/marketing-campaign/meta-ads/mobile-ui/motion/packaging/poster/social/web-product）
- `skill-fields-motion-after-start-zh-light.png`、`skill-fields-motion-real-mp4-upload-en-light.png` —— motion 运行/上传后状态
- main `docs/design/687/manifests/wash-manifest.phase1-4.json` / `social-retry.json` —— 洗图 manifest

### D. `docs/design/ui-parity/` @ sha `36ddc5378dbf47072724095b0f311fb1cd507eb6` —— #710 旧 L/R 六连（左 Lovart｜右 Loomi `5b8eb510`）
`01-dialog-default / 02-dialog-filled-upload / 03-running / 04-followup-unselected / 05-followup-selected / 06-followup-submitted .png`（各 3071×950 双栏）＋ `loomi-computed.json`（旧右栏 computed，仅参考，sha 已旧）。
用途：#710 初始差异清单来源；右栏 sha 旧，不能直接当本轮验收图。

## 二、#710 逐状态：金标 / 我方可对照图 / 缺什么

| # | 状态 | Lovart 金标（pinned） | 我们右图（main 3c71d5f，本轮现截） | L/R 文件 | 缺 / HOLD |
|---|---|---|---|---|---|
| 1 | 弹框默认 | A `skill_dialog_default.png` @82176288 | `shots/rh-pose-fission-dialog-default-en-light.png`（Same-Scene Pose Fission，en-light 1440×1000） | `shots/lr-710-skill-dialog-default-en-light.png` ✅ | — |
| 2 | 已上传+填写 | A `skill_dialog_filled_with_upload.png` @82176288 | `shots/rh-pose-fission-dialog-filled*-en-light.png` | `shots/lr-710-skill-dialog-filled-en-light.png` ✅ | 我方「补充描述」是单行 input（渲染与 Lovart 多行不一致，#710 差异 5 已列「已一致」待复核） |
| 3 | 运行中 | A `run_loading_outputting.png` @82176288 | HOLD：需 fake provider/`RV_MODE=timeout`（已请 QA 补右图） | 待拼 | 右图待 QA |
| 4 | 追问卡未选 | A `followup_question_card.png` @82176288（另有 B `337/lovart-live/*`） | HOLD：需 agent ask block（QA fake provider） | 待拼 | 右图待 QA |
| 5 | 追问卡已选 | A `followup_card_selected.png` @82176288（760×280） | 同上 | 待拼 | 右图待 QA |
| 6 | 提交后 | A `followup_card_submitted.png` @82176288 | 同上 | 待拼 | 右图待 QA |
| — | **computed 精确值** | 无（需登录态 DOM 实测） | — | — | **HOLD**：#710 原话「760px/16px 为像素估算，待 computed + DPR 核实后再交开发」。需补：弹框容器 w/h/pad/r、标题 16/600、Start making 高/r/bg、Additional Details 高/r、追问卡宽/pad/r/字号/label 12px α、Submit/Skip 28 高、用户气泡 chip 与 `image-1` chip 尺寸；DPR=2 复核。**下轮网络恢复补**（脚本已交付 `capture-lovart.mjs`，可直接输出 computed.json） |

## 三、#687 motion（剩余 HOLD = NEED-SHOT）

- **字段/弹框对照已有**：C 组 `lr-motion-lovart-vs-ours-en-light.png`（main 3c71d5f 现役）；B 组 `687/.../lovart-03-motion-poster-modal.png`；`docs/qa/687-fields/skill-fields-motion-*.png`。
- **本轮补的 L/R**：`shots/lr-687-motion-skill-dialog-en-light.png`（左 Lovart 动态海报弹框｜右我们 Animated Poster Generator，main 3c71d5f）。
- **仍缺（NEED-SHOT）**：motion 的 **cover / featured 媒体金标**（#687 盘点 11-06 原话「本盘点未新补封面/精选对照，仍待有图再定」）。审核基准不稳，本轮**不新开洗图**；等 lovart.ai 通道恢复后按 `capture-lovart.mjs` 的 followup/running 流程补 Lovart 动态海报卡 cover/精选整页截图（含 hover 动效帧）。
- 参考系：B 组 `lovart-raw/2026-11-05/anim/` 有堆叠展开动画帧与 measurements，可先作为 m otion 交互数值参考（非本卡 cover 金标）。

## 四、#725（旧链接恢复参考图 + 刷新保留草稿）

- **仓库里没有对应 Lovart 金标**（已全树检索 review-assets + main docs：无 725 目录/old-link 截图）。本卡 AC 是行为断言（composer N refs / canvas 0 / 刷新两次 refs+draft 保留 / mutation 能挂测试），可不依赖 Lovart 视觉金标。
- 现状（main 3c71d5f）：#723 已合 `b47b667136`（hidden skill 深链 refs），#725 要扩到 **visible skill**。我方「右图」= 现状基线：旧链接打开 → composer 参考图恢复情况 + 刷新前后草稿；需 `?ref=` 深链实测（handoff.ts `KEYS = ['ask','mode','ref','skill','tool','createSkill','editSkill','preset']`）。
- 本轮计划：用 mock 环境截 `?skill=<id>&ref=<url>` 的 composer/canvas 现状 → 作 #725 右图基线；**若 UI 复现需真实旧会话数据，标 HOLD 等 QA/fake data**。
- 产出（若成立）：`shots/lr-725-oldlink-restore-*.png`（左：无 Lovart 金标 → 用「AC 对照表」作左栏，或纯右图基线 + 断言清单）。

## 五、本轮产出文件（/tmp/team/design/shots/）

```
lr-710-skill-dialog-default-en-light.png      2250×908  L=Lovart@82176288  R=main 3c71d5f
lr-710-skill-dialog-filled-en-light.png       2250×908  L=Lovart@82176288  R=main 3c71d5f
lr-687-motion-skill-dialog-en-light.png       2250×908  L=Lovart review-assets@f2dfd06  R=main 3c71d5f
rh-pose-fission-dialog-default-en-light.png   1440×1000 右图原图（弹框默认）
rh-pose-fission-dialog-filled3-en-light.png   1440×1000 右图原图（上传+补充描述）
rh-motion-dialog-default-en-light.png         1440×1000 右图原图（动态海报弹框）
profile-session-lovart-ai-error.png           lovart.ai 不可达证据（登录 profile 副本仍 ERR_TIMED_OUT）
profile-session-lovart-art.png                www.lovart.art 可达（NON-GOLD 参考）
thirdparty-thumio-lovart-ai.png               www.lovart.ai 第三方匿名渲染（NON-GOLD，仅可达性证据）
```
上传 review-assets 后的 pinned URL 见本轮给 Lead 的消息（目录 `710/design/3c71d5f/`、`687/design/3c71d5f/`）。

## 六、网络恢复后的补抓配方（一次跑完）

```bash
# 匿名（默认，不碰登录态）
NODE_PATH=/Users/jingmeng.gan/Documents/open-lovart/node_modules \
node /tmp/team/design/capture-lovart.mjs --out /tmp/team/design/lovart-capture

# 有登录态：把 Chrome Profile 复制到 /tmp 再跑（绝不指向原 profile）
cp -R "$HOME/Library/Application Support/Google/Chrome/Profile 1/." /tmp/lovart-profile/Default/
node /tmp/team/design/capture-lovart.mjs --out /tmp/team/design/lovart-capture --authed-profile /tmp/lovart-profile

# 状态清单 / computed 都在 --states（默认 dialog-default,dialog-filled,computed）
--states dialog-default,dialog-filled,running,followup-unselected,followup-selected,followup-submitted,computed
```
输出：`shots/<state>.png` + `computed.json`（DPR、弹框/标题/按钮/Additional Details/追问卡/Submit/Skip 的 rect+font+radius+bg+padding）+ `capture-result.json`（每步失败原因，可直接贴 issue 当 HOLD 证据）。
补抓优先级：① #710 computed（最缺）；② #687 motion cover/featured 整页；③ #725 旧链接 Lovart 行为（如可能）；④ 需要新状态/多语言/深色再补。

## 七、缺口汇总（交给 Lead/PM 排期）

| 卡 | 金标状态 | 缺口 | 解除条件 |
|---|---|---|---|
| #710 | ✅ 六态齐（A 组） | computed 精确值；状态 3-6 右图（QA 补） | 网络通道 / QA 右图 |
| #687 motion | 字段 L/R 有；L/R 本轮补弹框 | cover/featured 媒体金标 NEED-SHOT | 网络通道（Next: `capture-lovart.mjs`） |
| #725 | 无 Lovart 视觉金标（非必需） | 现状基线右图（composer/canvas/刷新） | QA fake data 或 UI 可复现 |
| #783 | LEFT 已有（B 组，authed masked） | 同输入冻结参考图 | 网络通道 / 上游同步 |

---

## 八、固定 sha 链接（review-assets）

L/R 拼接图（sha `10bcbbd255a60bf9b9452fcf463923fb17b14187`）：
- #710 弹框默认：https://raw.githubusercontent.com/ganjmeng/ComfyArt/10bcbbd255a60bf9b9452fcf463923fb17b14187/710/design/3c71d5f/lr-710-skill-dialog-default-en-light.png
- #710 弹框已上传+填写：https://raw.githubusercontent.com/ganjmeng/ComfyArt/10bcbbd255a60bf9b9452fcf463923fb17b14187/710/design/3c71d5f/lr-710-skill-dialog-filled-en-light.png
- #687 motion 弹框（sha `98c1e190bcd5ba7ea6bfe79c5966213a8458f93e`）：https://raw.githubusercontent.com/ganjmeng/ComfyArt/98c1e190bcd5ba7ea6bfe79c5966213a8458f93e/687/design/3c71d5f/lr-687-motion-skill-dialog-en-light.png
右图原图（同上 sha）：`right-710-dialog-default-en-light.png` / `right-710-dialog-filled-en-light.png` / `right-687-motion-dialog-default-en-light.png`。
文档：`lovart-access.md` / `lr-inventory.md` / `capture-lovart.mjs`（sha `10bcbbd255a60bf9b9452fcf463923fb17b14187`，目录 `710/design/3c71d5f/`）。

**#725 右图现状**：本轮 probe（main 3c71d5f mock env）显示：`?skill=pose-fission&ref=<http 图片>` 直接打开 → composer 无参考图缩略图、无 skill chip 渲染证据（canvas 0）；home 的 prompt box 刷新后草稿不保留（`.ca-composer__input` 在 home 不存在，需先建项目/进 chat）。→ #725 右图需 QA fake data 或真实旧会话，标 HOLD；不编造。

---

## 九、补充：状态 3-6 的 L/R 已补齐（QA 右图到齐，2026-11-07 03:17）

QA 用仓库自带 `tests/js/ask763` harness 渲染**真实 `ChatMessage` 组件 + 真实 CSS**（chat 数据 mock，$0，与 #710 原右图「本机 Playwright, chat 接口 mock」同口径）；截图 808×912 / 808×1200 @2x、zh-light。脚本：`/tmp/team/qa/lr-right-shots.py`、`/tmp/team/qa/lr-running-harness.py`。
本轮已拼 4 张 L/R（左 Lovart 金标 @82176288｜右 Loomi 组件级渲染，main `3c71d5f`），review-assets sha `b2dea747fe57c8af3e3f3e2b21d6fb922dece847`：

| # | 状态 | L/R 图（pinned） | 右图原图 |
|---|---|---|---|
| 3 | 运行中（Outputting…） | https://raw.githubusercontent.com/ganjmeng/ComfyArt/b2dea747fe57c8af3e3f3e2b21d6fb922dece847/710/design/3c71d5f/lr-710-running-zh-light.png | .../right-710-running-zh-light.png |
| 4 | 追问卡未选 | https://raw.githubusercontent.com/ganjmeng/ComfyArt/b2dea747fe57c8af3e3f3e2b21d6fb922dece847/710/design/3c71d5f/lr-710-followup-unselected-zh-light.png | .../right-710-question-unselected-zh-light.png |
| 5 | 追问卡已选 A | https://raw.githubusercontent.com/ganjmeng/ComfyArt/b2dea747fe57c8af3e3f3e2b21d6fb922dece847/710/design/3c71d5f/lr-710-followup-selected-zh-light.png | .../right-710-question-selected-zh-light.png |
| 6 | 提交后折叠气泡 | https://raw.githubusercontent.com/ganjmeng/ComfyArt/b2dea747fe57c8af3e3f3e2b21d6fb922dece847/710/design/3c71d5f/lr-710-followup-submitted-zh-light.png | .../right-710-question-submitted-zh-light.png |

### 重要口径 / 限制（写 PR 时必须带上）
1. **右侧是组件级 mock 渲染**（真实 ChatMessage + CSS；chat/agent 数据 mock），不是 :8392 真 app 的点击路径 —— mock server 只 mock WaveSpeed、不 mock agent provider，真点「开始制作」需要 fullstack 起 agent provider mock。若要「真 app 路径」截图需另派 fullstack。
2. **内容/语言不同**：Lovart 金标是英文 4 张方案（电商同场景换人），QA 右图是中文 logo 风格问题（ask763 harness 固定场景）。本轮 L/R 只能证明**结构/状态一致**（卡片结构、A/B/C 字母单选、Skip/Submit、提交后折叠气泡），不能证明 #710 差异 1「逐张方案分行」的正文内容 —— 该项仍以 **A 组 `followup_question_card.png` 金标 + #710 AC 文字规格**为准，由全栈按规格实现、QA 断言。
3. **状态 5 金标存疑**：#710 评论 11-04 曾写「05 选中态仍待补」；现 `followup_card_selected.png` 是 **760×280 裁图**，内容显示问题句 + `A: Start generating` + 右下复制图标，语义更像「已选答案/提交后气泡」的一部分，与「选中高亮」未必同态。本轮按仓库文件标签使用，**下轮网络恢复后补一张真·选中态整页金标**（或由 QA 明确该文件语义）。
4. 运行中右图未含「停止按钮」证据（QA harness 未渲染 composer）；#710 差异 4「状态行 + 停止入口」需真 app 路径补图。

补图后 #710 只剩 **computed 精确值** 一项硬 HOLD（需登录态 DOM）；其余六态金标+L/R 已齐。
