#868 扩图面板避让（松手后不再挡住缩放条 /「生成」）

$0 mocked local shots, localhost only. After dragging the expand scale slider and releasing, the ModePanel is repositioned once (150ms move transition) so it stays ≥12px from the expand-box edges, the bottom dock, and the bottom-right zoom bar (`.ca-tools`).

Canvas zoom is 50% so 3× pads still fit in frame.

| 松手后 | 文件 |
| --- | --- |
| 缩放 1×，1440×900 | [01-after-release-1x.png](01-after-release-1x.png) |
| 缩放 2×，1440×900 | [02-after-release-2x.png](02-after-release-2x.png) |
| 缩放 3×，1440×900 | [03-after-release-3x.png](03-after-release-3x.png) |
| 缩放 3×，窄视口 1280×800 | [04-after-release-3x-1280.png](04-after-release-3x-1280.png) |

## How to reshoot

Build `dist` in this worktree (do not commit it), then:

```bash
/workspace/ca-venv/bin/python docs/qa/868-panel/shoot_after.py
```

`docs/qa/868/boot_app.py` serves the tree on 127.0.0.1:8868 with a stub host and the local WaveSpeed catalog fixture. Keys are unset except a fake in-process value that is never printed. No LAN / internal addresses.

## Notes

- 1× and 2× sit on the **right** of the expand box with a 16px gap. Handles, the bottom dock, and the zoom bar stay clear (≥12px). The 「生成」 button is fully visible.
- At 3× (and 3× in a 1280px-wide viewport) neither side has room for the 280px panel plus a 16px gap, so the panel is **pinned to the viewport right edge** with its bottom kept above the zoom bar (rule 2 fallback). The zoom bar, dock, and 「生成」 stay clear. The panel overlaps the expand box's right handle — a known limit of the pin fallback when the box extends close to the right edge.
- Canvas zoom is 50% so the 3× box still fits in frame. Host is `127.0.0.1` only.
