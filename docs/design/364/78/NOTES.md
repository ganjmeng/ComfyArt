# #364 Agent「审核」toggle + post-image 审图思考 · #78 shots

**Branch:** `tip/364-review-toggle-post-thought` · closes #364  
**AC:** issue comment [6431169259](https://github.com/ganjmeng/ComfyArt/issues/364#issuecomment-6431169259) · box `ComfyArt-review-assets/364/REVIEW-TOGGLE.md`

**Base:** `origin/main` @ `2679deb` (#365/#361 merged)

## Honest source
Tip CSS harness + static DOM matching BotSettings「审核」row and AssistantBlocks Done path — NOT full Electron / NOT live LLM. ProcessTimeline already stacks thought → image → thought when the model emits a second thinking block; guide + `[Review: ON|OFF]` injection steers that.

## After (this tip)
| Shot | Theme | Shows | Priority |
|------|-------|-------|----------|
| `after/agent-settings-review-on.png` | light | Agent 设置「审核」checked (default ON) | **MUST** |
| `after/agent-settings-review-off.png` | light | Agent 设置「审核」unchecked | **MUST** |
| `after/chat-done-image-review-on.png` | light | 思考 → 出图 → **审图思考** → 摘要+prose+👍；no chips | **MUST** |
| `after/chat-done-image-review-off.png` | light | No 审图 step; still 摘要+prose+👍 (#360) | **MUST** |

## Evidence (box, not in tip)
`ComfyArt-review-assets/364/lovart-post-media-thought-crop.png` · `lovart-done-image-full-ref.png` · `comfyart-1881f20-missing-post-thought.png`

## Out of scope (not shot / not touched)
#361 refusal · #362 @ menu · media hero · suggestion chips · stripping prose when Review OFF
