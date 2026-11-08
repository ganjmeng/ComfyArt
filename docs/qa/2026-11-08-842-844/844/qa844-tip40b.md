# #844 候选只读复验

锁定 tip：`40b446002da7fec41ecc992fa8af4cad1995470c`  
分支：`cursor/svg-826-t2i-b424`  
提交说明：`fix(#826): render SVG only after netns and Landlock succeed`（2026-11-08 14:09:27 UTC）  
对照旧 tip：`4e24170015629d61f92fbdc7889069359d7a7cea`（基线已复现，本轮不重跑）  
探针：`d2ee34ec4299d18a3cf190e29204ea5787f86b355ae8c7db67119c37b5e380d4`，原样，跑前跑后 `cmp` 相同  
#842 对照：`2e7d7f21cb3b40519adb119fa712143f33aa81de`  
报告时刻：2026-11-08 22:42 北京时间。22:41 再次读取 PR head，仍是上面的完整 SHA。本轮没有漂移。

没有改产品代码，没有提交、评论、合并，没有供应商、价格 API 或付费调用。

## 日志

- 原探针：[qa844-tip40b-probe.log](/opt/cursor/artifacts/qa844-tip40b-probe.log)
- 真实隔离与默认测试：[qa844-tip40b-isolation.log](/opt/cursor/artifacts/qa844-tip40b-isolation.log)
- 独立补充（空体单独、部署路径）：[qa844-tip40b-supplement.log](/opt/cursor/artifacts/qa844-tip40b-supplement.log)

## 原探针（不是验收门槛）

命令在 `/tmp/qa844/tip40b`，`GATE=1`，`PYTHONPATH` 含回归包 `guard/`。Python 3.12.3，pytest 9.2.0。退出码 1。

`7 failed, 3 passed in 0.89s`，顺序 `FF..FFF.FF`。

通过：`test_probe_utf16_doctype_and_invalid_encoding`、`test_probe_xxe_utf8_rejected_before_parser`、`test_probe_nonsvg_and_empty_are_saved`。最后这项里 PNG 先抛错，空体断言也执行了，并没有被挡住。

### 测试工具错误

`test_probe_clock_equality` 仍在第三条 `run([0, 0, 0.25])` 上 `StopIteration`（探针只给了 3 个采样，`admit` 读 4 次）。前两条已通过：等于 0.25 秒为 `normal`，刚超过为 `too_slow`。

### 已知契约 / 旧期望，不记成新缺陷

| 失败 | 本 tip 实际 | 归类 |
| --- | --- | --- |
| 分类第 162 行要 path 状态 `normal` | `stylesheet` 与 `fill=url(https)` 已是 `rejected` 且无下载。path 为 `transparent`，有 PNG | 探针把透明背景的已绘制 path 要求成 `normal`。可辨预览见补充，不因为状态词失败 |
| count 整表 | `count=1.5`、`True`、`0`、`2`、`"1.5"` 都是 `svgCount`。差异只剩 `tiff_error=None`、tiff 模型留在 2.5、点名 2.5 的 SVG 被改到 2.6 且没有 `svgEdit` | 1.5 已按整数规则拒绝。tiff 与“必须留在 2.5”仍是探针自己的契约，和本 tip「SVG 走 2.6、不改全局默认」相反 |
| 报价第 374 行 | 前面的 0.07、`svg.model` 为 2.6、`n=1`、note 不含 `2.5` 已通过。失败是顶层 `model` 为 `None` | 顶层 `model` 是 #842 的字段，本 tip 没加 |
| 边界第 235 行 | 正好 512 KiB 的非 XML：`malformed` 且 `download is None` | 旧探针要求仍可下载。新规则是畸形拒绝且不下载，这项符合新规则 |
| IO 计数第 110 行 | `external.svg` 在 `fromstring` 之前被拒绝，解析次数没有 +1。此前 normal 的 socket/open 为 0 已通过 | 外链提前拒绝，不是解析器被调用 |
| 下载 HTTP 第 333 行 | `text.svg` 返回 404，没走到响应头断言 | 这次原探针带着会拦截 `passwd` 的 guard。子进程对 `/etc/passwd` 的 Landlock 探针得到无 errno 的 `PermissionError`，产品只把 `EACCES`/`EPERM` 当成隔离成功，于是父进程拒绝下载。去掉 guard 后，同一份 text 在真实隔离里是 `preview_failed` 且可下载。404 是 guard 和产品探针撞车，不是安全文件在隔离成功时不能下载 |

## 新验收（独立补充 + 部署路径）

补充进程没有加载 guard，避免挡住 Landlock 的 `open("/etc/passwd")`。`GATE=1` 只影响导入了 conftest 的父进程；子进程是新的解释器，连接探针是它自己的 netns。没有读取 canary 或 passwd 的内容。`filesystem_probe=EACCES` 表示打开被拒绝。

