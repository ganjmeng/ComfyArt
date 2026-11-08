# 真实失败实测（同一 tip，只读）

锁定并实际运行的提交：`40b446002da7fec41ecc992fa8af4cad1995470c`  
内核：`6.12.113+`。云端结果不能外推到未提供的部署环境。  
封存探针仍是 `d2ee34ec4299d18a3cf190e29204ea5787f86b355ae8c7db67119c37b5e380d4`，本轮没有改它，也没有改产品。  
没有合并、解决冲突、提交或评论。没有供应商、付费或另行发起的外连。没有读取敏感文件内容。

完整日志：[qa844-tip40b-kernel-fail.log](/opt/cursor/artifacts/qa844-tip40b-kernel-fail.log)

## 漂移（未测）

本轮开始时和结束时，PR #844 的远端 head 都是 `f36fa178ae8cc48ee2cbd867ac66629ef7191296`（`updated` 2026-11-08 14:43:21 UTC）。那一提交不在本轮运行范围内。

## 怎么造成失败

`setpriv --no-new-privs` 之后，本机 `unshare(CLONE_NEWUSER|CLONE_NEWNET)` 仍返回 0。单靠 no-new-privs 造不出 EPERM。没有改宿主 sysctl，也没有装 seccomp 以外的全局策略。

实际使用的是只作用于该子进程的 seccomp-bpf：默认允许，仅对一个系统调用返回 `EPERM`。这不是 Python 里替换 `refuse()`。父进程 `isolated_admit` 没有钩子，所以 harness 直接执行与它相同的程序 `python .../api/svg_worker.py`（观察导入时多了 `-v`）。产品源码未改。

`strace` 不在这台机器上。导入证据来自 `python -v`。

## 目标 1：隔离创建失败

| 用例 | 内核结果 | 渲染 |
| --- | --- | --- |
| seccomp 拦截 `unshare`（272） | 子进程 pid 4484 的同路径复跑：退出码 0，`network_probe=EPERM`，`network_isolated=false`，`filesystem_probe=null` | `rendered=false`，`download=null`，`preview=null`，`reason=isolation_unavailable`。`-v` 里没有 `svg_raster` 或 `PIL`。结束后没有 `svg_worker.py` |
| seccomp 拦截 `landlock_create_ruleset`（444） | `network_probe=ENETUNREACH`（子进程里原有的 192.0.2.1:9 / 127.0.0.1:9 探针，无额外流量），`filesystem_probe=EPERM` | `rendered=false`，无下载、无预览。但 `-v` 已出现 `svg_raster.py` 和 `PIL`。`_render` 先 `_load_raster()`，再 `establish_filesystem()`。文件隔离失败时绘制模块已经加载，`admit` 没有被调用 |

网络这条满足「失败则不导入、不绘制、不给下载」。文件这条只满足「不调用 admit、不给下载」，不能满足「零加载」。`test_isolation_failure_does_not_parse_or_render` 的 `refuse()` 注入不是这次的证据。

## 目标 2：资源上限后回收

| 用例 | 结果 |
| --- | --- |
| 产品自己的 `alarm(3)`。stdin 保持打开，子进程停在 `read`。外层 8 秒只用于防止失控，没有打到 | 退出码 -14，`SIGALRM`。`timed_out_outer=false`。stdout 长度 0。`-v` 无 `svg_raster`/`PIL`。`workers_after` 为空。这是部署代码里的闹钟，不是 harness 改小的时限 |
| harness：`prlimit --as=33554432`（32 MiB，低于产品 768 MiB）。argv 不含 `-v` | 退出码 1。`svg_worker.py:34` `resource.setrlimit(RLIMIT_AS, (768MiB, 768MiB))` 抛出 `ValueError: not allowed to raise maximum limit`。无 JSON、无下载。进程已被 `wait` 回收，结束后无 `svg_worker.py`。这是外层硬上限让产品抬高上限失败，不是 768 MiB 把绘制进程打死 |
| 产品 `RLIMIT_CPU=3`、`RLIMIT_FSIZE=2MiB` | 未触发。真实 worker 不会空转 3 秒 CPU，也不会向普通文件写超过 2 MiB。本轮没有加空转或 fork bomb，因此这两项不能签 |

每次启动计数都是 1 个 `svg_worker.py`（pid 见日志）。运行后相关集合里只剩 harness 自己，没有孤儿。

## 可签 / 未验

可签，且只针对这台云主机上的 `40b446002da7fec41ecc992fa8af4cad1995470c`：

- 内核 `unshare` EPERM 时，worker 不导入绘制模块，不产出下载。
- 内核 Landlock 创建 EPERM 时，不调用 `admit`、不产出下载；绘制模块已被导入。
- 产品 `alarm(3)` 以 `SIGALRM` 终止并被回收，发生在读取 stdin 期间，绘制未开始。
- 外层 32 MiB 地址空间使产品 `setrlimit` 失败并退出，无下载。这是标明过的 harness 参数。

未验：

- 部署环境本身（未提供，未连接）。
- 不靠 seccomp、在本机用更低权限自然得到 `unshare` EPERM。no-new-privs 做不到。
- 产品 768 MiB / CPU 3 秒 / 输出 2 MiB 在绘制过程中把进程信号杀掉。
- 新 head `f36fa178ae8cc48ee2cbd867ac66629ef7191296`。
- 与 #842 的 7 个冲突文件。本轮没有合并。
