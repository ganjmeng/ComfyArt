import {
  CLEAR, EDGE, PANEL_NARROW_W, PANEL_W, SIDE_GAP, VIEW_CLEAR,
  expandBox, overlaps, placeExpandPanel, rightHandle, type Rect,
} from '../../src/ui/panelPlace'

const box = (l: number, t: number, r: number, b: number): Rect => ({ l, t, r, b })
const heights = { full: 520, narrow: 560 }
const host = { width: 1440, height: 900 }
const tools: Rect = { l: 1440 - 16 - 200, t: 900 - 64 - 44, r: 1440 - 16, b: 900 - 64 }
const dock: Rect = { l: 1440 / 2 - 260, t: 900 - 16 - 44, r: 1440 / 2 + 260, b: 900 - 16 }
const obstacles = [tools, dock]

const roomy = box(500, 200, 740, 520)
const leftOnly = box(400, 120, 1300, 700)
// 280 fits neither side; 220 fits on the right only
const narrowRightOnly = box(100, 40, 1160, 700)
// 280 fits neither side; 220 fits on both — must pick right
const narrowBoth = box(300, 40, 1160, 700)
// 280 fits neither side; 220 fits on the left only
const narrowLeftOnly = box(250, 40, 1300, 700)
// 280 and 220 fit neither side → dock
const tooWide = box(40, 40, 1200, 800)

const handleHost = { width: 800, height: 700 }
const handleTools: Rect = { l: 800 - 16 - 200, t: 700 - 64 - 44, r: 800 - 16, b: 700 - 64 }
const handleDock: Rect = { l: 800 / 2 - 200, t: 700 - 16 - 44, r: 800 / 2 + 200, b: 700 - 16 }
// Short box near the top: 220 cannot sit beside it, but there is room below the right handle
const shiftBox = box(20, 50, 700, 250)
const shiftHeights = { full: 200, narrow: 200 }

// Tall box filling the host: no vertical slot clears the handle
const coverBox = box(20, 20, 700, 680)
const coverHeights = { full: 470, narrow: 470 }

const asRect = (p: { left: number; top: number; width?: number }, h: number, w?: number): Rect => ({
  l: p.left, t: p.top, r: p.left + (w ?? p.width ?? PANEL_W), b: p.top + h,
})

const right = placeExpandPanel(roomy, heights, host, obstacles, roomy.t)
const left = placeExpandPanel(leftOnly, heights, host, obstacles, leftOnly.t)
const nRight = placeExpandPanel(narrowRightOnly, heights, host, obstacles, narrowRightOnly.t)
const nBoth = placeExpandPanel(narrowBoth, heights, host, obstacles, narrowBoth.t)
const nLeft = placeExpandPanel(narrowLeftOnly, heights, host, obstacles, narrowLeftOnly.t)
const docked = placeExpandPanel(tooWide, heights, host, obstacles, tooWide.t)
const shifted = placeExpandPanel(shiftBox, shiftHeights, handleHost, [handleTools, handleDock], shiftBox.t)
const covered = placeExpandPanel(coverBox, coverHeights, handleHost, [handleTools, handleDock], coverBox.t)

const pads = { l: 180, t: 240, r: 180, b: 240 }
const scaled = expandBox(box(500, 300, 680, 540), pads, 0.5)

const clearTools = (p: { left: number; top: number; width: number }, h: number, t = tools, d = dock) => {
  const r = asRect(p, h, p.width)
  return { tools: !overlaps(r, t, CLEAR), dock: !overlaps(r, d, CLEAR), gen: !overlaps({ ...r, t: r.b - 36 }, t, 0) }
}

console.log(JSON.stringify({
  constants: { SIDE_GAP, CLEAR, EDGE, VIEW_CLEAR, PANEL_W, PANEL_NARROW_W },
  right,
  left,
  nRight,
  nBoth,
  nLeft,
  docked,
  shifted,
  covered,
  scaled,
  handle: {
    shift: rightHandle(shiftBox),
    cover: rightHandle(coverBox),
    shiftedClearsHandle: !overlaps(asRect(shifted, shiftHeights.narrow, shifted.width), rightHandle(shiftBox), CLEAR),
    coveredHitsHandle: overlaps(asRect(covered, coverHeights.narrow, covered.width), rightHandle(coverBox), CLEAR),
  },
  clear: {
    right: clearTools(right, heights.full),
    left: clearTools(left, heights.full),
    nRight: clearTools(nRight, heights.narrow),
    nBoth: clearTools(nBoth, heights.narrow),
    nLeft: clearTools(nLeft, heights.narrow),
    docked: clearTools(docked, heights.narrow),
    shifted: clearTools(shifted, shiftHeights.narrow, handleTools, handleDock),
    covered: clearTools(covered, coverHeights.narrow, handleTools, handleDock),
  },
}))
