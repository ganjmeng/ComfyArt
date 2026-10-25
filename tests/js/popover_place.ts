import { placeBarMenu, placePopover } from '../../src/ui/popoverPlace'

const r = (left: number, top: number, w: number, h: number) => ({ left, top, right: left + w, bottom: top + h, width: w, height: h })
const view = { width: 1280, height: 800 }
const menu = { width: 160, height: 1060 }  // More menu with every item, taller than 800
const bar = r(495, 193, 690, 44)   // image toolbar at a2fa330's default placement
const btn = r(1093, 199, 36, 32)   // ⋯ on the right of that bar
const short = { width: 1280, height: 500 }
console.log(JSON.stringify({
  placePopover: [
    placePopover(r(900, 40, 32, 32), { width: 160, height: 300 }, view, 'bottom', 'end'),  // fits below
    placePopover(r(900, 700, 32, 32), { width: 160, height: 300 }, view, 'bottom', 'end'),  // flips up
    placePopover(r(900, 40, 32, 32), menu, view, 'bottom', 'end'),  // capped below, scrolls
    placePopover(r(900, 740, 32, 32), menu, view, 'bottom', 'end'),  // capped above, scrolls
    placePopover(r(900, 80, 32, 32), menu, { width: 1280, height: 200 }, 'bottom', 'end'),  // tiny window: pinned to viewport
  ],
  placeBarMenu: [
    placeBarMenu(bar, btn, menu, view),                                                          // open down at 1280x800
    placeBarMenu(r(495, 620, 690, 44), r(1093, 626, 36, 32), menu, view),                         // flip up (<240 below)
    placeBarMenu(r(495, 120, 690, 44), r(1093, 126, 36, 32), menu, short),                        // short 500px window, opens down
  ],
}))