部署入口 `svg_raster.isolated_admit` → `svg_worker.py`。子进程回传：

- `rendered=True`
- `network_isolated=True`，`network_probe=ENETUNREACH`（对 `192.0.2.1:9` 与 `127.0.0.1:9` 的连接不可达）
- `filesystem_isolated=True`，`filesystem_probe=EACCES`
- `rlimit_as=805306368`（768 MiB），`rlimit_cpu=3`，`rlimit_fsize=2097152`，`alarm_seconds=3`
- `rlimit_is_network_isolation=False`

这是子进程真实回传，不是把 rlimit 或 mock 当成断网。作者测试 `test_isolated_path_preview_requires_real_net_and_file_sandbox` 调用的也是这个入口，3 项里它通过（整组 `3 passed in 1.71s`）。同组的 `test_isolation_failure_does_not_parse_or_render` 用注入的 `refuse()`，只证明代码在“隔离函数返回失败”时不渲染。那是 mock，不能代替上面的 ENETUNREACH。本环境里真实 netns+Landlock 成功了，所以没有再制造一次真实的隔离创建失败。

| 输入 | 进程内 `admit` | 部署路径 `isolated_admit` |
| --- | --- | --- |
| 空体 | `rejected/empty`，无下载 | 同，无下载。单独跑，不依赖 PNG |
| PNG 体 | `rejected/unsupported_encoding`，无下载 | 同 |
| 未闭合 XML | `rejected/malformed`，无下载 | 同 |
| UTF-16 DOCTYPE | `rejected/unsupported_encoding`，无下载 | 同。原探针还证明没调用 `fromstring` |
| CSS `url(https://…)` | `rejected/external`，无下载 | 同 |
| `xml-stylesheet` | `rejected/stylesheet`，无下载 | 同 |
| `script.svg` | `rejected/script`，无下载 | 同，且 `rendered=True` 只表示隔离已建立后才做策略判断 |
| 只有 `<text>` | `preview_failed`，可下载，预览是 PNG | 同 |
| `path.svg`（`#00aa00` 方路径） | `transparent`，(16,16) 为 `(0,170,0,255)`，角点 alpha 0 | 同，下载保留 |
| `normal.svg` | `normal`，可下载 | 同 |

`count`：`1` 与 `"1"` 放行；`1.5`、`1.0`、`True`、`0`、`2`、`"1.5"` 为 `svgCount`。

内存和时限：成功的子进程回传了上述 rlimit 与 alarm，说明设置发生在这条渲染路径上。没有另造撑爆内存或卡死解析的样本，所以“超限会杀掉子进程”仍是代码路径（`isolated_admit` 在超时或非 0 退出时拒绝下载），不是本轮砸出来的实测。

## #842 `2e7d7f21` 集成

`git merge-tree`（base `fe342cea`，ours `2e7d7f21`，theirs `40b44600`）有冲突，不能当成已经集成：

`api/mcp_tools/canvas.py`、`bot/plan_quote.py`、`src/botCommands.ts`、`src/generate.ts`、`src/locales/en.json`、`src/locales/zh.json`、`src/ui/GenSettings.tsx`。

`api/curated_models.json` 与 `tests/test_svg_826.py` 不在冲突名单。本 tip 没有改 curated，目录默认仍是 `openai/gpt-image-2.5-flare/text-to-image` 与 `.../edit`。`test_default_model_stays_25_flare` 已不在这个 tip 上（pytest 报 not found）。替代测试 `test_svg_does_not_replace_the_configured_default` 通过：SVG 路由到 2.6，普通 Auto 等于当前 curated 默认，SVG 不改写该默认。因此这份测试不会把默认锁死回 2.5。真正合并仍要先解决上面 7 个冲突，再在合入结果上复验默认是否仍是 2.6。

`bot/guide.py` 第 97 行 GIF 段仍写稳定默认是 2.5；第 106 行 SVG 段写显式使用 2.6 且不改全局默认。`svg_note` 不再写“默认仍是 2.5”。

## 本 tip 结论

新规则里已在本环境跑通的部分：危险内容、空体、非 SVG、畸形 XML、UTF-16、CSS URL、处理指令都拒绝且无下载；安全但画不出的 text 可下载；path 在真实 netns+Landlock 里预览到绿色像素；`count=1.5` 可读拒绝。隔离创建在这台机器上成功，外连探针是 `ENETUNREACH`，本地打开探针是 `EACCES`，rlimit 回传值不是断网证据。

未完成：与 #842 的冲突还在；没有真实供应商调用；HTTP 下载头在带 guard 的原探针里没再看到 200。原探针 7 失败不作为门槛。
