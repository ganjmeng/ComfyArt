import { atom } from 'tldraw'
export const botEnabledAtom = atom<boolean | null>('bot enabled', true)
export const settingsAtom = atom<Record<string, string | boolean | number>>('bot settings', {
  'proactive-review': true,
  'proactive-daily': 10,
  'proactive-memory': false,
  'proactive-skills': false,
  'memory-enabled': true,
})
export type BotMessage = { id: string; parent_id: string | null; blocks: { type: string; text?: string }[] }
export async function announceMemoryUpdated() {}
