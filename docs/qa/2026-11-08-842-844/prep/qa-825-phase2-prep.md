# #825 阶段② QA 准备（不是 PASS）

仅只读卡、PR 元数据与历史 QA 证据；未读代码/差异、未运行测试、未调用供应商、未评论/发送/合并。以下均为待执行用例，非实测结果。

## 来源与基线
- S1 卡正文：https://github.com/ganjmeng/ComfyArt/issues/825
- S2 Tech 最新两阶段锁：https://github.com/ganjmeng/ComfyArt/issues/825#issuecomment-6721184472
- S3 产品端态：https://github.com/ganjmeng/ComfyArt/issues/825#issuecomment-6721185278
- S4 阶段① PR：https://github.com/ganjmeng/ComfyArt/pull/838
- S5 阶段① QA：https://github.com/ganjmeng/ComfyArt/pull/838#issuecomment-6721258295
- S6 报价历史：https://github.com/ganjmeng/ComfyArt/issues/825#issuecomment-6721027823

阶段①已合入 `202ae8b842262ebf42c60c62d08ad86182a7386f`（2026-11-08 20:06，北京时间）。历史 QA 签 `2b8d1a78`：225 passed / 9 skipped，其中本卡14 passed / 1 skipped；覆盖默认仍2.5、2.6选项、GIF t2i与参考图路径、不串视频、报价stub、零烧。以上只是历史记录，不代表本轮复跑或阶段②签字。

## 共用前置及证据要求
取得阶段② PR URL、不可变 head SHA、基底与可执行 mock/本地测试入口；网络禁止真实供应商提交。每项保存 tip SHA、输入、测试名称/命令、完整结果与跳过原因、脱敏路由/请求payload、quote/确认截图或快照，全部标 MOCK。真实供应商链路持续 HOLD。

| ID | 前置 | 输入 | 期望 | 必需证据 |
|---|---|---|---|---|
| D1 | 新会话、清除历史显式模型、文生mock | 不选模型，生成静图 | 实际路由 `openai/gpt-image-2.6-flare/text-to-image`，非sunburst或2.5 | 路由解析与最终payload，S1–S3 |
| D2 | 同D1 | 显式Auto，文生静图 | 同D1 | Auto原始输入及最终payload，S1–S3 |
| D3 | 编辑mock、固定参考图 | 不选模型，修改图片 | 实际路由2.6-flare编辑端点，参考图保留 | 图片引用、最终模型与请求，S1–S4 |
| D4 | 同D3 | 显式Auto，编辑图片 | 同D3 | Auto输入、参考图与编辑请求，S1–S4 |
| R1 | picker保留旧版，文生/编辑分别mock | 显式2.5-flare，各提交一次 | 各自走2.5文生/编辑，不被新默认覆盖；旧版可选可回滚，非双默认 | picker快照及两份最终payload，S2–S4 |
| Q1 | D1–D4及R1参数化 | quality完全未选/未提供 | 最终供应商payload不含quality键（不是null或固定medium）；估价采用模型默认档 | 键缺席断言、quote参数快照，S1/S4；本任务明确“未选不传” |
| Q2 | 同上、schema允许显式选档 | 显式选一个合法quality | 保留用户选择，不由默认迁移覆盖 | 显式输入与payload对照，S1/S4 |
| G1 | t2i GIF mock | “生成GIF/动图”，默认帧参数 | 2.6 t2i，output_format=gif；默认9帧/200ms；不调用generate_video/animate_image | 路由与工具调用轨迹、payload，S1/S4/S5 |
| G2 | 固定静图参考、GIF mock | “把这张图做成循环GIF” | 参考图+t2i GIF，不走edit gif或视频；UI/Agent明确说明等价路径且参考图未丢 | 输入引用、路由、UI/Agent说明快照，S1/S4/S5 |
| G3 | GIF参数mock | 帧数2/16、时长20/2000；另测越界 | 合法边界原样；越界不静默改视频，按产品校验约定返回可读错误（具体拒绝/规范化策略需实施方提供） | 参数化断言及错误回传，S1/S4 |
| F1 | 注入mock报价失败、生成失败 | GIF与静图各失败一次 | 报价失败可文档估价且明确估算；生成失败原因回传、不伪done、不丢静图路径说明、不静默转视频 | 故障fixture、UI/Agent错误快照、调用轨迹，S1/S4 |
| P1 | stub报价，统一1k及默认档 | D1–D4、R1，GIF分别2/9/16帧 | quote、确认模型/格式与最终路由一致；2.6历史medium基准$0.05，2.5 $0.024；GIF同档静图价、帧数不加价；确认显示GIF帧数/时长 | 同一请求ID的输入→quote→确认→payload对照，S4/S6；非当前实扣报价 |
| V1 | 使用已有GIF fixture完成mock任务 | 文生与静图GIF成功返回 | 画布/历史可播放、image/gif、下载.gif；静图输出不退化 | 页面/历史快照、文件类型/下载名断言，S4 |

## 关键缺项与开跑闸
1. 本次读取issue四条评论及最近15个PR（按创建时间降序，最新#841），未发现阶段②新PR链接；#838仅阶段①。不能据此断言后续不会新建。阶段②PR/head SHA仍缺。
2. 缺阶段②四路实际payload、未选quality键缺席断言、显式2.5回滚、报价确认一致性的本tip报告；历史225 passed不能替代。
3. 历史QA表未单列失败原因回传、静图说明、画布播放/下载的新tip证据，需执行F1/G2/V1补齐；历史9 skipped/本卡1 skipped的具体原因未在签字评论列出，执行时须解释相关覆盖是否受影响。
4. GIF越界策略与准确mock入口需工程提供；不调查代码行为。需要代码行为调查时交cloud agent，当前不启动。
5. 真实供应商链路/当前实扣/真实成片未跑，付费冒烟仍暂停；mock通过也不可宣称真实链路PASS。产品+QA+Tech新tip齐签后才进入合并决策，本清单不授权合并。
