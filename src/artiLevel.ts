import { readLocal, writeLocal } from './localPrefs'

/** #371: account Arti level. Real account level not ready → stub Lv.1.
 *  Mock override via localStorage `comfyart.arti.levelMock` = "1"|"2"|"3"
 *  or URL `?artiLevel=1|2|3` (dev/harness). Never fake a high level in UI. */

export type ArtiLevel = 1 | 2 | 3

const MOCK_KEY = 'comfyart.arti.levelMock'

/** Account level API stub — always 1 until product wires real account level. */
export function accountArtiLevel(): ArtiLevel {
  return 1
}

export function readArtiLevelMock(): ArtiLevel | null {
  try {
    const q = new URL(location.href).searchParams.get('artiLevel')
    if (q === '1' || q === '2' || q === '3') return Number(q) as ArtiLevel
  } catch { /* SSR / non-browser */ }
  const raw = readLocal(MOCK_KEY)
  if (raw === '1' || raw === '2' || raw === '3') return Number(raw) as ArtiLevel
  return null
}

export function setArtiLevelMock(level: ArtiLevel | null) {
  if (level == null) {
    try { localStorage.removeItem(MOCK_KEY) } catch { /* */ }
    return
  }
  writeLocal(MOCK_KEY, String(level))
}

/** Resolved level for UI: mock if set, else account stub (Lv.1). */
export function resolveArtiLevel(): ArtiLevel {
  return readArtiLevelMock() ?? accountArtiLevel()
}

export const MASCOT_FRAMES = 17
export const MASCOT_FRAME_MS = 250
export const MASCOT_DURATION_MS = MASCOT_FRAMES * MASCOT_FRAME_MS // 4250
