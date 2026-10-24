# peripheral-v1 — #249 chrome polish only

Scope locked by product (2026-10-25): **peripheral checklist, 6 items**.
3D viewport contents stay **pixel-identical** to main `0ec5d4d` (stage crop pasted).

## In scope (exactly these 6)

1. Panel outer/inner padding aligned with sibling `.ca-panel` (16px)
2. 相机/对象/预览 row height, selected state (`data-on` + active fill), spacing (gap 8, h 30)
3. Preset chip height 30, radius 10, gap 8 (not cramped); same 11 labels, 5+5+1 wrap
4. Three slider tracks (4px), thumbs (14px), label/value 13px + row gap 10
5. 一次生成 4 个角度 h 38; 取消/生成 h 40; foot gap 10
6. Panel shadow + border weight matching #243/#245 light styles
   - light: `--ca-border-w: 1px`, elevation-300 `--ca-shadow`
   - dark: `.5px` border, existing dark shadow

## Out of scope / do not change

- Cube, sphere, colored handles, corner live preview (stage pixels = main)
- Preset contents, slider ranges/values
- Generate-button-blocked (#254)
- detail-v1 cube redraw (`a6f038d`) — **VOID** for development

## Method

- Left = main panel PNG crops
- Right = HTML chrome mock (`panel.html`) + exact main stage crop pasted into `#stage`
- Stage pixel-diff vs main crop: **0** on all 4 variants
- Stage slot: 286×240 @ ~(17,87) on polished (main was ~(17,83); +4px from tab h 30)

## Files

```
pr249/peripheral-v1/
  SPEC.md
  panel.html
  right_object_zh_light.png
  right_object_zh_dark.png
  right_camera_zh_light.png
  right_camera_zh_dark.png
  compare/
    compare_object_zh_light.png
    compare_object_zh_dark.png
    compare_camera_zh_light.png
    compare_camera_zh_dark.png
    compare_all.png
```
