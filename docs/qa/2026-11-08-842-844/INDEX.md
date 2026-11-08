# 2026-11-08 QA 证据索引

这是本轮 QA 材料的归档，不是产品代码，也不是整个团队的同步声明。真实供应商生成不由这次归档执行，费用未知。

归档基线是当时的 `main` `fe342cea4b34c095285e90edc4b13da77d89a315`。没有修改 #842 / #844 的开发分支，没有合并，没有强推。

北京时间以各报告内的时间为准。本索引编写时的归档动作在 2026-11-09 早晨（UTC 2026-11-08 夜间）完成。

## 状态词

- **PASS**：该报告在其 tip 上对所写范围给出的通过。
- **HOLD**：证据不足或验收未完成，不是把功能判死。
- **未测**：没有在那个 tip 上跑。
- **工具错误**：探针或环境自己的失败，不作整卡全绿门槛。

封存探针 SHA-256：`d2ee34ec4299d18a3cf190e29204ea5787f86b355ae8c7db67119c37b5e380d4`。它是重建后的只读探针，时钟 `StopIteration` 是工具错误。原探针没有全绿，也不把全绿当门槛。探针文件未改。

回归 zip SHA-256：`e8e926ad52f875ff97539290cb09e9e59e87756f2ae5c9735c5074623a24f639`。推送前只做了内容扫描，没有运行。

## #844 SVG

| 本地 artifact | 仓库路径 | tip | 判定 |
| --- | --- | --- | --- |
| `/opt/cursor/artifacts/qa-844.md` | [844/qa-844.md](844/qa-844.md) | `4e24170015629d61f92fbdc7889069359d7a7cea` | M02/S01/S05 PASS；其余 HOLD；真实供应商未跑 |
| `/opt/cursor/artifacts/qa844-old-tip-reproduction.md` | [844/qa844-old-tip-reproduction.md](844/qa844-old-tip-reproduction.md) | 同上 | 重建探针复现 4 通过 / 6 失败 |
| `/opt/cursor/artifacts/qa844-old-tip-reproduction.log` | [844/qa844-old-tip-reproduction.log](844/qa844-old-tip-reproduction.log) | 同上 | 日志 |
| `/opt/cursor/artifacts/qa844-tip40b.md` | [844/qa844-tip40b.md](844/qa844-tip40b.md) | `40b446002da7fec41ecc992fa8af4cad1995470c` | 新规则多项在云端跑通；与 #842 的 7 文件冲突未合 |
| `/opt/cursor/artifacts/qa844-tip40b-probe.log` | [844/qa844-tip40b-probe.log](844/qa844-tip40b-probe.log) | 同上 | 原探针 3 通过 / 7 失败 |
| `/opt/cursor/artifacts/qa844-tip40b-isolation.log` | [844/qa844-tip40b-isolation.log](844/qa844-tip40b-isolation.log) | 同上 | 含一次因过期测试名而未收集的尝试，以及随后 3 passed |
| `/opt/cursor/artifacts/qa844-tip40b-supplement.log` | [844/qa844-tip40b-supplement.log](844/qa844-tip40b-supplement.log) | 同上 | 空体、危险类、path 像素、真实 `isolated_admit` |
| `/opt/cursor/artifacts/qa844-tip40b-kernel-fail.md` | [844/qa844-tip40b-kernel-fail.md](844/qa844-tip40b-kernel-fail.md) | 同上 | 内核 EPERM / SIGALRM 可签；CPU 与 FSIZE 未验 |
| `/opt/cursor/artifacts/qa844-tip40b-kernel-fail.log` | [844/qa844-tip40b-kernel-fail.log](844/qa844-tip40b-kernel-fail.log) | 同上 | 日志 |
| `/tmp/qa844/kernel_fail_harness.py` | [844/harness/kernel_fail_harness.py](844/harness/kernel_fail_harness.py) | 同上 | harness，不是封存探针 |
| `/opt/cursor/artifacts/qa844-regression.zip` | [regression/qa844-regression.zip](regression/qa844-regression.zip) | 旧 tip 探针包 | 未运行 |
| `/opt/cursor/artifacts/qa844-regression/` | [regression/unpacked/](regression/unpacked/) | 同上 | 含 probe、guard、`run.sh` |

