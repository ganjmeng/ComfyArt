import { atom } from 'tldraw'

import { t } from './i18n'
import { uuid } from './id'
import { backoff, MEMORY_POLICY, MemoryConflict, MemoryReadError, memoryStore, MemoryWriteError, newOpId, OWNER_DEFAULT, WORKSPACE_DEFAULT, type MemoryMeta } from './memoryStore'
import { MAX_INJECT, MAX_INJECT_TOKENS, selectMemoriesForInject } from './memoryBudget'
export { countTokens, estimateImageTokens, IMAGE_TOKENS, inputTokenBudget, insertMemoryUpdatedBlock, MAX_INJECT, MAX_INJECT_TOKENS, MAX_LOG, memoryUpdatedPlacementOk, selectMemoriesForInject, unifiedBudget } from './memoryBudget'

export { MemoryConflict, MemoryReadError, MemoryWriteError, setMemoryStore } from './memoryStore'

/** owner_id (= user_id) and workspace_id (= project_id) carry fixed local defaults (#381); nothing filters on them yet. */
export interface Memory { id: string; text: string; /** ms, stamped by the server on create/update; absent on legacy records */ time?: number; category?: string; label?: string; owner_id?: string; workspace_id?: string }
export interface MemoryInput { text: string; category?: string; label?: string }
export interface MemoryLog { time: number; action: 'add' | 'update' | 'forget' | 'skill'; text: string; source: string }
export interface Correction { old: string; new: string }

export const MEMORY_CATEGORIES: [string, string, string][] = [
  ['about', t('memory.basics'), 'About the user'], ['taste', t('memory.aestheticPreferences'), 'Visual taste'], ['work', t('memory.collaborationStyle'), 'Way of working'], ['assets', t('memory.frequentAssets'), 'Long-term assets'],
]
const CATEGORY_IDS = MEMORY_CATEGORIES.map(([id]) => id)

export function toInputs(value: unknown): MemoryInput[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((v) => {
    const text = typeof v === 'string' ? v : typeof v?.text === 'string' ? v.text : ''
    const category = CATEGORY_IDS.includes(v?.category) ? v.category : undefined
    const label = typeof v?.label === 'string' && v.label.trim() ? v.label.trim() : undefined
    return text.trim() ? [{ text: text.trim(), category, ...(label ? { label } : {}) }] : []
  })
}

/** #382: inject only the top-N relevant memories, capped by max_inject_tokens.
 * Empty query → recency-ordered cap (still budgeted). No relevant hits → '' (no header). */
export function memoryPrompt(query = ''): string {
  const selected = selectMemoriesForInject(memoryAtom.get(), query, { maxItems: MAX_INJECT, maxTokens: MAX_INJECT_TOKENS })
  return formatMemoryPrompt(selected)
}

export function formatMemoryPrompt(selected: Memory[]): string {
  if (!selected.length) return ''
  const groups = [...MEMORY_CATEGORIES.map(([id, , en]) => [en, selected.filter((m) => m.category === id)] as const), ['Other', selected.filter((m) => !m.category || !CATEGORY_IDS.includes(m.category))] as const]
  return `Remembered about the user (respect these):\n${groups.filter(([, list]) => list.length).map(([en, list]) => `${en}:\n${list.map((m) => `- ${m.text}`).join('\n')}`).join('\n')}`
}


export const memoryAtom = atom<Memory[]>('memory', [])
export const memoryLogAtom = atom<MemoryLog[]>('memory log', [])
/** #381: a text edit that matched several memories waits here for the user to pick one (nothing is written). */
export interface MemoryChoice { action: 'forget' | 'correct'; text: string; next?: string; candidates: Memory[]; source: string }
export const memoryChoiceAtom = atom<MemoryChoice | null>('memory choice', null)

const MAX_LOG = MEMORY_POLICY.max_log
/** #381: the server could not be read. The list is cleared (never a stale/local copy) and the UI shows an error state. */
/** #433: a display load is in flight (memory dialog skeleton). */
export const memoryLoadingAtom = atom<boolean>('memory loading', false)
/** #433: a manual save is in flight — pill shows 「记忆更新中」; the id (if any) is the entry being saved (dimmed). */
export const memorySavingAtom = atom<{ id?: string } | null>('memory saving', null)
function saving<T>(id: string | undefined, p: Promise<T>): Promise<T> {
  memorySavingAtom.set({ id })
  return p.finally(() => memorySavingAtom.set(null))
}
export const memoryErrorAtom = atom<boolean>('memory error', false)
/** #381: one transient toast (delete done / save failed). */
export interface MemoryToastState { text: string; kind: 'deleted' | 'error'; key: number }
export const memoryToastAtom = atom<MemoryToastState | null>('memory toast', null)
let toastTimer: ReturnType<typeof setTimeout> | undefined
export function showMemoryToast(text: string, kind: MemoryToastState['kind'] = 'deleted') {
  clearTimeout(toastTimer)
  memoryToastAtom.set({ text, kind, key: Date.now() })
  toastTimer = setTimeout(() => memoryToastAtom.set(null), 2400)
}

