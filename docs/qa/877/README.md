#877 Agent 设置与对话失败：官方默认 / 自定义 / 连接失败 / 官方（自定义保留） / 管理员 / 对话失败（左右对比 main）

$0 mocked local shots. Left is main (`1a11f11b`); right is this PR. Raw GitHub URLs in the PR body are pinned to the tip SHA and embedded as images.

| 状态 | 左 main | 右 PR | 左右对比 |
| --- | --- | --- | --- |
| 默认（官方 DeepSeek，字段收起） | [01-default-before-main.png](01-default-before-main.png) | [01-default-after-pr.png](01-default-after-pr.png) | [01-default-lr.png](01-default-lr.png) |
| 自定义连接成功 | [02-custom-before-main.png](02-custom-before-main.png) | [02-custom-after-pr.png](02-custom-after-pr.png) | [02-custom-lr.png](02-custom-lr.png) |
| 自定义服务返回错误（红点 + 切回按钮） | [03-failed-before-main.png](03-failed-before-main.png) | [03-failed-after-pr.png](03-failed-after-pr.png) | [03-failed-lr.png](03-failed-lr.png) |
| 官方默认（自定义配置保留、未使用） | [04-switched-before-main.png](04-switched-before-main.png) | [04-switched-after-pr.png](04-switched-after-pr.png) | [04-switched-lr.png](04-switched-lr.png) |
| 由管理员配置 | [05-admin-before-main.png](05-admin-before-main.png) | [05-admin-after-pr.png](05-admin-after-pr.png) | [05-admin-lr.png](05-admin-lr.png) |
| 对话失败 + 切回官方默认 | [06-chat-failed-before-main.png](06-chat-failed-before-main.png) | [06-chat-failed-after-pr.png](06-chat-failed-after-pr.png) | [06-chat-failed-lr.png](06-chat-failed-lr.png) |
