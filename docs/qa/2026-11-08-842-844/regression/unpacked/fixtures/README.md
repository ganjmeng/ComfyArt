# 内联复现夹具

这些文件是 `tests/test_qa844_readonly_probe.py` 里当时内联字节的副本。探针没有改成读取它们。复验仍以探针源码为准。

不要用浏览器、系统看图或 XML 工具打开。只在 `GATE=1` 且 guard 生效的探针里送进 `admit()` / `_download()`。

| 文件 | 探针位置 | 原 tip `4e241700` 的结果 |
| --- | --- | --- |
| `xml-stylesheet.svg` | `test_probe_classification_gaps_and_path_preview` 的 stylesheet | `normal`，可下载，socket/open 增量 0 |
| `fill-url-https.svg` | 同函数的 fill_url。这是属性上的 CSS `url(https://…)`，不是 `<style>` 块 | `normal`，可下载，socket/open 增量 0 |
| `path-only.svg` | 同函数的 path_only | `preview_failed` / `undrawable`，预览类型 `image/png`，原件可下载 |
| `animate.svg` | 同函数，断言在失败点之前已通过 | `rejected` / `script`，无下载 |
| `data-image.svg` | 同函数，断言在失败点之前已通过 | `rejected` / `external`，无下载 |
| `utf16-doctype.bin` | `test_probe_utf16_doctype_and_invalid_encoding`。内部实体名为 `x`，没有 file:// | `preview_failed`，原文可下载，解析器被调用 |
| `invalid-encoding.bin` | 同函数第二个输入 | 断言没单独打印；`fromstring` 计数为 2，说明它也被解析。补充观察是 `preview_failed` / `malformed` 且可下载 |
| `nonsvg-body.bin` | `test_probe_nonsvg_and_empty_are_saved` 的 PNG 体（8 字节 PNG 头 + 16 个 0） | 未抛 `WaveSpeedError`，被存成 `.svg`，状态 `preview_failed` |
| `empty-body.bin` | 同函数的空体 | pytest 没跑到这条，因为 PNG 先失败。内联观察：存成 `.svg`，状态 `preview_failed`，长度为 0 |
| `html-root.bin` | 同函数，在 PNG 失败之后，原 pytest 没跑到 | 内联观察未单独再打。探针期望 `svgRejected` |
| `count-1.5.json` | `block_reason(..., count=1.5)`。探针用的是 Python float，不读这个 JSON | `block_reason` 返回 `None`，没有 `svgCount` |

产品仓库里的 `tests/fixtures/svg826/local_file.svg` 不在本目录。它的文本含 `file:///etc/passwd`。不要把它复制进来，也不要让解析器打开那个路径。
