// #244: fixed tools (quick, chat) are always pinned and first; defaults are 快捷编辑→对话→放大→去背景→橡皮
import { migratePrefs, withFixed, FIXED_TOOLS, DEFAULT_PINNED } from '../../src/ui/toolbarPrefs'
const S = (o: unknown) => JSON.stringify(o)
const LEGACY = ['chat', 'quick', 'inpaint', 'cutout', 'upscale', 'expand']
console.log(JSON.stringify({
  fixed: FIXED_TOOLS,
  defaults: DEFAULT_PINNED,
  fresh: migratePrefs(null).pinned,
  broken: migratePrefs('{').pinned,
  legacyMigrated: migratePrefs(S({ pinned: LEGACY, names: true, seen: LEGACY })).pinned,
  unpinnedChat: migratePrefs(S({ pinned: ['quick', 'upscale', 'erase'], names: false, seen: DEFAULT_PINNED })),
  unpinnedBoth: migratePrefs(S({ pinned: ['erase'], names: true, seen: DEFAULT_PINNED })).pinned,
  reordered: migratePrefs(S({ pinned: ['upscale', 'quick', 'chat'], names: true, seen: DEFAULT_PINNED })).pinned,
  save: withFixed(['inpaint', 'chat']),
}))
