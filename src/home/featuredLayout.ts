/** #537 / #496: Loomic `featured-layout` column rule (280–320px cards, 16px gap). Logic only — no third-party feed data. */
export function featuredColumnCount(width: number, gap = 16): number {
  if (!Number.isFinite(width) || width <= 0) return 1
  const minimum = Math.max(1, Math.ceil((width + gap) / (320 + gap)))
  const maximum = Math.max(1, Math.floor((width + gap) / (280 + gap)))
  if (minimum <= maximum) return maximum
  let closest = 1
  let distance = Number.POSITIVE_INFINITY
  for (let count = 1; count <= Math.max(minimum, maximum) + 1; count++) {
    const cardWidth = (width - gap * (count - 1)) / count
    const next = Math.max(280 - cardWidth, cardWidth - 320, 0)
    if (next <= distance) {
      closest = count
      distance = next
    }
  }
  return closest
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
  gap = 16,
): T[][] {
  const count = featuredColumnCount(width, gap)
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
