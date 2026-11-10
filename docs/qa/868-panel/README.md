#868 扩图面板避让（松手后不再挡住缩放条 /「生成」）

$0 mocked local shots, localhost only. After dragging the expand scale slider and releasing, the ModePanel is repositioned once (150ms move transition).

Canvas zoom is 50% so 3× pads still fit in frame.

| 松手后 | 文件 |
| --- | --- |
| 缩放 1×，1440×900（全画布） | [01-after-release-1x.png](01-after-release-1x.png) |
| 缩放 2×，1440×900（全画布） | [02-after-release-2x.png](02-after-release-2x.png) |
| 缩放 3×，1440×900（右把手 + 面板边裁切） | [03-after-release-3x.png](03-after-release-3x.png) |
| 缩放 3×，窄视口 1280×800（右把手 + 面板边裁切） | [04-after-release-3x-1280.png](04-after-release-3x-1280.png) |
| 缩放 3×，窄视口 1280×800（整屏，含底部工具栏和右下角缩放栏） | [05-after-release-3x-1280-full.png](05-after-release-3x-1280-full.png) |

## How to reshoot

Build `dist` in this worktree (do not commit it), then:

```bash
/workspace/ca-venv/bin/python docs/qa/868-panel/shoot_after.py            # retake 3× crops + 1280 full-viewport
/workspace/ca-venv/bin/python docs/qa/868-panel/shoot_after.py --all      # also reshoot 1× / 2×
/workspace/ca-venv/bin/python docs/qa/868-panel/shoot_after.py --full-only  # only the uncropped 1280 full-viewport frame
```

`docs/qa/868/boot_app.py` serves the tree on 127.0.0.1:8868 with a stub host and the local WaveSpeed catalog fixture. Keys are unset except a fake in-process value that is never printed. No LAN / internal addresses.

## Notes

- 1× and 2× sit on the **right** of the expand box at 280px with a 16px gap. Handles, the bottom dock, and the zoom bar stay clear (≥12px). The 「生成」 button is fully visible.
- If 280px + 16px fits neither side, the panel narrows to **220px** and retries right, then left, staying ≥12px from the viewport edges. Ratio chips may wrap; the 缩放比例 slider + value, the size/price line, and 取消 / 生成 stay on one row with no ellipsis.
- If 220px still fits neither side, the panel **docks** to the viewport right edge (220px) and shifts vertically to stay ≥12px from the expand box's right drag handle when a slot exists. Only if no vertical position works may it cover the handle. 「生成」, the dock, and the zoom bar are never covered (≥12px).
- Observed: 3× at 1440 is **220px on the right of the box** (handle clear). 3× at 1280 **docks** at 220px; no vertical slot clears the handle, so the handle is covered, but 「生成」 / dock / zoom bar stay clear.
- Host is `127.0.0.1` only.
