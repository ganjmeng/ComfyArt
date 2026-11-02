# #497 list-width re-pin (2026-11-02 Asia/Shanghai)

## Miss cause
Soft pin `ad48d344` GAP row1 measured Lovart **nav right edge ≈159 @1280** and labeled it「列表分隔」. Tip AC 6573167553 + CSS `calc(12.5vw - rail)` / `max-width:180` crushed list to ~88–104px. Design PASS 6573526518 rubber-stamped #78 without checking tab/card truncation.

**Correct structure** (design 6547101132 @1920): 侧栏 **0–240** · 列表 **240–620 = 380 wide** · 详情 800 居中. ComfyArt collapsed icon rail ≠ Lovart text nav; **do not** map nav edge → list width.

## TARGET (tip FU)
| Viewport | List content width (exclude icon rail) | Notes |
|---|---|---|
| 1920 | **380px** (±8) | Gold from 6547101132 / pre-#631 ≈382 |
| 1280 | **380px** (±8) fixed, **not** 12.5vw | Same absolute as #539 usable width; readable tabs/cards |
| Void | **159 / 12.5vw / max-width:180** | Never again as list width |

Rail icons: perfect circles, no squash. Keep #631 wins: list `#f5f5f5`, no「从文件中提取」,「未命名」, dashed 新建, CTA.

## Evidence
- Lovart page measure: 6547101132 + `50726f3` 539/lovart/
- Ours pre-crush: AFTER #539 divider ~438 @1280/1920 → list ≈382 after ~56 rail
- Crush: tip `c1b3305d` AFTER divider ~158
