# QA #842 独立复验（HOLD）

结论：**HOLD**。只签这个不可变 head，不沿用作者的 441 passed，不签字、不评论、不合并、不部署。

真实 WaveSpeed 生成、价格 API、扣费、成片：**未跑**。下文价格都是 mock 或仓库里的历史文档表，不是现价，也不是实扣。

## 固定 SHA

| 项 | 值 |
|---|---|
| PR | https://github.com/ganjmeng/ComfyArt/pull/842 |
| 预期前缀 | `fbe28e7f` |
| 完整 head | `fbe28e7f11ef52ef9aa22176d5b9c9e6ced0d233` |
| 远程分支 `origin/cursor/gpt-image-26-default-e355` | 同一 SHA |
| 父提交 / PR base | `fe342cea4b34c095285e90edc4b13da77d89a315` |
| 提交时间 | 2026-11-08 13:11:02 +0000 |
| 状态 | OPEN，`mergeable=MERGEABLE`，`mergeStateStatus=CLEAN` |
| 漂移 | 无。前缀与远程 head 一致，本报告只覆盖这一 SHA |

本地 `main` 工作区仍停在 `fe342cea4b34c095285e90edc4b13da77d89a315`，未切分支、未改产品代码、未 commit / push。复验发生在 detached worktree `/tmp/qa-repos/ComfyArt`。临时探针 `tests/_qa842_independent.py` 只存在于该 worktree，未提交。

## 方法

- 只读 diff 与源码，对照准备清单 D1–D4、R1、Q1–Q2、G1–G3、F1、P1，以及阶段①选项是否还在。
- HTTP 全部换成进程内假 `ClientSession`。环境里没有 `WAVESPEED_API_KEY`。假价格接口成功时返回 `discounted_price=9.99`，用来证明「报价模型 = 即将 POST 的模型」，这个 9.99 不是文档价。
- 价格接口失败（传输异常或 HTTP 503）时，才落到代码里的历史表。
- 未打开浏览器，未做画布点击、历史播放或下载点击。

## 用例

判定只针对 mock。`PASS` 表示这条 mock 行为与清单一致。整体仍是 HOLD。

| ID | 结果 | 实测 |
|---|---|---|
| D1 不选模型，文生 | PASS | 缺省、`""` 都 POST `openai/gpt-image-2.6-flare/text-to-image`。body 无 `quality`、无 `complexity`。估价 `model` 与 URL 相同 |
| D2 显式 `auto`，文生 | PASS | 同上。产品 id 是小写 `auto`（`src/models.ts` 的 `AUTO_IMAGE`）。字符串 `Auto` 得到 400，且没有供应商 POST |
| D3 不选模型，编辑 | PASS | POST `openai/gpt-image-2.6-flare/edit`，`images` 仍是参考图 URL，body 无 `quality` |
| D4 显式 `auto`，编辑 | PASS | 同 D3 |
| R1 显式 2.5 文生 / 编辑 | PASS | `openai/gpt-image-2.5-flare/text-to-image` 与 `.../edit` 原样提交。编辑 `images` 保留。body 无 `quality`。没有被默认 2.6 覆盖 |
| Q1 未选 quality | PASS | 不传 params、params `{}`、`params.quality=null` 三种最终 body 都没有 `quality` 键，不是 `null`。报价 inputs 同样没有该键 |
| Q2 显式 quality | PASS | 文生 `high`、编辑 Auto `low`、显式 2.5 `max` 都原样进入 body。报价 inputs 与 body 同档，模型仍是点名的那个 |
| G1 文生 GIF | 路由 PASS，说明 FAIL | POST 2.6-flare text-to-image，`output_format=gif`，默认 `frame_count=9`、`frame_duration_ms=200`。URL 不含 video，也不是 edit。报价 inputs 不含帧字段。估价 `gif_route=text_to_image`。但 `gif_note` 仍写「默认模型仍是 GPT Image 2.5 Flare / The default model stays GPT Image 2.5 Flare」 |
| G2 静图参考 GIF | 路由 PASS，最终 payload HOLD | 路由改成 2.6 text-to-image，`gif_route=reference_t2i`。说明含「编辑模型没有 gif」和「not a video」。不走视频。已提交 catalog fixture 的 2.6 文生 schema 没有 `image` / `images`，`build_payload` 因此不把参考图写入最终 POST |
| G3 帧边界 | 路由 PASS，拒绝文案未实现 | 2/20、9/200、16/2000 原样。1/19 夹成 2/20，99/99999 夹成 16/2000，非数字回到 9/200。没有可读错误，也没有改走视频。这是阶段①的夹紧，本 PR 没有改成拒绝 |
| F1 失败回传 | PASS（mock） | 价格接口抛错：文生估价 `source=estimate`、`price=0.05`、`model` 为 2.6-flare 文生；确认 409 带 `estimate=true` 和同一 `model`，确认前没有生成 POST。GIF 16 帧同样是 0.05。显式 2.5 文生估价回落 0.024。生成 POST 返回 422 时异常文本含 `provider rejected the prompt`，`_jobs` 仍为空。GIF 失败时 URL 仍是 2.6 文生 gif |
| P1 估价与确认同路由 | PASS（mock，非实扣） | 价格接口在线时，2/9/16 帧的估价 `model`、价格请求 `model_id`、生成 URL 都是 2.6-flare 文生，价格都是假值 9.99，价格请求不含 `frame_count` / `frame_duration_ms`。`confirm_usd=0` 时，编辑 Auto 的 409 `error.model` 是 2.6-flare edit；静图 GIF 的 409 `error.model` 是 2.6-flare 文生，并带参考图说明。确认前没有生成 POST。`documented_usd`：2.6 medium 1k = 0.05，2.5 medium 1k = 0.024 |
| 阶段①选项 | PASS | 相对父提交，`models` 与 `more` 数组不变。2.5-flare 文生仍在推荐列表，2.5-flare 编辑仍在 more。2.5/2.6 sunburst 都在。没有 `default_params`，因此不会给 GPT Image 自动写入 quality。`poster_text` 从 2.5 文生改为 2.6-flare 文生；其余 Auto 分类模型 id 未改。下拉顺序函数不把 default 拉到第一位 |
| V1 画布播放 / 下载 | 未测 UI | `tests/test_gpt_image_26_gif.py` 断言 GIF 字节得到 `.gif`，以及 `image/gif`。没有打开画布、历史或下载 |

