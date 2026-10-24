import { placePopover } from '../../src/ui/popoverPlace'

const r = (left: number, top: number, w: number, h: number) => ({ left, top, right: left + w, bottom: top + h, width: w, height: h })
const view = { width: 1280, height: 800 }
const menu = { width: 160, height: 1060 }  // More menu with every item, taller than 800
console.log(JSON.stringify([
  placePopover(r(900, 40, 32, 32), { width: 160, height: 300 }, view, 'bottom', 'end'),  // fits below
  placePopover(r(900, 700, 32, 32), { width: 160, height: 300 }, view, 'bottom', 'end'),  // flips up
  placePopover(r(900, 40, 32, 32), menu, view, 'bottom', 'end'),  // capped below, scrolls
  placePopover(r(900, 740, 32, 32), menu, view, 'bottom', 'end'),  // capped above, scrolls
  placePopover(r(900, 80, 32, 32), menu, { width: 1280, height: 200 }, 'bottom', 'end'),  // tiny window: pinned to viewport
]))
