# #509 第 2 步 · 配音 / 声音克隆 / 音效自定义工作流

**Issue:** #524（父卡 #509）· 产品拍板 comment 6535042960  
**Branch tip:** feat/509-2-audio-custom（见 PR）

## 截图（zh light，mock WaveSpeed，无真实扣费）

| 文件 | 内容 |
|---|---|
| `real/workflows-audio-zh-light.png` | 自定义工作流对话框 · 音频分组新增 配音 / 声音克隆 / 音效（内置） |
| `real/workflows-speech-assigned-zh-light.png` | 配音行已分配 `speech-demo.json` |
| `real/audio-speech-voice-zh-light.png` | 音频对话框 · 配音页音色列表换成工作流文件名 `speech-demo`（产品裁定 1） |

## 裁定对照
1. 自定义配音不传对话框音色；列表改工作流名 → 见 `audio-speech-voice-zh-light.png`
2. 有录音走克隆；有自定义克隆则替换内置 → 代码 `audioInputs` `custom:'clone'`
3. 允许任意模型（含 minimax/voice-clone $1.60）；>$0.50 沿用现有确认 → 未改确认阈值
4. 内置音效默认保持 mirelo，不换 elevenlabs → `test_builtin_sfx_default_stays_mirelo`

真实自定义 e2e（约 $0.026）待 EL 批预算；本目录仅 mock。
