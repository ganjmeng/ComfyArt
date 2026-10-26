# #321 Local LLM「测试连接」· review assets

| Pack | Path |
|------|------|
| before（无测试按钮） | `321/before/light-botsettings.png` |
| after（测试连接 + 连接成功） | `321/after/light-botsettings.png` |
| after 三类失败文案 | `321/after/light-failures.png` |
| Theme | light（浅色设置页） |
| Code tip | `4c00e5b`（fix/p1-321-local-llm-test-connection） |

探活：`GET {base}/models`；codes：`ok` / `no_url` / `unreachable` / `auth_failed` / `model_missing` / `timeout`。截图为设置区 UI 复刻（无真实 key）。
