/** Expand-panel placement after the scale slider is released (#868 follow-up). */

export const SIDE_GAP = 16
export const CLEAR = 12
export const EDGE = 8
export const VIEW_CLEAR = 12
export const PANEL_W = 280
export const PANEL_NARROW_W = 220
export const MOVE_MS = 150
export const HANDLE_W = 8
export const HANDLE_H = 28

export type Rect = { l: number; t: number; r: number; b: number }
export type Size = { w: number; h: number }
export type Host = { width: number; height: number }
export type Heights = { full: number; narrow: number }
export type Side = 'right' | 'left' | 'narrow-right' | 'narrow-left' | 'dock'
export type Place = { left: number; top: number; side: Side; width: number }

export function expandBox(rect: Rect, pads: { l: number; t: number; r: number; b: number }, scale: number): Rect {
  return {
    l: rect.l - pads.l * scale,
    t: rect.t - pads.t * scale,
    r: rect.r + pads.r * scale,
    b: rect.b + pads.b * scale,
  }
}

export function obstacleRects(container: ParentNode, host: { left: number; top: number }, selectors: string[] = ['.ca-tools', '.ca-dock']): Rect[] {
  const out: Rect[] = []
  for (const sel of selectors) {
    const el = container.querySelector(sel)
    if (!el) continue
    const r = el.getBoundingClientRect()
    out.push({ l: r.left - host.left, t: r.top - host.top, r: r.right - host.left, b: r.bottom - host.top })
  }
  return out
}

/** Midpoint handle on the expand box's right edge (matches `.ca-expand__handle[data-side=r]`). */
export function rightHandle(box: Rect): Rect {
  const mid = (box.t + box.b) / 2
  return {
    l: box.r - HANDLE_W / 2,
    t: mid - HANDLE_H / 2,
    r: box.r + HANDLE_W / 2,
    b: mid + HANDLE_H / 2,
  }
}

export function overlaps(a: Rect, b: Rect, gap: number) {
  return a.l < b.r + gap && a.r > b.l - gap && a.t < b.b + gap && a.b > b.t - gap
}

function hzOverlap(left: number, w: number, o: Rect, gap: number) {
  return left < o.r + gap && left + w > o.l - gap
}

function maxBottom(left: number, w: number, host: Host, obstacles: Rect[], edge: number): number {
  let bottom = host.height - edge
  for (const o of obstacles) {
    if (hzOverlap(left, w, o, CLEAR)) bottom = Math.min(bottom, o.t - CLEAR)
  }
  return bottom
}

function pickTop(preferredTop: number, left: number, size: Size, host: Host, obstacles: Rect[], edge: number): number | null {
  const topMax = maxBottom(left, size.w, host, obstacles, edge) - size.h
  if (topMax < edge) return null
  return Math.min(Math.max(preferredTop, edge), topMax)
}

function trySide(
  side: 'right' | 'left',
  box: Rect,
  size: Size,
  host: Host,
  obstacles: Rect[],
  preferredTop: number,
  edge: number,
): { left: number; top: number } | null {
  const left = side === 'right' ? box.r + SIDE_GAP : box.l - SIDE_GAP - size.w
  if (left < edge || left + size.w > host.width - edge) return null
  const top = pickTop(preferredTop, left, size, host, obstacles, edge)
  if (top == null) return null
  return { left, top }
}

function panelRect(left: number, top: number, size: Size): Rect {
  return { l: left, t: top, r: left + size.w, b: top + size.h }
}

function dockPanel(
  size: Size,
  host: Host,
  obstacles: Rect[],
  preferredTop: number,
  handle: Rect,
): Place {
  const left = Math.max(VIEW_CLEAR, host.width - VIEW_CLEAR - size.w)
  const topMax = maxBottom(left, size.w, host, obstacles, VIEW_CLEAR) - size.h
  // Keep the panel bottom above the zoom bar / dock even if that means a top < VIEW_CLEAR.
  const clamp = (top: number) => {
    if (topMax >= VIEW_CLEAR) return Math.min(Math.max(top, VIEW_CLEAR), topMax)
    return topMax
  }
  const clearsHandle = (top: number) => !overlaps(panelRect(left, top, size), handle, CLEAR)
  const inRange = (top: number) => top >= Math.min(VIEW_CLEAR, topMax) && top <= topMax && top + size.h <= maxBottom(left, size.w, host, obstacles, VIEW_CLEAR) + 0.01

  const pref = clamp(preferredTop)
  if (inRange(pref) && clearsHandle(pref)) return { left, top: pref, side: 'dock', width: PANEL_NARROW_W }

  const above = handle.t - CLEAR - size.h
  if (inRange(above) && clearsHandle(above)) return { left, top: above, side: 'dock', width: PANEL_NARROW_W }

  const below = handle.b + CLEAR
  if (inRange(below) && clearsHandle(below)) return { left, top: below, side: 'dock', width: PANEL_NARROW_W }

  // No vertical slot clears the handle. Still never cover the toolbars / Generate row.
  return { left, top: pref, side: 'dock', width: PANEL_NARROW_W }
}

/** Prefer the right of the expand box (16px gap) at 280px, then the left.
 *  If neither fits, narrow to 220px and try right then left (≥12px from the viewport).
 *  If 220px still does not fit, dock to the viewport right edge and shift vertically
 *  to stay clear of the right drag handle when a slot exists. */
export function placeExpandPanel(
  box: Rect,
  heights: Heights,
  host: Host,
  obstacles: Rect[],
  preferredTop: number,
  handle: Rect = rightHandle(box),
): Place {
  const full: Size = { w: PANEL_W, h: heights.full }
  const right = trySide('right', box, full, host, obstacles, preferredTop, EDGE)
  if (right) return { ...right, side: 'right', width: PANEL_W }
  const left = trySide('left', box, full, host, obstacles, preferredTop, EDGE)
  if (left) return { ...left, side: 'left', width: PANEL_W }

  const narrow: Size = { w: PANEL_NARROW_W, h: heights.narrow }
  const nRight = trySide('right', box, narrow, host, obstacles, preferredTop, VIEW_CLEAR)
  if (nRight) return { ...nRight, side: 'narrow-right', width: PANEL_NARROW_W }
  const nLeft = trySide('left', box, narrow, host, obstacles, preferredTop, VIEW_CLEAR)
  if (nLeft) return { ...nLeft, side: 'narrow-left', width: PANEL_NARROW_W }

  return dockPanel(narrow, host, obstacles, preferredTop, handle)
}
