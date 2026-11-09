# #826 三态界面证据（LOCAL FIXTURE / mock）

这三张图是测试夹具里的**真实产品组件**渲染：Tldraw 画布、`ImageToolbar`、生成卡片（`GeneratorShape`）。页顶棕条写着 `LOCAL FIXTURE · mock · 不是供应商结果`，用来标明夹具，不是仿造的卡片。

它们**不是**供应商出图，**不是**部署环境或线上冒烟。整张 #826 仍是 HOLD。`40b44600` 上的旧说明（path 不能预览、畸形 SVG 仍可下载）不要当作当前头的证据。

生成这三张图的实现是 `f36fa178ae8cc48ee2cbd867ac66629ef7191296`（`tests/test_svg826_canvas_tip.py` 与 `tests/js/svg826/`）。像素来自本地 `admit()`，没有供应商请求。

| 图 | Fixture | 当前行为 |
| --- | --- | --- |
| `01-path-preview.png` | `tests/fixtures/svg826/path.svg` | 正常 path 有可辨的本地 PNG 预览，工具条可以下载 |
| `02-preview-failed-download.png` | `tests/fixtures/svg826/text_only.svg` | 安全但画不出像素（纯 text）：预览失败，原 SVG 仍可下载 |
| `03-rejected-no-download.png` | `tests/fixtures/svg826/script.svg` | 恶意脚本：生成卡片拒绝，没有下载 |

畸形或不合法的 SVG（例如 `truncated.svg`）与恶意文件一样拒绝，不提供下载。只有通过完整安全校验、但本地栅格画不出像素的文件才保留下载。

安全准入和子进程隔离见 `docs/qa/826/SECURITY.md`。那份文档是本地策略与测试记录，同样不是供应商或部署实证。
