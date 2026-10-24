// #244: fixed tools (chat, quick) are always pinned and first, including for users who unpinned them before
import { migratePrefs, withFixed, FIXED_TOOLS, DEFAULT_PINNED } from '../../src/ui/toolbarPrefs'
const S = (o: unknown) => JSON.stringify(o)
console.log(JSON.stringify({
  fixed: FIXED_TOOLS,
  defaults: DEFAULT_PINNED,
  fresh: migratePrefs(null).pinned,
  broken: migratePrefs('{').pinned,
  unpinnedChat: migratePrefs(S({ pinned: ['quick', 'upscale', 'erase'], names: false, seen: DEFAULT_PINNED })),
  unpinnedBoth: migratePrefs(S({ pinned: ['erase'], names: true, seen: DEFAULT_PINNED })).pinned,
  reordered: migratePrefs(S({ pinned: ['upscale', 'quick', 'chat'], names: true, seen: DEFAULT_PINNED })).pinned,
  save: withFixed(['inpaint', 'chat']),
}))
