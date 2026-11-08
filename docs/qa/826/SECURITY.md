# #826 SVG 安全阈值

实现在 `api/svg_image.py`。生产调用 `admit(data)`，不传入自定义 limits。

| 阈值 | 值 | 超过以后 |
| --- | --- | --- |
| 文件大小 | 512 KiB (`MAX_BYTES`) | 拒绝，不解析，不下载 |
| 边长 | 1024 (`MAX_EDGE`) | 拒绝，不分配位图 |
| 像素面积 | 1024×1024 (`MAX_PIXELS`) | 拒绝，不分配位图 |
| 元素个数 | 2000 (`MAX_ELEMENTS`) | 拒绝 |
| 时长 | 0.25 秒 (`MAX_SECONDS`) | 拒绝，不提供下载 |

隔离方式（不是「没有弹窗」）：

- 脚本：拒绝 `script`、`foreignObject`、`on*`、`javascript:`。模块里没有 `eval` / `exec`。
- 外网：模块不引用 socket、urllib、HTTP 客户端。`http(s):`、`//`、`data:` 在遍历属性时拒绝。
- 本地文件：拒绝 `file:`、绝对路径和相对文件引用。`ElementTree` 没有自定义 opener。
- 实体：原始字节里出现 `DOCTYPE` / `ENTITY` / `CDATA` 时，在 `ElementTree.fromstring` 之前拒绝。
- 预览：只画 rect / circle / ellipse / polygon，输出 PNG。失败回退是 PNG，不是 SVG URL。
- 危险文件：`download is None`，缩略图 404，下载路由不返回原文。
- 已确认安全但画不出的文件：`preview_failed`，保留原始字节，提示「预览失败，原 SVG 仍可下载。」

SVG 任务显式使用 GPT Image 2.6 文生图，不修改全局默认模型。报价是既有静图价 + $0.02。medium 1k 为 0.05 + 0.02 = 0.07，不是新的供应商核价。本卡没有调用 WaveSpeed，也没有付费冒烟。