## 源码证据（head `fbe28e7f11ef52ef9aa22176d5b9c9e6ced0d233`）

默认 id：

- `api/curated_models.json` 文生 `default` 为 `openai/gpt-image-2.6-flare/text-to-image`；2.5-flare 文生仍在 `models`。
- 同文件编辑 `default` 为 `openai/gpt-image-2.6-flare/edit`；2.5-flare 编辑在 `more`。
- `api/wavespeed.py` `resolve_model`：空模型，以及 `auto` / `auto:video`，返回该 feature 的 `default`。其他未知 id 400。
- `api/wavespeed.py` `build_payload`：`params` 里值为 `None` 的键不写入。GPT Image 的 `default_params` 为空，所以未选 quality 不会被补成 `medium` 或 `null`。
- `api/wavespeed.py` `_submitted_tier`：报价档会补上 schema 的 resolution 默认值（fixture 为 `1k`），注释写明该键不随生成 POST 发出。未选 quality 不会在这里补上。

GIF 与说明：

- `bot/guide.py` 已改成默认是 2.6-flare 文生 / 编辑，并写明 2.5 只有点名才用；静图是参考，禁止 `generate_video` / `animate_image`。
- `api/gif_image.py` `note("text_to_image")` 仍是：「默认模型仍是 GPT Image 2.5 Flare。」以及 “The default model stays GPT Image 2.5 Flare.” 这条会进估价 `gif_note` 和确认 409。
- `api/gif_image.py` `note("reference_t2i")` 正确说明编辑没有 gif、静图作参考、不改走视频。
- `api/mcp_tools/canvas.py` 的 `generate_image` 工具说明仍写 “a GIF uses GPT Image 2.6 Flare, not the stable 2.5 default.” 同文件 GIF 分支注释仍写 “the stable default stays 2.5 for stills.” 本 PR 没有改这个文件。
- `src/gifFile.ts` 文件头注释仍写 “Defaults stay on 2.5”。这是注释，不是确认文案。
- `api/wavespeed.py` `build_payload` 只有 schema 含 `images` 或 `image` 才把参考图放进 POST。fixture `tests/fixtures/wavespeed_catalog_subset.json` 里 2.6-flare 文生的 properties 只有 aspect_ratio、resolution、quality、complexity、prompt、output_format、frame_count、frame_duration_ms 等，没有图像字段。因此 mock 最终 POST 丢掉参考图 URL。线上 schema 未拉取。

阶段①保留：`picker_order` 不把 default 提前。Agent 的 `list_models` 仍按既有规则把 default 放在推荐视图第一位，所以推荐视图现在以 2.6-flare 开头。这是 default 切换的结果，不是下拉数组重排。

## 命令与数量

工作目录：`/tmp/qa-repos/ComfyArt`。`git rev-parse HEAD` = `fbe28e7f11ef52ef9aa22176d5b9c9e6ced0d233`。

