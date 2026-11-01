/** Home 「用 Skill 快速开始」: one row of this many cover cards (skills-cut1). */
export const HOME_SKILL_ROW = 6

/** Home 「精选」 waterfall: at most FEATURED_MAX_COLUMNS columns (skills-cut1: 4 → 5), each ≥ FEATURED_MIN_CARD px; fewer on narrow widths. */
export const FEATURED_MAX_COLUMNS = 5
export const FEATURED_MIN_CARD = 180
export const FEATURED_GAP = 16
/** Overridable from CSS vars (--ca-featured-cols / --ca-featured-min-col / --ca-featured-gap); final 1280x800 numbers TODO-measure (design v2). */
export interface FeaturedMetrics { maxColumns: number; minCard: number; gap: number }
export const FEATURED_DEFAULTS: FeaturedMetrics = { maxColumns: FEATURED_MAX_COLUMNS, minCard: FEATURED_MIN_CARD, gap: FEATURED_GAP }
export function featuredColumnCount(width: number, gap = FEATURED_GAP, maxColumns = FEATURED_MAX_COLUMNS, minCard = FEATURED_MIN_CARD): number {
  if (!Number.isFinite(width) || width <= 0) return 1
  const fit = Math.floor((width + gap) / (minCard + gap))
  return Math.max(1, Math.min(maxColumns, fit))
}
export function readFeaturedMetrics(el: Element): FeaturedMetrics {
  const cs = getComputedStyle(el)
  const num = (name: string, d: number) => { const v = parseFloat(cs.getPropertyValue(name)); return Number.isFinite(v) && v > 0 ? v : d }
  return {
    maxColumns: Math.round(num('--ca-featured-cols', FEATURED_MAX_COLUMNS)),
    minCard: num('--ca-featured-min-col', FEATURED_MIN_CARD),
    gap: num('--ca-featured-gap', FEATURED_GAP),
  }
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
  maxColumns = FEATURED_MAX_COLUMNS,
  minCard = FEATURED_MIN_CARD,
): T[][] {
  const count = featuredColumnCount(width, gap, maxColumns, minCard)
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
