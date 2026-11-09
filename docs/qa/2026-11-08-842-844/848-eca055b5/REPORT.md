# #848 集成候选只读复验

锁定 head：`eca055b522d2f10ca2b3993f9af1f75f338ff8bc`  
提交说明：`fix(#826): show SVG failure placeholder and a display-only checker`（2026-11-09 00:10:52 UTC）  
分支：`cursor/integrate-842-844-b424`  
PR：https://github.com/ganjmeng/ComfyArt/pull/848  
复核时刻：2026-11-09 08:16 开始，08:21 北京时间远端 head 仍是这一枚。没有漂移。

这不是 Lovart 新版，也不是供应商出图。没有改产品代码，没有合并，没有关卡。真实生成不由本复验执行，费用未知。云端结果不能外推到未提供的部署环境。

## 输入是否在这棵树上

合并提交 `64fe6eae703e09be5c5f08e95291d695ce829cf3` 的两个父提交就是：

- #844 `b00d0b3a38932456f0f43f05ec3262f895117be6`
- #842 `69223e84763a9e02d24e87281da3e005d50a0842`

`git merge-base --is-ancestor` 对当前 head 两者都是 YES。

## 7 个冲突文件和 4 个自动合并文件

树上没有残留冲突标记。对照两个父提交，结果里两侧行为都在：

- `api/mcp_tools/canvas.py`：带静图的 GIF 在报价前拒绝；合法 SVG 仍走 2.6 文生。普通 Auto 断言已是 2.6（测试函数名仍带 `stays_25`，断言不是 2.5）。
- `bot/plan_quote.py`：GIF 先 `refuse_still_gif`，SVG 仍按文生并在编辑时拒绝。
- `src/botCommands.ts`、`src/generate.ts`：SVG 的编辑/`count≠1` 与 GIF 静图拒绝都在。
- `src/locales/en.json`、`src/locales/zh.json`：GIF 说明是带参考图不生成；SVG 说明和透明背景句都在。
- `src/ui/GenSettings.tsx`：GIF 帧数夹紧，同时保留 SVG `n=1`。
- 自动合并的 `api/wavespeed.py`、`bot/guide.py`、`src/comfy.ts`、`src/ui/GenPanel.tsx`：目录默认是 `openai/gpt-image-2.6-flare/text-to-image` 与 `.../edit`。2.5-flare 文生和编辑仍在列表里。指引写默认是 2.6，点名 2.5 仍可用；SVG 写明不改全局默认。

## 命令

工作树 `/tmp/qa848`，`GATE=1`，未设置供应商密钥。

| 命令 | 结果 |
| --- | --- |
| `npx tsc --noEmit` | 退出码 0 |
| `pytest -q tests/test_svg_826.py tests/test_gpt_image_26_route.py tests/test_gpt_image_26_gif.py tests/test_flare_default.py tests/test_curated_models.py tests/test_plan_quote_235.py tests/test_svg826_canvas_tip.py` | **286 passed**，112.89s，退出码 0 |
| 封存探针 `d2ee34ec…` 原样 | **5 failed, 5 passed**，4.52s。哈希前后不变 |
| 路由/准入脚本 | 见下。GIF 估价在缺密钥处停下，没有出网 |
| 隔离与绘制负载 | 见下。结束后无 `svg_worker.py` |

## PASS / HOLD

**PASS（本 tip、本云端、mock/本地夹具）**

- Auto / 空模型 / `auto` 文生解析为 `openai/gpt-image-2.6-flare/text-to-image`。显式 2.5 文生和 2.5 编辑仍解析到 2.5。
- 带静图的 GIF 抛 `StillGifUnsupported`。这是拒绝保护，**不算**静图转 GIF 原 AC 完成。原 AC 仍是 HOLD。
- 确认框本地夹具可见：「这次云端生成约需 5 积分，GIF 16 帧（已从 99 帧调整），每帧 20 毫秒（已从 5 毫秒调整）」。标了 `LOCAL FIXTURE · mock price 0.05 · not a live price API`。金额是夹具，不是实价。
- SVG：`script` / `onload` / 外链 / 实体拒绝且 `download is None`。`text_only` 为 `preview_failed`，中文原因「预览失败，原 SVG 仍可下载。」，下载字节等于原件。失败记录 PNG 为 8×8 且不透明像素数为 0。
- `path.svg` 状态 `transparent`，下载 SHA-256 `03d74eefb3e52a48a0ef4452a219ce2d6ea7ee4f4834112faa8d16c70bf44c18`，与原件相同。
- 画布操作：真实 Tldraw、`ComfyImageShapeUtil`、`ImageToolbar`。棋盘只在 `.ca-svg-checker` 显示层。点下载得到的文件名和字节与原件一致。拒绝态生成卡写「不会提供下载」，没有下载按钮，也没有失败占位。横幅写明 mock，不是供应商结果。
- `count=1.5` 为 `svgCount`。SVG 估价 mock：`0.07`，`source=estimate`，顶层 `model` 与 `svg.model` 都是 2.6，note 不含 2.5。`ClientSession` 没有被用来打价格 API。
- 内核 `unshare` EPERM：`rendered=false`，无下载，`-v` 无 `svg_raster`/`PIL`。Landlock 创建 EPERM：无下载，但模块已导入后才失败。71 KiB path 绘制负载 0.098s 内完成，真实探针 `ENETUNREACH` + `EACCES`，无残留进程。

**工具错误 / 旧契约（封存探针，不改）**

- 时钟第三条 `StopIteration`。
- 外链已在解析前拒绝，所以 IO 计数仍期望 `fromstring + 1` 而失败。
- path 状态是 `transparent` 不是探针要的 `normal`。
- 正好 512 KiB 的非 XML 现在不下载，旧探针仍期望下载。
- `tiff` 不报 `svgEdit`；点名 2.5 的 SVG 改走 2.6 而不是留在 2.5。这是旧契约，不是本 tip 的路由回退。

**HOLD**

- 静图转 GIF 的成功生成。拒绝保护不是完成。
- 产品 768 MiB、CPU 3 秒、2 MiB 输出没有被这次有界绘制负载打中（0.098s 正常结束）。没有用空 stdin 的 `alarm` 冒充渲染负载。无目标部署，不外推。
- 真实供应商生成、实价、付费：未跑。

## 截图（本次重跑，mock）

| 文件 | 内容 |
| --- | --- |
| [01-path-preview.png](01-path-preview.png) | 棋盘上的绿色 path，工具栏写背景透明、下载仍是原 SVG |
| [01-checker-face.png](01-checker-face.png) | 棋盘特写 |
| [02-preview-failed-download.png](02-preview-failed-download.png) | 失败图标和原因句，不是灰底黑块 |
| [02-fail-face.png](02-fail-face.png) | 占位特写 |
| [03-rejected-no-download.png](03-rejected-no-download.png) | 拒绝文案，无下载 |
| [qa848-confirm-mock.png](qa848-confirm-mock.png) | 确认框 mock，16 帧 / 20 毫秒 |

日志：[qa848-pytest.log](qa848-pytest.log)、[qa848-sealed-probe.log](qa848-sealed-probe.log)、[qa848-isolate.log](qa848-isolate.log)、[qa848-tsc.log](qa848-tsc.log)。
