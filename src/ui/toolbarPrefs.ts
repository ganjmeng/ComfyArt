// #244 image toolbar prefs: tool ids, fixed tools and stored-prefs migration (pure, no React)
/** Default pinned order (#244 Jingmeng): 快捷编辑 → 对话 → 放大 → 去背景 → 橡皮;
 *  then ⋯ → 下载 on the bar. No dividers; spacing before 下载 matches the bar gap (design). */
export const DEFAULT_PINNED = ['quick', 'chat', 'upscale', 'cutout', 'erase']
/** Pre-#244 default; users still on this set are migrated to DEFAULT_PINNED. */
const LEGACY_DEFAULT = ['chat', 'quick', 'inpaint', 'cutout', 'upscale', 'expand']
export const MENU_MAIN = ['inpaint', 'expand', 'text', 'crop', 'style', 'adjust', 'layers', 'animate', 'angles']
export const MENU_GEN = ['regenerate', 'remix', 'copyPrompt', 'export']
export const MORE_TOOLS = ['effects', 'elements', 'move', 'mockup', 'to3d', 'transform', 'vectorize', 'ocr', 'smudge', 'preview', 'info']
export const ALL_TOOLS = [...DEFAULT_PINNED, ...MENU_MAIN, ...MENU_GEN, ...MORE_TOOLS]
/** always on the bar, first, in this order; cannot be unpinned (快捷编辑 then 对话) */
export const FIXED_TOOLS = ['quick', 'chat']
export const isFixed = (id: string) => FIXED_TOOLS.includes(id)

export interface BarPrefs { pinned: string[]; names: boolean; seen: string[] }

function sameSet(a: string[], b: string[]) {
  return a.length === b.length && a.every((id) => b.includes(id))
}

/** fixed tools first (even if a user unpinned them before), then the rest in stored order */
export function withFixed(pinned: string[]): string[] {
  return [...FIXED_TOOLS, ...pinned.filter((id) => !isFixed(id))]
}

export function migratePrefs(raw: string | null): BarPrefs {
  try {
    const stored = JSON.parse(raw ?? 'null') as Partial<BarPrefs> | null
    if (!stored?.pinned) return { pinned: DEFAULT_PINNED, names: stored?.names ?? true, seen: ALL_TOOLS }
    // users still on the old default set get the new product defaults
    if (sameSet(stored.pinned, LEGACY_DEFAULT)) {
      return { pinned: DEFAULT_PINNED, names: stored.names ?? true, seen: ALL_TOOLS }
    }
    const seen = stored.seen ?? []
    const pinned = [...stored.pinned, ...DEFAULT_PINNED.filter((id) => !seen.includes(id) && !stored.pinned!.includes(id))]
    return { pinned: withFixed(pinned), names: stored.names ?? true, seen: ALL_TOOLS }
  } catch {
    return { pinned: DEFAULT_PINNED, names: true, seen: ALL_TOOLS }
  }
}