/** #382: open the memory dialog focused on one id (from 「记忆已更新 ›」). undoable → show revoke. */
export interface MemoryFocus { id: string; undoable?: boolean }
export const memoryFocusAtom = atom<MemoryFocus | null>('memory focus', null)


/** #381: the five memories the old empty-state demo seeded (by text; their ids were random). Cleanup only, never written. */
export const DEMO_SEED_TEXTS: readonly string[] = [
  '你长期从事咖啡与茶饮品牌的视觉内容创作，常涉及品牌识别、海报、包装及周边视觉。',
  '你习惯用简短直接的方式下达任务，不附加长篇背景，中英文交流都是如此。',
  '信息类任务里，你只要文字输出，不自动生成图片。',
  '关键步骤希望先出方案再动手；不确定时先问你。',
  '偏好极简、几何构成与克莱因蓝方向，少装饰、强留白。',
]
/** Seed ids, when known. The old seeding used random ids, so this stays empty and text decides. */
export const DEMO_SEED_IDS: readonly string[] = []

/** #381: one in-tab queue for every read-modify-write; the server's rev check (api/memory.py) covers other tabs and
 * the agent. A stale write (MemoryConflict) re-runs the whole step on fresh data. */
let queue: Promise<unknown> = Promise.resolve()
function serial<T>(fn: () => Promise<T>): Promise<T> {
  const attempt = async (n: number): Promise<T> => {
    try { return await fn() } catch (e) {
      if (e instanceof MemoryConflict && n < MEMORY_POLICY.max_retries) { await new Promise((r) => setTimeout(r, backoff(n))); return attempt(n + 1) }
      // never look saved: a write that did not land (offline / server error / conflicts exhausted) is reported
      if (e instanceof MemoryWriteError || e instanceof MemoryConflict || e instanceof MemoryReadError) showMemoryToast(t('memory.saveFailed'), 'error')
      throw e
    }
  }
  const run = queue.then(() => attempt(0), () => attempt(0))
  queue = run.catch(() => undefined)
  return run
}

type Meta = MemoryMeta
let rev = 0
let meta: Meta = {}

/** Only ever called inside serial() right after loadUnlocked(), so list/log/rev are this attempt's fresh read. */
async function writeStore(list: Memory[], log: MemoryLog[], nextMeta?: Meta) {
  const saved = await memoryStore().write({ memory: list, log, meta: nextMeta ?? meta }, rev, newOpId())
  rev = saved.rev
  meta = saved.meta
  memoryAtom.set(saved.memory)
  memoryLogAtom.set(saved.log)
}

const isSeed = (m: Memory) => DEMO_SEED_IDS.includes(m.id) || DEMO_SEED_TEXTS.includes(m.text)
const entry = (action: MemoryLog['action'], text: string, source: string): MemoryLog => ({ action, text, source, time: Date.now() })
const withLog = (log: MemoryLog[], add: MemoryLog[]) => [...add.reverse(), ...log].slice(0, MAX_LOG)

/** Load, and once per store drop the old demo seeds (#381). Must run inside serial(). */
async function loadUnlocked(): Promise<Memory[]> {
  let state
  try {
    state = await memoryStore().read()
  } catch (e) {
    memoryErrorAtom.set(true)
    memoryAtom.set([])
    memoryLogAtom.set([])
    throw e
  }
  memoryErrorAtom.set(false)
  const { memory: list, log } = state
  rev = state.rev
  meta = state.meta
  if (!meta.demoCleanup381) {
    const kept = list.filter((m) => !isSeed(m))
    const removed = list.length - kept.length
    const nextLog = removed ? withLog(log, [entry('forget', t('memory.demoCleanup', removed), 'demo-cleanup-381')]) : log
    await writeStore(kept, nextLog, { ...meta, demoCleanup381: true })
    return kept
  }
  memoryAtom.set(list)
  memoryLogAtom.set(log)
  return list
}

/** Load for display. A read failure resolves to [] with memoryErrorAtom set (error state, no toast). */
export function loadMemory(): Promise<Memory[]> {
  const run = queue.then(() => loadUnlocked(), () => loadUnlocked())
  queue = run.catch(() => undefined)
  memoryLoadingAtom.set(true)
  void run.finally(() => memoryLoadingAtom.set(false)).catch(() => undefined)
  return run.catch(async (e) => {
    if (!(e instanceof MemoryReadError)) throw e
    return []
  })
}

