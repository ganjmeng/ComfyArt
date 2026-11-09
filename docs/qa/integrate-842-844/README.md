# #842 + #844 独立集成候选

这是一次新的合并，不是 #842 或 #844 的签字延续。没有改 main，没有合并原 PR，没有部署，没有供应商请求，也没有付费调用。确认文案里的金额来自本地夹具，不能当成产品链路已经打通。

## 两个输入

| 角色 | 完整 SHA | 说明 |
| --- | --- | --- |
| #844 | `b00d0b3a38932456f0f43f05ec3262f895117be6` | 含 SVG 实现 `f36fa178ae8cc48ee2cbd867ac66629ef7191296` 与安全隔离 `40b44600` |
| #842 | `69223e84763a9e02d24e87281da3e005d50a0842` | 含确认展示 `246cdf0994b40f741b656b4211743c54e3b22229` 与截图文档 |

合并提交是 `64fe6eae703e09be5c5f08e95291d695ce829cf3`。它的两个父提交就是上面两个 SHA。代码树是 `0b34d3224504cc52a2f3775c11b96f2646825402`。本说明和三张图是在这次测试之后追加的，没有再改行为。

## 冲突（逐块保留，没有整文件取一侧）

- `api/mcp_tools/canvas.py`：保留 GIF `still_block`（带参考图在报价和提交前拒绝）和 SVG `svg_block` / `ensure_svg_args`。纯文生 GIF 与合法 SVG 都显式走 2.6 文生。SVG 文案写明不改全局默认。工具说明使用 #842 的 “image default” 与 “refused before any quote”，不再写静图会被改写成 GIF。
- `bot/plan_quote.py`：GIF 先 `refuse_still_gif` 再按文生计价；SVG 仍按文生，编辑在计价前拒绝。两侧已有的报价标签都留着。
- `src/botCommands.ts`：SVG 的编辑 / `count≠1` 拒绝，以及 GIF 的 `gifHasStill` 拒绝，按这个顺序都执行。
- `src/generate.ts`：导入同时带上 SVG 规格和 GIF 静图拒绝。生成与估价里两条路径都在。
- `src/locales/en.json`、`src/locales/zh.json`：GIF 说明用 #842（带参考图不估价、不生成）。SVG 说明和透明背景句用 #844。
- `src/ui/GenSettings.tsx`：帧数和帧时长用 #842 的 `GifFrames`（夹紧到有效值）。格式里同时保留 SVG，`n=1`。

## 自动合并后人工看过的四个文件

`api/wavespeed.py`、`bot/guide.py`、`src/comfy.ts`、`src/ui/GenPanel.tsx`。对照合并基线，两侧新增行都还在结果里。保留的行为是：Auto / 默认 2.6、点名 2.5 留在 2.5、未选 quality 不写入 payload、纯文生 GIF 使用请求里的有效帧数、有价和无价确认句、带参考图的 GIF 在提交前拒绝、SVG 的安全准入和本地隔离。

## 这次实际跑过的测试

工作树就是合并提交 `64fe6eae703e09be5c5f08e95291d695ce829cf3`。

- `npx tsc --noEmit`：退出码 0。
- `PYTHONPATH=/agent/repos python3 -m pytest -q tests/test_svg_826.py tests/test_gpt_image_26_route.py tests/test_gpt_image_26_gif.py tests/test_flare_default.py tests/test_curated_models.py tests/test_plan_quote_235.py`：284 passed。
- `PYTHONPATH=/agent/repos python3 -m pytest -q tests/test_svg826_canvas_tip.py`：1 passed。三张图由这次重跑生成。

下面三张图是后来的设计复验重跑，不是上面那次合并测试的旧图，也不是 #844 签字头 `b00d0b3a38932456f0f43f05ec3262f895117be6`。它们仍是 **LOCAL FIXTURE / mock**：真实 Tldraw、`ComfyImageShapeUtil`、`ImageToolbar`、生成卡片，像素来自本地 `admit()`。不是供应商出图，也不是部署实证。

| 图 | 状态 |
| --- | --- |
| `01-path-preview.png` | 透明 path 铺在棋盘上，棋盘只在显示层。下载文件名 `path.svg`，字节和 SHA-256 与已准入原件一致 |
| `02-preview-failed-download.png` | 画布居中失败图标和「预览失败，原 SVG 仍可下载。」没有灰底黑块。下载是 `text_only.svg` 原件 |
| `03-rejected-no-download.png` | 脚本拒绝，没有下载，也没有失败占位图 |

## 设计复验（#844 评论，追加在本候选上）

评论指出两处：失败画布是灰底加左上黑块；透明预览看不出透明。修复在本分支追加，输入祖先仍是 `69223e84763a9e02d24e87281da3e005d50a0842` 和 `b00d0b3a38932456f0f43f05ec3262f895117be6`。

- 失败占位由 `ComfyImageShapeUtil` 绘制，不再把带黑块的预览 PNG 画上画布。存档用的失败 PNG 改为全透明，没有不透明像素。
- 棋盘是 `.ca-svg-checker` 的 CSS。预览 PNG 四角仍是透明，SVG 下载字节不含棋盘。
- 安全拒绝仍无下载，也不会出现失败占位。

这次在修复后的树上重跑：`npx tsc --noEmit` 退出码 0；`tests/test_svg_826.py`、`tests/test_gpt_image_26_route.py`、`tests/test_gpt_image_26_gif.py`、`tests/test_flare_default.py`、`tests/test_curated_models.py`、`tests/test_plan_quote_235.py` 共 285 passed；`tests/test_svg826_canvas_tip.py` 1 passed。#842 上单独的 67 passed 只对应 `69223e84`，不代替这次集成重验。

## 这次没有做

- 没有跑全量 pytest。
- 没有向 WaveSpeed 提交，没有打价格 API，没有付费冒烟，没有加 Replicate 设置工作流。
- 没有把任何直连 GIF 成功写成产品链路通过。
