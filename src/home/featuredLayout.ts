/** Home 「用 Skill 快速开始」: one row of this many cover cards (skills-cut1). */
export const HOME_SKILL_ROW = 6

/** Home 「Skill 案例」 masonry: column width ≈ FEATURED_COL_W (design: 299 @1280 expanded), gap FEATURED_GAP;
 * column count adapts to the container (3 @1280, 5 @1920) — columns stay fluid so they fill the row.
 * Overridable from CSS vars --ca-featured-col-w / --ca-featured-gap. */
export const FEATURED_COL_W = 299
export const FEATURED_GAP = 16
export interface FeaturedMetrics { colWidth: number; gap: number }
export const FEATURED_DEFAULTS: FeaturedMetrics = { colWidth: FEATURED_COL_W, gap: FEATURED_GAP }
export function featuredColumnCount(width: number, gap = FEATURED_GAP, colWidth = FEATURED_COL_W): number {
  if (!Number.isFinite(width) || width <= 0) return 1
  // round (not floor): 928 @1280 → 2.997 → 3 columns ≈ 298.7 wide
  return Math.max(1, Math.round((width + gap) / (colWidth + gap)))
}
export function readFeaturedMetrics(el: Element): FeaturedMetrics {
  const cs = getComputedStyle(el)
  const num = (name: string, d: number) => { const v = parseFloat(cs.getPropertyValue(name)); return Number.isFinite(v) && v > 0 ? v : d }
  return { colWidth: num('--ca-featured-col-w', FEATURED_COL_W), gap: num('--ca-featured-gap', FEATURED_GAP) }
}

/** Stable aspect for masonry height without remote metadata (deterministic cycle). */
const ASPECTS = [4 / 3, 3 / 4, 1, 9 / 16, 16 / 9, 5 / 4] as const
export function featuredAspect(seed: string): number {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return ASPECTS[h % ASPECTS.length]!
}

/** Shortest-column pack — same idea as Loomic home-featured-gallery when count ≠ 5. */
export function packFeaturedColumns<T extends { id: string; aspect: number }>(
  items: readonly T[],
  width: number,
  gap = FEATURED_GAP,
  colWidth = FEATURED_COL_W,
): T[][] {
  const count = featuredColumnCount(width, gap, colWidth)
  const columns: T[][] = Array.from({ length: count }, () => [])
  const heights = Array.from({ length: count }, () => 0)
  const columnWidth = (width - (count - 1) * gap) / count
  for (const item of items) {
    const index = heights.indexOf(Math.min(...heights))
    columns[index]!.push(item)
    heights[index] = (heights[index] ?? 0) + gap + Math.min(columnWidth / item.aspect, 680) + 34
  }
  return columns
}
