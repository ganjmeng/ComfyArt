---
title: "WaveSpeed Key"
description: "填写 WaveSpeed API Key，查看余额，了解费用怎么显示。"
---

# WaveSpeed Key

ComfyArt 里的所有模型都跑在 [WaveSpeed](https://wavespeed.ai) 上，费用记在你自己的 WaveSpeed 账户。画布编辑、导出和视频剪辑器导出都在本地完成，不需要 Key。

## 填写 Key

1. 在 [wavespeed.ai](https://wavespeed.ai) 创建 API Key。
2. 打开 **设置 → WaveSpeed API key** 粘贴，或在启动 ComfyUI 前设置环境变量：
   ```bash
   export WAVESPEED_API_KEY=ws_xxxxxxxxxxxxxxxx   # 示例占位，不是真实 Key
   ```

## Key 怎么保存

- 环境变量 `WAVESPEED_API_KEY` 优先于界面里填的 Key，此时界面不能修改。
- 新 Key 会用 WaveSpeed 免费的余额接口（`GET /api/v3/balance`）校验，无效会被拒绝。
- 界面填的 Key 保存在后端 ComfyUI 用户目录下的配置文件里，权限 `600`；不写日志，浏览器只能看到最后 4 位（`••••••••abcd`）。
- 没有 Key 时画布照常可用，用到模型的功能会提示云端生成不可用。

## 余额与费用

- 顶栏的余额标签显示 WaveSpeed 余额，点它可以打开 Key 设置。
- 每次运行模型前，**发送** 旁边会显示预估费用（例如 `≈$0.039`）。估价用 WaveSpeed 自己的报价接口，按实际输入计算，包括参考图张数。
- 预估 **$0.50 及以上** 的任务会先请你确认，确认框里显示同样的价格。
- 费用直接付给 WaveSpeed，ComfyArt 不另收费。
