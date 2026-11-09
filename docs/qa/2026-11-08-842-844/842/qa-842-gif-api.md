# 静图参考 → GIF 的 API 能力查验（HOLD）

结论：**HOLD**。静图参考转 GIF 没有完成。当前 head 在估价和生成之前拒绝，生成 POST 次数为 0，参考图没有进入任何请求体。明确拒绝不能代替这个功能。

本次实现对照的 SHA 是 **`2e7d7f21cb3b40519adb119fa712143f33aa81de`**。它是 PR #842 在 2026-11-08 22:19 CST 的 head，提交说明是 `fix(#825): refuse still-to-GIF before quote or generation`。上一份签字 `a59b683bdd438a576adbb9a0c984ba4649df7bd8` 是它的父提交，行为不同（丢掉静图后仍 POST 文生），不并入这次签字。

Lovart 实现没有核实。没有生成 POST，没有付费，没有读取密钥，没有上传用户图片。

查询时间：2026-11-08 22:20:04–22:20:54 北京时间（响应头 `Date` 为 14:20:04–14:20:54 GMT）。原始记录在 [artifacts/qa-842-gif-api/](artifacts/qa-842-gif-api/)。

## 能力矩阵

| 对象 | 文档 | 实时 schema | 离线最终 payload | 真实生成 |
|---|---|---|---|---|
| OpenAI Images API，`gpt-image-2.6` 指南 | 支持。`POST /v1/images/generations` 和 `POST /v1/images/edits` 都可以 `output_format: gif`。静图参考要送到 edits。`frame_count` 2–16 默认 9，`frame_duration_ms` 20–2000 默认 200 | 未知。没有无鉴权的 schema GET | 不适用。本仓库不调用这条 API | 未测 |
| WaveSpeed `openai/gpt-image-2.6-flare/edit` 与 `.../sunburst/edit` | 公开页面把 `output_format` 写成 `png` / `jpeg` / `webp`。有必填 `images`（最多 16）、`quality`（low–max，默认 medium）、`complexity`（low/medium/high，默认 high）、`resolution`（1k/2k/4k）。正文没有 `frame_count` / `frame_duration_ms`。总览写明 GIF 只在文生，编辑返回 PNG/JPEG/WebP | 未知。`GET https://api.wavespeed.ai/api/v3/models` 无鉴权返回 401 | 本 head 不产生编辑 GIF payload | 未测 |
| WaveSpeed 两个 2.6 文生端点 | 支持 GIF 与 SVG。`frame_count` 2–16 默认 9，`frame_duration_ms` 20–2000 默认 200，时长按 10ms 取整。页面写 GIF/SVG 只在文生。没有参考图字段 | 未知，同一 401 | 纯文生 GIF 仍可组 payload。带静图的调用到不了 payload | 未测 |
| 本仓库 fixture 与路由 | fixture 与上面的 WaveSpeed 页面一致：编辑有 `images`、无 gif；文生有 gif 和帧字段、无 `images` | fixture 不是实时 schema | 见下方探针 | 未测 |

OpenAI 文档支持 edits+GIF，不能写成 WaveSpeed 编辑端点支持 GIF。两边是不同的 URL。

## 抓取证据

全部是 GET，没有 `Authorization`。

| 时间（CST） | HTTP | URL |
|---|---|---|
| 22:20:04 | 200 | https://developers.openai.com/api/docs/guides/image-generation?model=gpt-image-2.6#generate-animated-gif-output |
| 22:20:05 | 200 | https://wavespeed.ai/models/openai/gpt-image-2.6-flare/edit |
| 22:20:05 | 200 | https://wavespeed.ai/models/openai/gpt-image-2.6-flare/text-to-image |
| 22:20:05 | 200 | https://wavespeed.ai/models/openai/gpt-image-2.6-sunburst/edit |
| 22:20:06 | 200 | https://wavespeed.ai/models/openai/gpt-image-2.6-sunburst/text-to-image |
| 22:20:06 | 200 | https://wavespeed.ai/gpt-image-2-6-api |
| 22:20:06 | 200 | https://wavespeed.ai/docs/docs-api/openai/openai-gpt-image-2.6-flare-edit |
| 22:20:06 | 200 | https://wavespeed.ai/docs/docs-api/openai/openai-gpt-image-2.6-flare-text-to-image |
| 22:20:06 | 200 | https://wavespeed.ai/docs/docs-api/openai/openai-gpt-image-2.6-sunburst-edit |
| 22:20:07 | 200 | https://wavespeed.ai/docs/docs-api/openai/openai-gpt-image-2.6-sunburst-text-to-image |
| 22:20:54 | 401 | https://api.wavespeed.ai/api/v3/models |

