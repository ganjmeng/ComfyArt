#868 扩图滑块钉住位置 / Krea 2 Turbo 下拉（左右对比 main）

$0 mocked local shots. Left is main (`058e8447`); right is this PR. Raw GitHub URLs in the PR body are pinned to the tip SHA and embedded as images.

This PR does **not** change SVG / LAN HTTP preview, so there is no `03-svg-lan-http-lr.png`.

| 对比 | 左 main | 右 PR | 左右对比 |
| --- | --- | --- | --- |
| 扩图缩放滑块 1× / 2× / 3×（左随 pads 重算会跳动，右在按下期间钉住） | [01-slider-1x/2x/3x-before-main.png](01-slider-1x-before-main.png) | [01-slider-1x/2x/3x-after-pr.png](01-slider-1x-after-pr.png) | [01-slider-lr.png](01-slider-lr.png) |
| 模型下拉，Krea 2 Turbo 只出现在右侧（Midjourney 与 Ideogram 之间） | [02-krea-dropdown-before-main.png](02-krea-dropdown-before-main.png) | [02-krea-dropdown-after-pr.png](02-krea-dropdown-after-pr.png) | [02-krea-dropdown-lr.png](02-krea-dropdown-lr.png) |

## How to reshoot

Build `dist` in both worktrees (do not commit it), then:

```bash
MAIN_ROOT=/tmp/wt887-main /workspace/ca-venv/bin/python docs/qa/868/shoot_lr.py
```

`boot_app.py` serves each tree on :8871 / :8872 with a stub host and the local WaveSpeed catalog fixture. Keys are unset except a fake in-process value that is never printed.

Notes for anyone reading the frames:

- Slider shots use canvas zoom **50%**. At 100% the panel is already clamped to the host `EDGE`, so main and the PR look the same even when `held` works.
- The PR column is captured **mid-pointer-down** (`held` + `setPointerCapture`). After release the panel still jumps to the computed position, which is intended.
- The model row's native `title={m.id}` tooltip is not visible in screenshots (the in-row description is). Auto is off so rows are not greyed.
