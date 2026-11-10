import { CLEAR, EDGE, SIDE_GAP, expandBox, placeExpandPanel, type Rect } from '../../src/ui/panelPlace'

const box = (l: number, t: number, r: number, b: number): Rect => ({ l, t, r, b })
const size = { w: 280, h: 520 }
const host = { width: 1440, height: 900 }
// .ca-tools: right 16, bottom 64, height 44. Approximate a 200x44 bar.
const tools: Rect = { l: 1440 - 16 - 200, t: 900 - 64 - 44, r: 1440 - 16, b: 900 - 64 }
// .ca-dock: centered, bottom 16, ~44px tall, ~520px wide
const dock: Rect = { l: 1440 / 2 - 260, t: 900 - 16 - 44, r: 1440 / 2 + 260, b: 900 - 16 }
const obstacles = [tools, dock]

const roomy = box(500, 200, 740, 520)           // image with room on the right
const wide = box(40, 40, 1200, 800)             // 3x-like: neither side has 16+280 room
const leftOnly = box(400, 120, 1300, 700)       // no room on the right, room on the left
const narrowHost = { width: 1280, height: 800 }
const narrowTools: Rect = { l: 1280 - 16 - 200, t: 800 - 64 - 44, r: 1280 - 16, b: 800 - 64 }
const narrowDock: Rect = { l: 1280 / 2 - 260, t: 800 - 16 - 44, r: 1280 / 2 + 260, b: 800 - 16 }

const gap = (a: Rect, b: Rect) => {
  const sepX = Math.max(b.l - a.r, a.l - b.r)
  const sepY = Math.max(b.t - a.b, a.t - b.b)
  if (sepX >= 0 && sepY >= 0) return Math.hypot(sepX, sepY)
  if (sepX >= 0) return sepX
  if (sepY >= 0) return sepY
  return -Math.min(-sepX, -sepY) // overlap amount (negative)
}

const asRect = (p: { left: number; top: number }, s = size): Rect => ({
  l: p.left, t: p.top, r: p.left + s.w, b: p.top + s.h,
})

const right = placeExpandPanel(roomy, size, host, obstacles, roomy.t)
const left = placeExpandPanel(leftOnly, size, host, obstacles, leftOnly.t)
const pin = placeExpandPanel(wide, size, host, obstacles, wide.t)
const narrow = placeExpandPanel(
  box(30, 30, 1100, 720),
  size,
  narrowHost,
  [narrowTools, narrowDock],
  30,
)
const pads = { l: 180, t: 240, r: 180, b: 240 }
const scaled = expandBox(box(500, 300, 680, 540), pads, 0.5)

console.log(JSON.stringify({
  constants: { SIDE_GAP, CLEAR, EDGE },
  right,
  left,
  pin,
  narrow,
  scaled,
  gaps: {
    rightBox: right.left - roomy.r,
    rightTools: gap(asRect(right), tools),
    rightDock: gap(asRect(right), dock),
    leftBox: leftOnly.l - (left.left + size.w),
    leftTools: gap(asRect(left), tools),
    leftDock: gap(asRect(left), dock),
    pinTools: gap(asRect(pin), tools),
    pinDock: gap(asRect(pin), dock),
    narrowTools: gap(asRect(narrow), narrowTools),
    narrowRight: narrowHost.width - EDGE - (narrow.left + size.w),
  },
}))
