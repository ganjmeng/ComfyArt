# Lovart CN agent step rail — observed only

Source: https://www.lovart.ai/zh (already signed in; no login wall, no captcha). Canvas used for the shots:

- https://www.lovart.ai/canvas?projectId=2tzuws6128e8 — project title **画一只红色苹果，白底** (updated 2026-10-26). This is the evidence below.
- Cross-check only: https://www.lovart.ai/canvas?projectId=2sk810lxks1s — **Simple red apple on white background**. Same image-step label pattern. Not the screenshots.

No project whose title contained 草莓 / strawberry was in the loaded CN project list. No new generation was started (credits not spent). Viewport of the PNGs is 1919×1112 (Chrome window larger than the 1280×800 desktop). Chat column is the left 400px.

Theme: `<html class="light" style="color-scheme: light">`. No theme toggle on home, projects, or the canvas agent chrome. Dark was not captured.

Language: CN site. Step labels below are Chinese. Model name stays English. No in-chat language switch was available; EN site was not used.

## Strings that were NOT on screen

Not observed as visible step labels in either chat: **思考中**, **图片模型**, **生图** (as an agent step), **摘要**, **审图**, **再思考**, emoji **👍**.

Separate control, not the agent rail: canvas toolbar button aria-label **生图画布**.

English words **Thought** / **Generated images** were not used as labels.

## What the rail actually shows (apple project, second turn)

User asked the agent to show thinking and every tool step. Visible session titles, top to bottom:

| Order | Exact label | Icon (shape, ~16px, gray) |
| --- | --- | --- |
| 1 | 思考完成 | Head in profile / brain-like outline (round skull, small side lobe). Not a spinner. |
| 2 | 技能加载完成 | Open book |
| 3 | 思考完成 | same head/brain |
| 4 | 技能加载完成 | open book |
| 5 | 思考完成 | same head/brain |
| 6 | 1 个网页 | Globe (meridians). A small colored dot sits just left of the globe. |
| — | 联网搜索结果 | Card under that row, not the same title style. Copy button on the card. |
| 7 | GPT Image Flare | Picture frame with a mountain/landscape (generic image icon). Label is the model name, not 图片模型 or 生图. |
| 8 | 参考素材分析结束 | Clipboard / lined page, then a chevron `>`. Row is expandable. |

Then body text, with **no heading 摘要**:

- Recap starts **全流程已走完，逐步记录如下：** and lists Step 1–Step 5 in prose.
- Next-step sentence, exact: **相比上一轮的区别：这只苹果的红色是条纹状霞红而非均匀大红，果形更扁圆、果点可见，品种特征落在红富士上。需要写实摄影质感、加投影，或转成透明底/其他尺寸，我接着做。**
- Then two icon buttons, no text glyph: aria-label **点赞** (thumb up outline) and **点踩** (thumb down outline).

## First turn in the same chat (no “show steps” instruction)

Visible order only:

1. **GPT Image Flare** (same picture icon)
2. The image
3. Prose, exact: **已画好：一只红苹果，纯白底，方形构图（1254×1254）。** then **需要的话我可以调整风格（写实摄影 / 扁平插画 / 水彩）、加投影，或换成透明底、其他尺寸。**
4. **点赞** / **点踩**

No 思考完成 row is painted on this turn.

## Post-image second 思考完成

After the image, the painted row is **参考素材分析结束**, then the prose above, then thumbs. A second **思考完成** is **not** visible.

In the DOM of that same post-image group there is one more `agent-chat-session-title` whose text is **思考完成**, inside an ancestor with class `hidden` (container height 0). It is not rendered. No 审图 control was found, so this note does **not** treat that hidden node as a confirmed “review off” switch — only that a second thought row is absent on screen, while 点赞/点踩 and the prose next step are present. There is no visible label 摘要.

The other project (2sk810lxks1s) also has **思考完成** titles with the same `hidden` class before **GPT Image Flare** rows, so those thoughts were not on screen either. Visible image step there is again **GPT Image Flare**. One historical status pill reads **生成任务已取消** (body status, not a rail title). Other visible titles in that chat, not part of the image chain: **技能加载完成**, **思考完成** (visible once, before video), **Seedance 2.0 视频生成**, **GIF 生成完成**.

## 思考中

Not present. Both chats are finished. A live run was not started, so the in-progress label was not captured. Do not assume it reads 思考中 from these screenshots.

## Files

Full frames (chat left, canvas right):

- `/workspace/ComfyArt-review-assets/627/prep/lovart/cn-apple-step-rail-lr.png` — thinking/skill/web rows, then GPT Image Flare, then 参考素材分析结束
- `/workspace/ComfyArt-review-assets/627/prep/lovart/cn-apple-after-image-summary-thumbs-lr.png` — post-image prose, next-step sentence, thumbs; no second 思考完成
- `/workspace/ComfyArt-review-assets/627/prep/lovart/cn-apple-first-turn-then-think-lr.png` — first turn (model + result + thumbs) then the start of the thinking rail

Left column only:

- `.../lovart/cn-apple-step-rail-left.png`
- `.../lovart/cn-apple-summary-thumbs-left.png`
- `.../lovart/cn-apple-first-turn-left.png`

Crops in `.../lovart/crops/`: `labels-think-skill-web.png`, `icon-strip-think-skill-web.png`, `maximized-think-stack.png`, `icon-strip-maximized-think.png`, `row-*.png`, `icon-*.png`, `thumbs-up-down.png`.
