# #509 第 2 步 · 配音 / 声音克隆 / 音效自定义工作流

**Issue:** #524（父卡 #509）· 产品拍板 comment 6535042960  
**Code tip:** 见 PR #525（含 WorkflowsDialog 已分配行显示工作流文件名 fix）  
**Assets tip:** 本目录 git tip

## 截图（zh light）

| 文件 | 内容 |
|---|---|
| `real/workflows-audio-zh-light.png` | 自定义工作流对话框 · 音频分组新增 配音 / 声音克隆 / 音效 |
| `real/workflows-speech-assigned-zh-light.png` | 配音行已分配 → 下拉显示 `speech-demo`（非「内置」；design HOLD fix） |
| `real/audio-speech-voice-zh-light.png` | 音频对话框 · 配音页音色列表 = 工作流文件名 `speech-demo` |

## 真调证据（API billed · #514 模式 · 总实扣 $0.026 ≤ $0.05）

目录：`real/evidence/api-billed/` · ledger：`billed-ledger-three.json`

| 路径 | 自定义 JSON | 模型 | task id | 余额前→后 | 实扣 |
|---|---|---|---|---|---|
| speech | `workflows/speech-qwen3-default.json` | qwen3-tts/text-to-speech | `c41f44726a874104804ca882bd75c61d` | 6.302244→6.297244 | $0.005 |
| clone | `workflows/clone-qwen3-default.json` | qwen3-tts/voice-clone | `38c605d8414d499388036da215a8de84` | 6.297244→6.292244 | $0.005 |
| sfx | `workflows/sfx-mirelo-default.json` | mirelo-ai/sfx-2.0/text-to-audio (1s) | `2e4568e08bce4efab0c43e536d27c02e` | 6.292244→6.276244 | $0.016 |

未跑 `minimax/voice-clone`（$1.60）。actual_billed = balance delta。

## 裁定对照
1. 自定义配音不传对话框音色；列表改工作流名 → `audio-speech-voice-zh-light.png`
2. 有录音走克隆；有自定义克隆则替换内置 → `audioInputs` `custom:'clone'`
3. 允许任意模型（含 minimax/voice-clone $1.60）；>$0.50 沿用现有确认 → 未改确认门槛；本 PR 真调未跑 minimax
4. 内置音效默认保持 mirelo → 真调用 mirelo 1s