export function logMemory(entries: Omit<MemoryLog, 'time'>[]) {
  if (!entries.length) return Promise.resolve()
  return serial(async () => {
    const list = await loadUnlocked()
    await writeStore(list, withLog(memoryLogAtom.get(), entries.map((e) => entry(e.action, e.text, e.source))))
  })
}

/** Result of a text/id edit. `candidates` is set (and nothing written) when the text matched several memories. */
export interface EditResult { changed: string[]; candidates?: Memory[]; rejected?: string }

function pick(list: Memory[], key: { id?: string; text?: string }): Memory[] {
  if (key.id) return list.filter((m) => m.id === key.id)
  const text = key.text?.trim() ?? ''
  return text ? list.filter((m) => m.text === text) : []
}

/** Forget by id or exact text. Several exact matches: no write, candidates returned so the user picks. */
export function forget(texts: (string | { id?: string; text?: string })[], source: string): Promise<EditResult> {
  return serial(async () => {
    const list = await loadUnlocked()
    const gone: Memory[] = []
    for (const raw of texts) {
      const key = typeof raw === 'string' ? { text: raw } : raw
      if (!key.id && !key.text?.trim()) return { changed: [], rejected: 'empty text' }
      const hit = pick(list, key)
      if (hit.length > 1) {
        memoryChoiceAtom.set({ action: 'forget', text: key.text ?? '', candidates: hit, source })
        return { changed: [], candidates: hit }
      }
      gone.push(...hit)
    }
    if (!gone.length) return { changed: [] }
    await writeStore(list.filter((m) => !gone.includes(m)), withLog(memoryLogAtom.get(), gone.map((m) => entry('forget', m.text, source))))
    return { changed: gone.map((m) => m.text) }
  })
}

/** Correct by id or exact old text. Empty old/new is rejected; several matches: no write, candidates returned. */
export function correct(items: (Correction & { id?: string })[], source: string): Promise<EditResult> {
  return serial(async () => {
    const list = await loadUnlocked()
    const plan: [Memory, string][] = []
    for (const c of items) {
      const next = String(c.new ?? '').trim()
      if ((!c.id && !String(c.old ?? '').trim()) || !next) return { changed: [], rejected: 'old and new must be non-empty' }
      const hit = pick(list, { id: c.id, text: c.old })
      if (hit.length > 1) {
        memoryChoiceAtom.set({ action: 'correct', text: c.old, next, candidates: hit, source })
        return { changed: [], candidates: hit }
      }
      if (hit[0] && hit[0].text !== next) plan.push([hit[0], next])
    }
    if (!plan.length) return { changed: [] }
    const done = plan.map(([m, n]) => `${m.text} → ${n}`)
    await writeStore(list.map((m) => { const p = plan.find(([x]) => x === m); return p ? { ...m, text: p[1] } : m }),
      withLog(memoryLogAtom.get(), done.map((d) => entry('update', d, source))))
    return { changed: done }
  })
}

/** Update one memory by id (inline edit). */
export async function updateMemory(id: string, text: string, source: string): Promise<boolean> {
  return (await saving(id, correct([{ id, old: '', new: text }], source))).changed.length > 0
}

/** Delete one memory by id with persistence. */
export async function removeMemory(id: string, source: string): Promise<boolean> {
  return (await saving(id, forget([{ id }], source))).changed.length > 0
}

export function remember(items: MemoryInput[], source = t('botCommands.chat')): Promise<Memory[]> {
  return serial(async () => {
    const list = await loadUnlocked()
    const known = new Set(list.map((m) => m.text))
    const fresh = items.filter((m) => !known.has(m.text) && (known.add(m.text), true))
    if (!fresh.length) return []
    const added: Memory[] = fresh.map((m) => ({ id: uuid().slice(0, 8), text: m.text, owner_id: OWNER_DEFAULT, workspace_id: WORKSPACE_DEFAULT, ...(m.category ? { category: m.category } : {}), ...(m.label ? { label: m.label } : {}) }))
    await writeStore([...list, ...added], withLog(memoryLogAtom.get(), added.map((m) => entry('add', m.text, source))))
    return added
  })
}

/** #382: revoke a memory learned from the chat row. Logs forget with source memory-updated-undo. */
export function undoMemoryUpdated(id: string): Promise<boolean> {
  return removeMemory(id, 'memory-updated-undo')
}

// e2e seam for the chooser interaction test (tests/test_e2e_memory_381.py); inert unless localStorage['comfyart.e2e'] === '1'
try { if (globalThis.localStorage?.getItem('comfyart.e2e') === '1') (globalThis as { __comfyartMemory?: unknown }).__comfyartMemory = { forget, correct, load: loadMemory, list: () => memoryAtom.get(), log: () => memoryLogAtom.get() } } catch { /* no storage */ }
