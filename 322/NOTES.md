# #322 viewport follow · review assets

| Pack | Path |
|------|------|
| before（出图后视口未跟） | `322/before/light-agent-gen.png` |
| after（自动跟本轮最新） | `322/after/light-agent-gen.png` |
| Theme | light（浅色至少一条典型 Agent 出图路径） |
| Code tip | 见 PR（fix/p1-322-viewport-follow-result） |

行为取舍：多结果跟最新一张；用户正在 pan/pinch 时跳过本次跟随（完成瞬间跟一次）。
