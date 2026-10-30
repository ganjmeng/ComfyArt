# #410 Agent 循环全面审计（#409 合并后）

基准：`docs/design/410/78/reference/` 下的 CN 对照图 + `docs/design` 既有实测图 + 10-27 产品定稿的 Agent 逻辑优先级表。  
文中一律称对照方为 **「reference」**（不出现品牌名）。  
方法：mock 优先（`$0`）；真实 WaveSpeed 调用走已批 **$5** 预算，跑前报 EL，本 PR **未花**。

截图：`docs/design/410/78/after/<scene>-{zh,en}-{light,dark}.png`（harness = 真实 `AssistantBlocks` + tip CSS，非整窗 Electron）。

---

## A. 步骤状态（图标 / 竖线 / 顺序 / 进行中→完成）

| 项目 | 「reference」怎么做 | 我们怎么做 | 截图 | 对齐 / 差距 |
|---|---|---|---|---|
| **思考 live** `thought` | 脑图标 + 「思考中…」/ Thinking…，label 带 active 动效 | `SHOW_THINKING_ROW=true`；`chatMessage.thinking`；`ca-process__label--active` | `thought-live-*` · `no-tool-live-*` | **对齐** |
| **思考 done** `thought` | 脑图标 + 「思考完成」/ Thought，可点开看正文 | 同；单步走 #325 `Thought`（无竖线），多步挂 rail | `thought-done-*` · `no-tool-done-*` | **对齐**（单步无竖线是既定 #325） |
| **输出中** `outputting` | 回复流式时状态卡 / 行 | rail 末行 `输出中…`；纯文本流式时 `AgentPanel` 也用同文案 | `outputting-live-*` | **对齐** |
| **技能加载** `skill` | ScrollText 图标；「技能加载完成」/ Skill ready | Lucide `scrollText` stroke 2；live/done 同文案 | `skill-live-*` · `skill-done-*` | **对齐** |
| **技能文件读取** `skill_file_read` | 文件检索图标；live「正在读取…」→ done「已读」 | `fileSearch`；`skillFileReadLive` / `skillFileRead` | `skill-file-*` | **对齐** |
| **联网搜索 live** `search` | Globe + 「正在搜索网页」+ 底部 status 卡 | 同文案；status 卡在 rail 外 | `search-live-*` · `chain-live-*` | **对齐**（对照 `reference/process-timeline-liked.png`） |
| **联网搜索 done** `search_pages` | 页数行 + 「联网搜索结果」卡 | `{N} 个网页` / `{N} web pages` + favicon + 结果卡 | `search-done-*` · `chain-done-*` | **对齐**（#437） |
| **图片生成** `image` | 生成中文案 → 完成后模型名行 | live `正在生成图片…`；done 用 `model` 名（无「已生成图片」） | `image-live-*` · `image-done-*` | **对齐**（#437） |
| **视频生成** `video` | 同上 | live `正在生成视频…`；done 模型名 | `video-*` | **对齐** |
| **写代码族** `code` / `code_generated` / `code_updated` / `design_validated` / `preview_artifact` | 代码步骤链 | 自动补 `Writing code` 头行 + 子行；Lucide SquareCode / FileCode / FilePenLine / ListChecks / Sparkles | `code-*` | **对齐**（#348） |
| **记忆已读取** `memory_retrieved` | 记忆头标；更新既有条目时出现 | 有 `updated_ids` 时插在 `memory_updated` 前；不可点 | `memory-done-*` | **对齐**（#437/#430） |
| **记忆更新中** `memory_updating` | live 无 › | tool_use add 且尚未落 `memory_updated` 时 | `memory-live-*` | **对齐** |
| **记忆已更新** `memory_updated` | 「记忆已更新 ›」可点开弹窗；竖线不断 | Lucide/`memoryHead`；`›`；点开 MemoryDialog；同 rail | `memory-done-*` · 对照 `reference/memory-updated-row-in-chat-light.png` | **对齐**（#409/#414 后；深度入口纠偏见 #430） |
| **通用工具** `tool` | 画布/其他工具上轨 | `get_canvas` 等走 `tool`，失败读「工具名 · 失败」 | `tool-*` | **对齐**（#420） |
| **没调工具的轮次** | 只有思考 → 回复 | 单 `thinking` → `text`；走 #325 Thought | `no-tool-*` | **对齐**（设计单列，见 issue 评论） |
| **竖线 / 间距 / 字号色** | 1px spine、等距、muted、active 仅 live | `--ca-rail`、`--ca-process-row-gap`、14/20、`.55` ink（#441 实测） | `chain-*` · `memory-done-*` | **对齐**（视觉签字仍请设计对 after 与 reference 并排） |

---

## B. Arti 技能沉淀与记忆（真写入 / 下一轮可读）

