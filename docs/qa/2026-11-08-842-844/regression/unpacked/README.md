# qa844 回归包（原探针，未改失败）

固定证据 tip：`4e24170015629d61f92fbdc7889069359d7a7cea`（PR #844 复验当时的 head）。

本包是那一次独立探针的原件，供以后有新 tip 时复验。这次只打包，没有对任何新 tip 跑测试，没有改产品代码，没有提交仓库，没有调用供应商，没有开或评论 PR。

探针源码在出报告时随临时工作树删除。这里的 `tests/test_qa844_readonly_probe.py` 按当时执行版本逐字恢复。失败断言没有删、没有改成期望的错误行为。夹具是探针里内联字节的副本，探针本身仍不读这些文件。

探针 SHA-256：`d2ee34ec4299d18a3cf190e29204ea5787f86b355ae8c7db67119c37b5e380d4`

## 安全运行前提

必须同时满足，否则不要跑：

1. `GATE=1`。仓库 `tests/conftest.py` 会在此变量下拦截非本机 TCP 和 DNS，并去掉 `WAVESPEED_API_KEY` 与 `KIE_API_KEY`。
2. `PYTHONPATH` 指到本包的 `guard/`，让 `sitecustomize.py` 先加载。它拒绝打开文件名为 `passwd`、`shadow`、`.env`、`id_rsa*` 的路径。
3. 不读取真实敏感文件。不要为了“证明 XXE”去指向 `/etc`、`/proc`、家目录、密钥或 `.env`。探针里的 UTF-8 外部实体只用 pytest 的 `tmp_path` 临时 marker。产品夹具 `tests/fixtures/svg826/local_file.svg` 的属性文本里有 `file:///etc/passwd` 这几个字符；跑的时候必须留下探针自己的 `open` 替换和本 guard，确认没有打开该路径。本包不复制那份产品夹具。
4. 不出站，不调用 WaveSpeed，不打价格 API，不付费。`ClientSession` 在报价探针里会被换成一构造就失败的类。不要在浏览器或系统看图工具里打开本包的 SVG/二进制。
5. 把探针复制到被测 tip 的 `tests/test_qa844_readonly_probe.py` 再跑。它的 `ROOT_FIX` 指向同级 `fixtures/svg826`（产品夹具）。跑完删掉这份复制，不要提交。
6. 不要设置 `COMFYART_SKIP_NODE_TESTS`。这个探针本身不跑前端打包；若同进程收集了别的测试，缺 node 会让整个 pytest 会话失败，那是仓库 conftest 的行为。

## 以后怎么跑

在被测 tip 的干净检出里，且已能导入该检出的测试依赖时：

```bash
export GATE=1
export PYTHONPATH="/绝对路径/qa844-regression/guard${PYTHONPATH:+:$PYTHONPATH}"
unset WAVESPEED_API_KEY KIE_API_KEY
cp /绝对路径/qa844-regression/tests/test_qa844_readonly_probe.py tests/test_qa844_readonly_probe.py
python -m pytest -q --tb=short tests/test_qa844_readonly_probe.py
rm -f tests/test_qa844_readonly_probe.py
```

`run.sh` 只打印上述约束并在缺少 `QA844_TIP` 时退出。本轮没有执行它。

## 原 tip 上的实际结果

命令（`GATE=1`，guard 已加载）：

`python -m pytest -q --tb=short tests/test_qa844_readonly_probe.py`

结果：**4 passed，6 failed**，0 skipped，0.27s。原文见 `observed/4e241700-pytest.txt`。空体、UTF-16、估价键的补充观察见 `observed/4e241700-inline.txt`（同一次复验里的内联脚本，不是另一套断言）。

| 测试 | 原 tip |
| --- | --- |
| `test_probe_io_counters_on_safe_and_dangerous` | 通过。normal/external/local_file/entity 的 socket 与 open 增量为 0；entity 不调用 `fromstring` |
| `test_probe_xxe_utf8_rejected_before_parser` | 通过。临时 marker 未被打开 |
| `test_probe_boundaries_equal_and_over` | 通过 |
| `test_probe_download_headers_and_hash` | 通过。安全文本 SVG 可下载且带 attachment / CSP / nosniff；脚本 SVG 404 |
| `test_probe_classification_gaps_and_path_preview` | **失败**。animate 与 data URI image 已拒绝。`xml-stylesheet` 的 https 与 `fill="url(https://…)"` 均为 `normal` 且可下载。仅含 `<path>` 的文件是 `preview_failed` / `undrawable`，不是可辨预览 |
| `test_probe_utf16_doctype_and_invalid_encoding` | **失败**。UTF-16 DOCTYPE 为 `preview_failed`，原文可下载，解析器被调用（断言消息 `('preview_failed', 'malformed', True, 2)`） |
| `test_probe_clock_equality` | **失败，但是探针少给了一个时钟采样**。前两条已通过：最后一次检查等于 0.25 为 `normal`，刚超过 0.25 为 `too_slow`。第三条只给了 3 个值，第 4 次 `clock()` 产生 `StopIteration`。这不是产品缺陷。不要改这条断言来“修绿” |
| `test_probe_count_and_unknown_format` | **失败**。`count=1.5`（float）与 `count=True` 的 `block_reason` 为 `None`。`0`、`2`、字符串 `"1.5"` 为 `svgCount`。`tiff` 不拒绝，模型留在 2.5。点名 2.5 的 SVG 被改写成 2.6，没有 `svgEdit` |
| `test_probe_nonsvg_and_empty_are_saved` | **失败**。PNG 体没有抛 `WaveSpeedError`（`DID NOT RAISE`），因此同函数里的空体断言没跑到。内联观察确认空体也被存成 `preview_failed` 的 `.svg` |
| `test_probe_quote_fields` | **失败**。前四条已通过：价 0.07、`svg.model` 为 2.6、`n=1`、tier 含 `SVG` 与 `n=1`、计划步骤 count 为 1。失败点是 `svg_note` 含 `2.5`。下一条“顶层 model 等于 2.6”没跑到。内联观察里顶层没有 `model` 键 |

补充内联（同一 tip，socket 替换）：`xml-stylesheet.svg` 与 `fill-url-https.svg` 的 socket Δ=0、open Δ=0，状态仍是 `normal`，下载字节含 `https://evil.example`。

## 后续产品边界

这是给下一个 tip 的产品边界，**没有写回探针**。探针仍按上面的原断言失败。

- 只有通过安全校验的合法 SVG 可以下载。未通过校验的字节、非 SVG、空体，都不能变成可下载的 `.svg`。
- 正常 `<path>` 必须有可辨的栅格预览，不能只给“预览失败仍可下载”。
- `count` 必须是整数 1。`1.5` 必须可读拒绝（原探针期望 `svgCount`）。

新 tip 若只满足这三条，原探针仍可能在时钟采样、`count=True`、未知格式、旧模型改写、UTF-16、`svg_note` 含 2.5 等断言上失败。那些失败要单独记录，不要为了全绿去改本包里的探针。

## 夹具

`fixtures/` 与探针内联字节一致，探针运行时不读取它们。SHA-256 见 `fixtures/SHA256SUMS`。不要在普通查看器里打开。
