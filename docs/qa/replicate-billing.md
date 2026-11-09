# Replicate GPT Image 2.6 计费

核对日期：2026-11-08。来源是 Replicate 官方模型页 `https://replicate.com/openai/gpt-image-2.6-flare` 的说明，不是第三方价目转载。

官方页写明：

- `quality` 改变价格。取值 `low`、`medium`、`high`、`xhigh`、`max`、`auto`（默认）。
- `complexity` 不改变价格。
- GIF 按 OpenAI 回报的 token 计费。帧数更多、质量更高更贵，每张输入图另加输入 token。
- SVG 按出图 token 再加描图模型的 token。`svg_model` 会改变费用。
- 页面没有给出可当作硬上限的单价表。

因此这里不把任何一次观察到的金额（包括 $0.030405）写成固定价或上限。第三方价目互相不一致，也不能当合同价。

产品行为：

- 管理员保存 Replicate 只表示新任务可以走这条线路。保存不等于终端用户同意付费，也不等于已经能静默扣费。
- 没有 `source=quote` 的数字时，估价返回 `price: null`、`source: unpriced`、`confirm: true`。
- 第一次提交只记下这次 provider、model、质量和参数的快照并返回 409，不向 Replicate 发请求。
- 同一次快照上、使用的人确认之后的下一次提交才发送。直接带 `confirmed=true` 而没有先拿到这次快照的报价，仍然不发送。
- 参数、模型或版本变了，旧确认作废。
- 主备两边都没有可比较的报价时，不自动改走备选。
