/** Expand-panel placement after the scale slider is released (#868 follow-up). */

export const SIDE_GAP = 16
export const CLEAR = 12
export const EDGE = 8
export const MOVE_MS = 150

export type Rect = { l: number; t: number; r: number; b: number }
export type Size = { w: number; h: number }
export type Host = { width: number; height: number }
export type Side = 'right' | 'left' | 'pin'
export type Place = { left: number; top: number; side: Side }

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

function hzOverlap(left: number, w: number, o: Rect, gap: number) {
  return left < o.r + gap && left + w > o.l - gap
}

function maxBottom(left: number, w: number, host: Host, obstacles: Rect[]): number {
  let bottom = host.height - EDGE
  for (const o of obstacles) {
    if (hzOverlap(left, w, o, CLEAR)) bottom = Math.min(bottom, o.t - CLEAR)
  }
  return bottom
}

function pickTop(preferredTop: number, left: number, size: Size, host: Host, obstacles: Rect[]): number | null {
  const topMax = maxBottom(left, size.w, host, obstacles) - size.h
  if (topMax < EDGE) return null
  return Math.min(Math.max(preferredTop, EDGE), topMax)
}

function trySide(side: 'right' | 'left', box: Rect, size: Size, host: Host, obstacles: Rect[], preferredTop: number): Place | null {
  const left = side === 'right' ? box.r + SIDE_GAP : box.l - SIDE_GAP - size.w
  if (left < EDGE || left + size.w > host.width - EDGE) return null
  const top = pickTop(preferredTop, left, size, host, obstacles)
  if (top == null) return null
  return { left, top, side }
}

/** Prefer the right of the expand box (16px gap), then the left; otherwise pin to the
 *  viewport right edge and keep the panel bottom above the bottom / zoom toolbars. */
export function placeExpandPanel(box: Rect, size: Size, host: Host, obstacles: Rect[], preferredTop: number): Place {
  return trySide('right', box, size, host, obstacles, preferredTop)
    ?? trySide('left', box, size, host, obstacles, preferredTop)
    ?? (() => {
      const left = Math.max(EDGE, host.width - EDGE - size.w)
      const topMax = maxBottom(left, size.w, host, obstacles) - size.h
      const top = Math.min(Math.max(preferredTop, EDGE), Math.max(EDGE, topMax))
      return { left, top, side: 'pin' as const }
    })()
}
