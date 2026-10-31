/** #540 — home tool card covers on orphan review-assets (commit-pinned; design wash PASS).
 *  Same embed pattern as skills.ts WASH_COVER_COMMIT — raw.githubusercontent, no WaveSpeed. */
export const TOOL_WASH_COMMIT = '8eb46909'
const BASE = `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${TOOL_WASH_COMMIT}/540/wash`

export type ToolCoverGroup = 'main-5' | 'more-10' | 'unique-4'

/** #540 main 5: design wash-v2 (#540 comment 6545206549) on review-assets 1ecb47a; the 14 backups stay on TOOL_WASH_COMMIT. */
export const TOOL_MAIN5_COMMIT = '1ecb47a'
const MAIN5_BASE = `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${TOOL_MAIN5_COMMIT}/540/wash-v2/main-5`

export const toolCover = (group: ToolCoverGroup, id: string) =>
  group === 'main-5' ? `${MAIN5_BASE}/${id}.png` : `${BASE}/${group}/${id}.png`