```text
python3 -m pytest --import-mode=prepend -q --tb=line -ra \
  tests/_qa842_independent.py \
  tests/test_gpt_image_26_route.py \
  tests/test_gpt_image_26_gif.py \
  tests/test_flare_default.py \
  tests/test_curated_models.py \
  tests/test_model_auto.py \
  tests/test_auto_pick.py \
  tests/test_auto_pick_accuracy_237.py \
  tests/test_list_models_paging.py \
  tests/test_model_fallback_236.py \
  tests/test_linkedin_size_707.py \
  tests/test_ref_structure.py \
  tests/test_region_pasteback.py
```

结果：**459 passed，0 failed，0 skipped，exit 0，5.35s**。

拆分：

- 独立探针 `tests/_qa842_independent.py`：25 collected，全部通过。
- 上列作者测试文件：434 collected，全部通过。
- 本次没有任何 skip，因此没有 skip 原因。未跑的全库用例不是 skip，是没有纳入这条命令。
- 作者 PR 正文的 441 passed **没有复用，也没有复跑成同一个数字**。

```text
npx tsc --noEmit
```

结果：exit 0，无输出。`tsc` 7.0.2。依赖来自该 worktree 的 `npm ci`（206 packages，exit 0）。

运行环境：Python 3.12.3，pytest 9.2.0。为了让 conftest 能导入，本机额外安装了 aiohttp、pytest、pytest-asyncio、sqlalchemy、Pillow、pypdfium2、av。这些安装不改变产品代码。

## 盲区

- 真实供应商提交、轮询、成片、价格 API、扣费：未跑。mock 通过不能写成真实链路 PASS。
- 画布可播放、历史记录、`image/gif` 下载点击：未在浏览器执行。
- 2.6 文生线上 schema 是否接受参考图：未知。当前结论只对已提交 fixture 成立。
- 编辑模型在价格 API 失败时不走 2.6 文生的 0.05 表。`_quote` 的文档表只覆盖 `GIF_T2I`（2.6 flare/sunburst 文生）。编辑会落到 catalog `base_price`。fixture 里 2.6-flare edit 的 `base_price` 是 0.065。这条编辑回落没有单独打探针。
- 全库 pytest、e2e、付费冒烟：未跑。
- 越界帧没有用户可读错误，只有夹紧。若产品要求拒绝文案，这一条还没实现。

## #844 共享默认配置（只报告）

PR：https://github.com/ganjmeng/ComfyArt/pull/844  
head：`4e24170015629d61f92fbdc7889069359d7a7cea`（`cursor/svg-826-t2i-b424`）  
base：与 #842 相同，`fe342cea4b34c095285e90edc4b13da77d89a315`。

文本合并：

```text
git merge-tree --write-tree \
  fbe28e7f11ef52ef9aa22176d5b9c9e6ced0d233 \
  4e24170015629d61f92fbdc7889069359d7a7cea
```

exit 0，结果树 `7b8debf924a4cdb514fff6f28e058492e7a57624`。两边都改过的 `api/wavespeed.py`、`bot/guide.py`、`src/comfy.ts`、`src/ui/GenPanel.tsx` 能自动合上，没有冲突标记。`api/curated_models.json` 只有 #842 修改，合并后 default 仍是 2.6-flare。`resolve_model` 对 `auto` 的处理也还在。

语义风险（不修改任何一边）：

1. 合并后的 `bot/guide.py` 同时存在两句相反的话：GIF 段写默认是 `openai/gpt-image-2.6-flare/text-to-image`；紧接着的 SVG 段写 “The stable image default stays openai/gpt-image-2.5-flare/text-to-image.”
2. #844 的 `tests/test_svg_826.py` `test_default_model_stays_25_flare` 断言 `curated["text_to_image"]["default"]` 和 `resolve_model("text_to_image", None)` 都是 2.5-flare 文生。合并后 curated default 已是 2.6，这条测试会失败。
3. #844 `api/svg_image.py` 的用户说明仍写「默认模型仍是 GPT Image 2.5 Flare」。`api/mcp_tools/canvas.py` 的 SVG 注释也写 stable default stays 2.5。
4. #844 自己的说明是「默认图像模型仍是 2.5，未改 curated_models.json」。该说明在 #842 合入之后不再成立。先合 #842 再合 #844，行为会变成静图默认 2.6，而 SVG 文案和测试仍锁 2.5。

未把两边检出后跑合并测试，以上第 2 点是断言与合并后文件内容的直接对照。

## 未执行的写操作

未改产品代码，未 commit，未 push，未创建或更新 PR，未在 GitHub 评论、签字或合并，未部署，未调用真实供应商。
