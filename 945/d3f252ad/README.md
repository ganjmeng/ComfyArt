#945 $0 official DeepSeek prompt check and Full App proof @ d3f252ad

- User message (product 6840756336, same as the lovart.ai audit):
  帮我做一张 YouTube 频道横幅。频道名 Loomi Studio，内容是 AI 绘画教程和创意工作流，每周二、周五更新。风格明亮活泼。
- LLM: official DeepSeek (`https://api.deepseek.com`, `deepseek-flash`). No WaveSpeed/KIE/Replicate key. Cost $0.
- Card 1 question 2 options from the live ask_user call (see prompt-card1-options.json) match lovart.ai verbatim:
  - A: Loomi Studio ＋ AI 绘画教程·创意工作流 ＋ 每周二/五更新
  - B: Loomi Studio ＋ AI 绘画教程·创意工作流
  - C: 只有 Loomi Studio
- Screenshots: zh light and en dark Full App, plus left lovart.ai | right ours compares. `card-1.png` / `lovart-card-1.png` is the QA audit file from the lovart.ai run.
