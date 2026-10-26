#324 Mode 菜单 off 行露出 provider.detail

- before: main @ 65f637e — off 行仅右侧「去配置 / Set up」，无可见原因；title 为「未检测到」
- after: tip 287179b — off 行 status 显示「未检测到 / Not detected」（probe miss）；title 为 `executable not found`（provider.detail）
- 截自 tests/test_e2e_default_agent.py（fake probe → executable not found）
