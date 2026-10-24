export const GAP = 8
export const EDGE = 8

type Rect = { left: number; top: number; right: number; bottom: number; width: number; height: number }

/** #229: place a popover next to its anchor without leaving the viewport. Use the preferred side if the panel fits,
 *  else the other side if it fits, else the side with more room, capped to that room (the panel scrolls inside). */
export function placePopover(a: Rect, p: { width: number; height: number }, view: { width: number; height: number },
  side: 'top' | 'bottom', align: 'start' | 'center' | 'end'): { left: number; top: number; maxHeight?: number } {
  let left = align === 'start' ? a.left : align === 'end' ? a.right - p.width : a.left + a.width / 2 - p.width / 2
  left = Math.min(Math.max(left, EDGE), view.width - p.width - EDGE)
  const below = view.height - EDGE - (a.bottom + GAP)
  const above = a.top - GAP - EDGE
  const order: ('top' | 'bottom')[] = side === 'top' ? ['top', 'bottom'] : ['bottom', 'top']
  const room = (s: 'top' | 'bottom') => (s === 'top' ? above : below)
  const fit = order.find((s) => room(s) >= p.height)
  if (fit) return { left, top: fit === 'top' ? a.top - GAP - p.height : a.bottom + GAP }
  const s = above > below ? 'top' : 'bottom'
  const h = Math.max(room(s), 0)
  // anchor partly off-screen: neither side has real room, so pin to the viewport instead
  if (h < Math.min(p.height, 160)) return { left, top: EDGE, maxHeight: view.height - 2 * EDGE }
  return { left, top: s === 'top' ? a.top - GAP - h : a.bottom + GAP, maxHeight: h }
}
