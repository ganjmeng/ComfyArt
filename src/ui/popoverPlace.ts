export const GAP = 8
export const EDGE = 8

type Rect = { left: number; top: number; right: number; bottom: number; width: number; height: number }

/** #229: place a popover next to its anchor without leaving the viewport. Use the preferred side if the panel fits,
 *  else the other side if it fits, else the side with more room, capped to that room (the panel scrolls inside). */
export function placePopover(a: Rect, p: { width: number; height: number }, view: { width: number; height: number },
  side: 'top' | 'bottom', align: 'start' | 'center' | 'end', viewportCap = false): { left: number; top: number; maxHeight?: number } {
  let left = align === 'start' ? a.left : align === 'end' ? a.right - p.width : a.left + a.width / 2 - p.width / 2
  left = Math.min(Math.max(left, EDGE), view.width - p.width - EDGE)
  const below = view.height - EDGE - (a.bottom + GAP)
  const above = a.top - GAP - EDGE
  const order: ('top' | 'bottom')[] = side === 'top' ? ['top', 'bottom'] : ['bottom', 'top']
  const room = (s: 'top' | 'bottom') => (s === 'top' ? above : below)
  const fit = order.find((s) => room(s) >= p.height)
  if (fit) return { left, top: fit === 'top' ? a.top - GAP - p.height : a.bottom + GAP }
  // #287 (home): neither side fits → centre in the window, height capped to window - 64, scroll inside
  if (viewportCap) {
    const maxHeight = Math.max(view.height - 64, 0)
    return { left, top: Math.max((view.height - Math.min(p.height, maxHeight)) / 2, 32), maxHeight }
  }
  const s = above > below ? 'top' : 'bottom'
  const h = Math.max(room(s), 0)
  // anchor partly off-screen: neither side has real room, so pin to the viewport instead
  if (h < Math.min(p.height, 160)) return { left, top: EDGE, maxHeight: view.height - 2 * EDGE }
  return { left, top: s === 'top' ? a.top - GAP - h : a.bottom + GAP, maxHeight: h }
}

/** Menu that hangs off a toolbar: never covers the toolbar, right edge on the trigger's right edge.
 * Opens 4px below the bar; height = min(window - 64, window - menu top - 16), overflow scrolls inside.
 * Only if fewer than 240px would be left below does it open 4px above the bar instead. */
export function placeBarMenu(bar: Rect, btn: Rect, p: { width: number; height: number }, view: { width: number; height: number }): { left: number; top: number; maxHeight: number } {
  const G = 4, M = 16
  const left = Math.min(Math.max(btn.right - p.width, 8), view.width - p.width - 8)
  const top = bar.bottom + G
  const below = view.height - top - M
  const above = bar.top - G - M
  const up = below < 240 && above > below
  const maxHeight = Math.max(Math.min(view.height - 64, up ? above : below), 0)
  return { left, top: up ? bar.top - G - Math.min(p.height, maxHeight) : top, maxHeight }
}