401 正文：`{"code":401,"message":"Missing API key. Send it as: Authorization: Bearer <your API key>."}` 请求 id `dcb1b4a1-0706-40c2-922b-0d936fda9e62`。因此实时模型 schema **未知**，不能从这次 GET 写成「线上不支持」。

OpenAI 页面原文：Set `output_format: "gif"` on `POST /v1/images/generations` or `POST /v1/images/edits`. To guide the animation with still reference images, send them to the image edit endpoint. 同页写 Both models（Sunburst 与 Flare）support animated GIF output through the Image API。

WaveSpeed flare/sunburst 编辑文档的参数行：`output_format` No `png` (default), `jpeg`, or `webp`. 文生文档 Notes：`GIF and SVG output are available on text-to-image only.` 总览 FAQ：`GIF and SVG output are available for text-to-image only; edits return PNG, JPEG, or WebP.`

仓库 `tests/fixtures/wavespeed_catalog_subset.json` 在这个 head 上没有被这轮提交改过。探针读到的编辑 schema 有 `images`、`quality`，`output_format` 不含 `gif`，也没有帧字段。文生 schema 含 `gif`，`frame_count` 最小 2、最大 16，没有 `images`。这和上述 WaveSpeed 页面一致，也和旧 tip 用过的同一份 fixture 一致。

## 离线契约

期望的编辑 GIF 体（只在进程内构造，未发送）：

```text
model=openai/gpt-image-2.6-flare/edit 或 sunburst/edit
images=["https://cdn.test/qa-still.png"]
output_format=gif
frame_count=9
frame_duration_ms=200
```

```text
env -u WAVESPEED_API_KEY -u KIE_API_KEY GATE=1 COMFYART_SKIP_NODE_TESTS=1 \
  python3 -m pytest --import-mode=prepend -vv --tb=short \
  tests/_qa842_edit_gif_capability.py
```

工作目录 `/tmp/qa-2e7d/ComfyArt`，HEAD `2e7d7f21cb3b40519adb119fa712143f33aa81de`。

**1 passed，2 failed，exit 1。** 通过的是 fixture 字段对照。失败的是 flare 与 sunburst 各一次：`status=400`，`kind=gifStillUnsupported`，`gen_count=0`，`posts=[]`。异常文本是「静图转 GIF 不支持参考图，估价和生成都不会开始」。参考图没有被静默丢掉后继续生成，也没有出现在编辑 GIF 的最终 payload 里，因为根本没有 payload。`api/gif_image.py` 写明这次拒绝不读取 schema，`schemas is unused for that refusal`。所以即使以后的实时 schema 给编辑加上 `gif`，这段代码仍会挡住。

`COMFYART_SKIP_NODE_TESTS=1` 只跳过前端 node 测试。这个探针没有调用 node。没有出站记录。

## 最小真实冒烟（只设计，未运行，未取凭据）

1. 凭据留在操作者侧。本代理不读取。
2. 只做一次带鉴权的 `GET https://api.wavespeed.ai/api/v3/models`。抽出四个 id 的 `output_format` 枚举、是否有 `images`、是否有 `frame_count` / `frame_duration_ms` 及 min/max/default。把 JSON 存档。这一步仍然不是生成。
3. 若 flare edit 与 sunburst edit 的实时枚举里没有 `gif`，停住，不 POST。把结果写成「实时 schema 不支持」，而不是沿用今天的未知。
4. 只有实时枚举同时有 `gif` 和 `images` 时，才各做一笔冒烟：公开示例图 URL（不用用户图），`output_format=gif`，`frame_count=2`，`frame_duration_ms=200`，不传 quality。先走现有估价。报价高于事先写死的上限（建议 0.10 USD）就取消，不提交。只 POST 一次，不重试，不轮询以外的额外生成。
5. OpenAI `POST /v1/images/edits` 是另一条供应商。除非产品决定改接入，否则不纳入这笔 WaveSpeed 冒烟。

## 未做

未改产品代码，未提交，未评论，未切供应商，未生成，未付费。
