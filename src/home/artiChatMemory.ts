/** #385: chat-to-edit memory intents (add / correct / forget) via a mockable LLM ask. */
import { ask, parseJson } from '../llm'
import { correct, forget, memoryAtom, remember, type Memory } from '../memory'
import { t } from '../i18n'

export type ChatMemoryCategory = 'about' | 'work' | 'taste' | 'assets'

export type ChatMemoryIntent =
  | { action: 'add'; text: string; category: ChatMemoryCategory }
  | { action: 'correct'; old: string; new: string }
  | { action: 'forget'; text: string }
  | { action: 'none'; reason: 'empty' | 'parse' | 'noop' }

export type AskFn = (prompt: string, system: string, images: string[]) => Promise<string>

const CATS = new Set<string>(['about', 'work', 'taste', 'assets'])

export const CHAT_MEMORY_SYSTEM =
  'You turn one short user message about long-term memory into ONE JSON object and nothing else. ' +
  'Shape: {"action":"add"|"correct"|"forget"|"none","text":"...","category":"about|work|taste|assets","old":"...","new":"..."}. ' +
  'Rules: add = lasting fact about the user (set category; default about); correct = change an existing memory (old + new, both non-empty); ' +
  'forget = remove an existing memory (text = the memory to drop); none = unclear / empty / not about memory. Prefer exact old/text match against Known memories.'

/** Parse the LLM JSON into a typed intent. Exported so tests can exercise the parser without calling ask. */
export function intentFromLlmJson(raw: unknown): ChatMemoryIntent {
  if (!raw || typeof raw !== 'object') return { action: 'none', reason: 'parse' }
  const o = raw as Record<string, unknown>
  const action = String(o.action ?? '')
  if (action === 'add') {
    const text = String(o.text ?? '').trim()
    if (!text) return { action: 'none', reason: 'parse' }
    const cat = String(o.category ?? 'about')
    return { action: 'add', text, category: (CATS.has(cat) ? cat : 'about') as ChatMemoryCategory }
  }
  if (action === 'correct') {
    const old = String(o.old ?? '').trim()
    const next = String(o.new ?? '').trim()
    if (!old || !next) return { action: 'none', reason: 'parse' }
    return { action: 'correct', old, new: next }
  }
  if (action === 'forget') {
    const text = String(o.text ?? '').trim()
    if (!text) return { action: 'none', reason: 'parse' }
    return { action: 'forget', text }
  }
  if (action === 'none') return { action: 'none', reason: 'noop' }
  return { action: 'none', reason: 'parse' }
}

export async function parseChatMemoryIntent(
  utterance: string,
  known: Memory[],
  askFn: AskFn = ask,
): Promise<ChatMemoryIntent> {
  const v = utterance.trim()
  if (!v) return { action: 'none', reason: 'empty' }
  const knownLines = known.length
    ? known.map((m) => `- [${m.category ?? 'about'}] ${m.text}`).join('\n')
    : '(none)'
  try {
    const raw = await askFn(
      `Known memories:\n${knownLines}\n\nUser message:\n${v}`,
      CHAT_MEMORY_SYSTEM,
      [],
    )
    return intentFromLlmJson(parseJson(raw))
  } catch {
    return { action: 'none', reason: 'parse' }
  }
}

export interface ApplyResult {
  changed: number
  intent: ChatMemoryIntent
}

/** Apply a resolved intent through the real memory APIs (owner_id/workspace_id stamped inside remember). */
export async function applyChatMemoryIntent(intent: ChatMemoryIntent, source: string): Promise<ApplyResult> {
  if (intent.action === 'add') {
    const before = memoryAtom.get().length
    await remember([{ text: intent.text, category: intent.category }], source)
    return { changed: Math.max(0, memoryAtom.get().length - before), intent }
  }
  if (intent.action === 'correct') {
    const r = await correct([{ old: intent.old, new: intent.new }], source)
    return { changed: r.changed.length, intent }
  }
  if (intent.action === 'forget') {
    const r = await forget([intent.text], source)
    return { changed: r.changed.length, intent }
  }
  return { changed: 0, intent }
}

/** One-shot: parse then apply. Used by the memory-center chat composer. */
export async function runChatMemoryEdit(
  utterance: string,
  known: Memory[],
  source = t('arti.memory.sourceChat'),
  askFn: AskFn = ask,
): Promise<ApplyResult> {
  const intent = await parseChatMemoryIntent(utterance, known, askFn)
  return applyChatMemoryIntent(intent, source)
}