| 项目 | 「reference」怎么做 | 我们怎么做 | 截图 / 证据 | 对齐 / 差距 |
|---|---|---|---|---|
| **记忆工具写入** | 对话内写记忆并出「记忆已更新」行 | `#413` `memory` tool → `memory_updated` block；`tests/test_memory_tool_413.py` | `memory-done-*` | **对齐** |
| **记忆兜底写入** | 模型未调 memory 时系统可补写 | `src/proactive.ts` `learnMemory`；**默认关**（`proactive-memory: false`，#424）；有写入才扣配额 | — | **行为对齐（默认关）**；**触发次数统计**需真实调用 → 见 §D（本 PR 未跑） |
| **记忆下一轮注入** | 下轮上下文能读到 | `selectMemoriesForInject` / `memoryBudget.ts`；`tests/test_memory_budget_382.py` | — | **对齐**（mock） |
| **技能 load / read** | 步骤行可见 | `skill` / `skill_file_read` 上轨 | `skill-*` · `skill-file-*` | **对齐** |
| **技能 save / 沉淀** | 对话沉淀可复用 | `skill` action=save → `saveSkill`；Arti「自进化技能」开关默认关 | — | **链路有**；**Skills create 全流程审计 → #411**（本卡不做） |
| **Arti 记忆中心入口** | 记忆列表/分组/编辑 | 现有 #367/#368/#385；与聊天行跳转 | — | **深度对照纠偏 → #430** |

---

## C. 循环本身（多轮 / 报价确认 / 失败换模型 / 停止）

| 项目 | 「reference」怎么做 | 我们怎么做 | 证据 | 对齐 / 差距 |
|---|---|---|---|---|
| **多轮** | 连续用户轮保持上下文 | `bot/agent_loop.py` + chat_store；agent_regression 多 turn cases | `tests/agent_regression` | **对齐**（mock） |
| **报价确认** | 付费前确认卡 | `plan_quote` / `paid_gate` / `askBeforeGenerating`；拒则 `cancelled` 不扣费 | cases `decline`；#397 积分卡 | **对齐** |
| **失败重试** | 超时/429/5xx 重试提示 | `#232` Retry 行 + 2 次重试；耗尽 bilingual notice | cases `15-*-retry` / `15-timeout` 等 | **对齐** |
| **失败换模型** | 失败后可换模型再试 | `bot/local_llm.py` 换模型确认文案；`fallback_model` 在报价参数中剔除 | 源码 + 文案 | **有能力**；**真实失败换模型抽查 → §D** |
| **用户停止** | 停止后保留已生成、已提交仍结算 | `#391/#419` `run_stop` 卡；已 submit 不取消 | cases `15-hardcap`；RunStop UI | **对齐** |
| **步数硬顶** | 触顶停止并说明 | hard cap / 80-step notice | cases `15-steps80` / `15-hardcap` | **对齐** |

---

## D. 真实调用预算清单（未跑，等 EL 批）

共用 Jingmeng 已批 **$5** WaveSpeed 预算。本 PR **全部 mock**，余额不动。建议 EL 批下列各 **1 次**、最便宜模型：

| # | 项目 | 目的 | 预估 |
|---|---|---|---|
| 1 | 多轮（≥3）不调 memory 工具 | **兜底触发次数**（issue 评论第 1 条） | ~$0.05–0.20 |
| 2 | 多轮调 memory 工具 | 对照：兜底应跳过 | ~$0.05–0.20 |
| 3 | 强制模型失败 → 换模型确认 | 失败换模型 UI/文案 | ~$0.05–0.15 |
| 4 | 报价确认 → 同意 → 实扣对账 | 报价与实扣 | ~$0.02–0.10 |
| 5 | 记忆/技能写入后新开一轮读取 | 下一轮真可读 | ~$0.05–0.20 |

跑前测试把最终预估贴群里给 EL；跑完报实际花费与余额。key 不打印、不落盘。

---

## E. 差距裁定栏（产品填 P0/P1/P2）

| ID | 差距摘要 | 建议去向 | 产品优先级 |
|---|---|---|---|
| G1 | 兜底触发率未知（默认关，但开启后频次未实测） | 真实调用 §D.1–2 后再开卡 | _待产品_ |
| G2 | Skills create 界面/沉淀全流程未审 | **#411** | — |
| G3 | Arti 记忆模块入口与步骤链深度纠偏 | **#430** | — |
| G4 | 「reference」没有、我们有的增强 | Ideas，不进本轮修复 | — |
| G5 | 单步思考无竖线（#325）vs 多步有竖线 | 既定行为；若要对齐多步样式再开卡 | _待产品_ |

产品：在 PR 评论或本表填优先级；有 P0/P1 由 **项目经理** 开修复卡（#78）。

---

## F. 本 PR 产出清单

- [x] 审计表（上）
- [x] 每一种步骤 live+done harness 截图（zh/en × light/dark）
- [x] 没调工具轮次单列
- [x] `tests/test_agent_loop_audit_410.py` + `tests/js/process410/`
- [x] `tests/agent_regression/run.py` 绿（见 PR 正文）
- [ ] 真实调用 §D（等 EL）
- [ ] 设计并排视觉签字
- [ ] 产品填 §E 优先级
