/** #540 — home tool card covers on orphan review-assets (commit-pinned; design wash PASS).
 *  Same embed pattern as skills.ts WASH_COVER_COMMIT — raw.githubusercontent, no WaveSpeed. */
export const TOOL_WASH_COMMIT = '8eb46909'
const BASE = `https://raw.githubusercontent.com/ganjmeng/ComfyArt/${TOOL_WASH_COMMIT}/540/wash`

export type ToolCoverGroup = 'main-5' | 'more-10' | 'unique-4'

export const toolCover = (group: ToolCoverGroup, id: string) =>
  `${BASE}/${group}/${id}.png`
