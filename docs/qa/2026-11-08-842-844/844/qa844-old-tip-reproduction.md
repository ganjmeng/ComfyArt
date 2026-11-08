# 旧 tip 复跑：重建探针 `d2ee34ec`

- 只跑旧 tip `4e24170015629d61f92fbdc7889069359d7a7cea`
- 新 tip 未跑。收到确定 SHA 后再用同一脚本复验
- 探针未改。产品代码未改。没有提交、评论、合并，没有供应商调用
- 日志：[qa844-old-tip-reproduction.log](/opt/cursor/artifacts/qa844-old-tip-reproduction.log)
- 时刻：2026-11-08 21:55:23 北京时间（13:55:23 UTC）

## 结论

重建脚本可以在旧 tip 上复现原先那次 4 通过 / 6 失败。顺序仍是 `.FF..FFF.F`，耗时 0.27s。脚本 SHA-256 在打包件、复制后、pytest 之后都是：

`d2ee34ec4299d18a3cf190e29204ea5787f86b355ae8c7db67119c37b5e380d4`

失败不全是缺陷。本趟按日志拆开：5 项是产品失败，1 项是测试工具错误，若干断言是待确认契约或本趟没跑到。

## 环境与命令

| 项 | 值 |
| --- | --- |
| 检出 | `/tmp/qa844/oldtip`，detached HEAD，`git status` 只有未跟踪的探针副本 |
| Python | 3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0] |
| pytest | 9.2.0（插件 pytest-asyncio 1.4.1.post1，`asyncio_mode=auto`） |
| Node | v22.23.4。工作树里 `npm ci --ignore-scripts` 只为满足 conftest 对 `rolldown` 的检查 |
| `GATE` | `1`。conftest 拦截非本机 TCP/DNS，并去掉付费密钥 |
| `PYTHONPATH` | `/opt/cursor/artifacts/qa844-regression/guard:/tmp/qa844/guard`。先加载回归包里的 guard，拒绝打开名为 `passwd`、`shadow`、`.env`、`id_rsa*` 的路径 |
| `WAVESPEED_API_KEY` / `KIE_API_KEY` | 均未设置 |
| 解释器 | `/tmp/qa844/venv/bin/python` |

```bash
cd /tmp/qa844/oldtip
GATE=1 PYTHONPATH=/opt/cursor/artifacts/qa844-regression/guard:/tmp/qa844/guard \
  /tmp/qa844/venv/bin/python -m pytest --tb=short -ra tests/test_qa844_readonly_probe.py
```

退出码 1。没有出站失败，也没有 guard 拒绝记录。pytest 汇总：`6 failed, 4 passed in 0.27s`。

## 脚本哈希

| 时点 | SHA-256 |
| --- | --- |
| 打包件 `/opt/cursor/artifacts/qa844-regression/tests/test_qa844_readonly_probe.py` | `d2ee34ec4299d18a3cf190e29204ea5787f86b355ae8c7db67119c37b5e380d4` |
| 复制进工作树之后、pytest 之前 | 同上 |
| pytest 之后，工作树副本与打包件 `cmp` | 相同，`CMP_AFTER_OK` |

## 通过（与原记录一致）

- `test_probe_io_counters_on_safe_and_dangerous`
- `test_probe_xxe_utf8_rejected_before_parser`
- `test_probe_boundaries_equal_and_over`
- `test_probe_download_headers_and_hash`

## 失败分类

### 测试工具错误

`test_probe_clock_equality`，`tests/test_qa844_readonly_probe.py:263`。

`run([0, 0, 0.25])` 在 `api/svg_image.py:524` 的第四次 `clock()` 上 `StopIteration`。这条调用只准备了 3 个采样，`admit()` 会读 4 次。同函数前两条已经通过：最后一次检查等于 0.25 时结果是 `normal`，刚超过 0.25 时是 `too_slow`。这不是产品缺陷，不计入漏洞。

### 产品失败