云端限制：隔离失败用的是该子进程 seccomp 返回的真实 `EPERM`。`setpriv --no-new-privs` 在这台云主机上拦不住 `unshare`。768 MiB / CPU 3 秒 / 2 MiB 输出没有被绘制负载打中。这些结果不能外推到未提供的部署环境。

未测：归档时远端 #844 head 已是 `f36fa178ae8cc48ee2cbd867ac66629ef7191296`，本包没有跑它。

## #842

| 上传件 | 仓库路径 | tip | 判定 |
| --- | --- | --- | --- |
| `qa-842-fbe28e7f_f1d8.md` | [842/qa-842-fbe28e7f.md](842/qa-842-fbe28e7f.md) | `fbe28e7f11ef52ef9aa22176d5b9c9e6ced0d233` | HOLD |
| `qa-842-a59b683b_313b.md` | [842/qa-842-a59b683b.md](842/qa-842-a59b683b.md) | `a59b683bdd438a576adbb9a0c984ba4649df7bd8` | HOLD |
| `qa-842-gif-api_dbf8.md` | [842/qa-842-gif-api.md](842/qa-842-gif-api.md) | `2e7d7f21cb3b40519adb119fa712143f33aa81de` | HOLD |
| `qa-842-2e7d7f21_74bf.md` | [842/qa-842-2e7d7f21.md](842/qa-842-2e7d7f21.md) | 同上 | 默认路由 mock 可签；静图 GIF AC 未完成。副本有一处脱敏，见 [REDACTIONS.md](REDACTIONS.md) |

与 #844 `40b44600` 的 merge-tree 有 7 个冲突文件，本归档不解决。

缺项：报告里的 `/tmp/qa842-ac.txt`、`/tmp/qa842-editgif-probe.txt` 和 `artifacts/qa-842-gif-api/` 不在本环境，没有补造。

## #843 与 #707

历史证据板已经在 PR #843 和 #707 评论里。本目录不重传那些图，也不混入已撤回的 Qwen RIGHT、弃用 wash/new19 或海报 cover。

- 审计原文：[843/qa-843-review.md](843/qa-843-review.md)。历史图源标注 PASS；当前四技能真实链路 HOLD。
- 盘点原文：[707/qa-707-evidence-inventory.md](707/qa-707-evidence-inventory.md)。四技能真实链路 HOLD。
- 10f740f9 四板：<https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6721987448>
- 320949dc 的 LinkedIn 修订板：<https://github.com/ganjmeng/ComfyArt/issues/707#issuecomment-6722223485>
- 固定树前缀：`https://raw.githubusercontent.com/ganjmeng/ComfyArt/10f740f9d465e944a1881b6db76850f0e7aaa394/docs/design/707/evidence-audit/` 与 `https://raw.githubusercontent.com/ganjmeng/ComfyArt/320949dc129da0ad47e86f0d1f356a0e4038e1de/docs/design/707/evidence-audit/`

缺项：`/workspace/qa-843/` 与 `/workspace/qa-843/320949dc/` 的四张本机 PNG 不在本环境，没有伪造。盘点里的 `/workspace/704-lr/` 本机包同样未复制。

## 准备文档

| 上传件 | 仓库路径 | 说明 |
| --- | --- | --- |
| `qa-825-phase2-prep_041b.md` | [prep/qa-825-phase2-prep.md](prep/qa-825-phase2-prep.md) | 用例准备，不是 PASS |
| `qa-826-security-prep_3e80.md` 与 `qa-826-security-prep_140c.md` | [prep/qa-826-security-prep.md](prep/qa-826-security-prep.md) | 两份上传 SHA-256 同为 `226ccc94cb29285a607814e21a5c91d27b73d45e3aaa88bcbfd653233e1ff438`，只存一份 |

## 关联

- #842 <https://github.com/ganjmeng/ComfyArt/pull/842>
- #843 <https://github.com/ganjmeng/ComfyArt/pull/843>
- #844 <https://github.com/ganjmeng/ComfyArt/pull/844>
- #707 <https://github.com/ganjmeng/ComfyArt/issues/707>
- #825 <https://github.com/ganjmeng/ComfyArt/issues/825>
- #826 <https://github.com/ganjmeng/ComfyArt/issues/826>