这些是本趟日志里直接打出来的行为，对着已经写明的规则（外链/DOCTYPE 不放行下载，或后续边界：只下载通过安全校验的 SVG、正常 path 要有可辨预览、`count` 必须是整数 1 且 1.5 要可读拒绝）。这里不把它们写成“已证明的利用”。

| 断言 | 本趟观察 | 分类 |
| --- | --- | --- |
| `xml-stylesheet` 的 https（第 160 行） | `('normal', 'normal', True)`，原文可下载 | 产品失败。处理指令里的 https 没有被拒绝 |
| `fill="url(https://…)"` | 失败消息里的 `observed`：`('normal', 'normal', True)`。第 161 行还没执行 | 产品失败。属性上的 CSS `url(https)` 没有被拒绝，原文可下载 |
| 仅 `<path>` | `observed`：`('preview_failed', 'undrawable', True, 'image/png')`。第 162 行还没执行 | 产品失败。没有可辨预览。这是该 tip 已写明的绘制范围限制，和对“正常 path 须有可辨预览”的边界不符 |
| UTF-16 DOCTYPE（第 181 行） | `('preview_failed', 'malformed', True, 2)`。状态是预览失败，原文可下载，`fromstring` 被调用 | 产品失败。字节过滤没挡住这种 DOCTYPE，也没有在解析前拒绝。夹具是内部实体 `x`，本趟没有证明读到了外部文件 |
| `count=1.5`（float） | `None`，不是 `svgCount` | 产品失败。`int(1.5)==1`，没有可读拒绝 |
| PNG 体当 SVG 任务下载（第 302 行） | `Failed: DID NOT RAISE WaveSpeedError` | 产品失败。非 SVG 没有被拒绝。同函数里的空体断言没有跑到 |

`test_probe_quote_fields` 第 373 行：`svg_note` 含「默认模型仍是 GPT Image 2.5 Flare」/ “The default model stays GPT Image 2.5 Flare.”。同函数前面的断言已通过，估价是 0.07，`svg.model` 为 2.6，`n=1`。这是文案和实际路由并立，属于已复现的文案不一致，不是安全漏洞。下一条“顶层 `model` 等于 2.6”没有跑到。

### 待确认契约

探针期望和这个 tip 已经写明的行为不一致，或者日志被截断、断言没执行到。不升格为缺陷。

| 项 | 本趟能确定的 | 为什么待确认 |
| --- | --- | --- |
| `count=True` | 结果是 `None`，探针期望 `svgCount` | 已宣布的边界只点名 1.5。布尔值是否必须拒绝，契约没写死 |
| `output_format=tiff` | `tiff_error` 为 `None`。探针期望 `svgEdit` | 非 svg 不进入 SVG 路由。探针把期望种类写成 `svgEdit`，这不是产品文档里的拒绝码。`tiff_model` 在本趟被 pytest 截掉，不另判 |
| 点名 2.5 的 SVG | `old_model` 实为 `openai/gpt-image-2.6-flare/text-to-image`，探针期望留在 2.5 并 `svgEdit` | 这个 tip 的实现就是把 SVG 改到 2.6。失败说明探针期望和该契约相反，不能把“没有留在 2.5”叫缺陷。`old_error` 被截断，不另判 |
| `count` 0、2、字符串 `"1.5"` | pytest 把它们算进 omitted identical items | 与 `svgCount` 一致，拒绝已发生 |
| 无效编码 `\xff\xfe\x00\x00not-xml` | `fromstring` 总次数为 2，说明这次也进了解析器 | 断言消息没有单独给出它的 status 和是否可下载。本趟不写它的下载结论 |
| 空体 | 未执行 | PNG 断言先失败，空体那条 `pytest.raises` 没跑到 |
| animate、data URI image | 第 158–159 行已通过，失败停在第 160 行 | 这两类按探针期望被拒绝。`data_image` 的值在字典打印里被省略，通过与否以失败行号为准 |

## 本趟没有做的事

没有跑 `18abdffb` 或任何更新的 tip。没有改探针，没有把失败断言改成与观察值一致。没有第二遍 `-vv`。截断字段保持截断。
