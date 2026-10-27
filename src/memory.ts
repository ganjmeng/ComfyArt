import { atom } from 'tldraw'

import { readUserJson, writeUserJson } from './comfy'
import { t } from './i18n'
import { uuid } from './id'
import { readLocal, writeLocal } from './localPrefs'

export interface Memory { id: string; text: string; time: number; category?: string; label?: string }
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

export function memoryPrompt(): string {
  const memory = memoryAtom.get()
  if (!memory.length) return ''
  const groups = [...MEMORY_CATEGORIES.map(([id, , en]) => [en, memory.filter((m) => m.category === id)] as const), ['Other', memory.filter((m) => !m.category || !CATEGORY_IDS.includes(m.category))] as const]
  return `Remembered about the user (respect these):\n${groups.filter(([, list]) => list.length).map(([en, list]) => `${en}:\n${list.map((m) => `- ${m.text}`).join('\n')}`).join('\n')}`
}

const FILE = 'comfyart/memory.json'
const LOG_FILE = 'comfyart/memory-log.json'

export const memoryAtom = atom<Memory[]>('memory', [])
export const memoryLogAtom = atom<MemoryLog[]>('memory log', [])

const LOCAL_FILE = 'comfyart.memory.local'
const LOCAL_LOG = 'comfyart.memory-log.local'

function readLocalJson<T>(key: string, fallback: T): T {
  const raw = readLocal(key)
  if (!raw) return fallback
  try { return JSON.parse(raw) as T } catch { return fallback }
}

async function readMemoryStore(): Promise<[Memory[], MemoryLog[]]> {
  try {
    return await Promise.all([readUserJson<Memory[]>(FILE, []), readUserJson<MemoryLog[]>(LOG_FILE, [])])
  } catch {
    return [readLocalJson<Memory[]>(LOCAL_FILE, []), readLocalJson<MemoryLog[]>(LOCAL_LOG, [])]
  }
}

async function writeMemoryStore(list: Memory[], log?: MemoryLog[]) {
  writeLocal(LOCAL_FILE, JSON.stringify(list))
  if (log) writeLocal(LOCAL_LOG, JSON.stringify(log))
  try {
    await writeUserJson(FILE, list)
    if (log) await writeUserJson(LOG_FILE, log)
  } catch {
    /* home / mock: localStorage is the demo persistence layer */
  }
}

export async function loadMemory(): Promise<Memory[]> {
  const [list, log] = await readMemoryStore()
  // Prefer userdata; if empty, fall back to local demo layer
  const localList = readLocalJson<Memory[]>(LOCAL_FILE, [])
  const localLog = readLocalJson<MemoryLog[]>(LOCAL_LOG, [])
  const merged = list.length ? list : localList
  const mergedLog = log.length ? log : localLog
  memoryAtom.set(merged)
  memoryLogAtom.set(mergedLog)
  return merged
}

export async function logMemory(entries: Omit<MemoryLog, 'time'>[]) {
  if (!entries.length) return
  const next = [...entries.map((e) => ({ ...e, time: Date.now() })), ...memoryLogAtom.get()]
  memoryLogAtom.set(next)
  await writeMemoryStore(memoryAtom.get(), next)
}

const same = (a: string, b: string) => a === b || a.includes(b) || b.includes(a)

export async function forget(texts: string[], source: string): Promise<string[]> {
  const list = await loadMemory()
  const gone = list.filter((m) => texts.some((t) => t.trim() && same(m.text, t.trim())))
  if (!gone.length) return []
  await saveMemory(list.filter((m) => !gone.includes(m)))
  await logMemory(gone.map((m) => ({ action: 'forget' as const, text: m.text, source })))
  return gone.map((m) => m.text)
}

export async function correct(items: Correction[], source: string): Promise<string[]> {
  const list = await loadMemory()
  const done: string[] = []
  const next = list.map((m) => {
    const c = items.find((x) => same(m.text, x.old))
    if (!c) return m
    done.push(`${m.text} → ${c.new}`)
    return { ...m, text: c.new, time: Date.now() }
  })
  if (!done.length) return []
  await saveMemory(next)
  await logMemory(done.map((text) => ({ action: 'update' as const, text, source })))
  return done
}

export async function saveMemory(list: Memory[]) {
  memoryAtom.set(list)
  await writeMemoryStore(list, memoryLogAtom.get())
}

/** Update one memory by id (inline edit). Persists via saveMemory. */
export async function updateMemory(id: string, text: string, source: string): Promise<boolean> {
  const list = await loadMemory()
  const prev = list.find((m) => m.id === id)
  if (!prev || prev.text === text) return false
  const next = list.map((m) => (m.id === id ? { ...m, text, time: Date.now() } : m))
  await saveMemory(next)
  await logMemory([{ action: 'update', text: `${prev.text} → ${text}`, source }])
  return true
}

/** Delete one memory by id with persistence. */
export async function removeMemory(id: string, source: string): Promise<boolean> {
  const list = await loadMemory()
  const gone = list.find((m) => m.id === id)
  if (!gone) return false
  await saveMemory(list.filter((m) => m.id !== id))
  await logMemory([{ action: 'forget', text: gone.text, source }])
  return true
}

/** Seed CN-aligned demo memories when the store is empty (mock-first demo layer). */
export async function ensureArtiDemoMemories(): Promise<Memory[]> {
  const list = await loadMemory()
  if (list.length) return list
  const demo: MemoryInput[] = [
    { category: 'about', label: '创作领域', text: '你长期从事咖啡与茶饮品牌的视觉内容创作，常涉及品牌识别、海报、包装及周边视觉。' },
    { category: 'work', label: '指令风格', text: '你习惯用简短直接的方式下达任务，不附加长篇背景，中英文交流都是如此。' },
    { category: 'work', label: '输出形式', text: '信息类任务里，你只要文字输出，不自动生成图片。' },
    { category: 'work', label: '确认方式', text: '关键步骤希望先出方案再动手；不确定时先问你。' },
    { category: 'taste', label: '视觉风格', text: '偏好极简、几何构成与克莱因蓝方向，少装饰、强留白。' },
  ]
  await remember(demo, 'arti-demo')
  return memoryAtom.get()
}

export async function remember(items: MemoryInput[], source = t('botCommands.chat')) {
  const known = new Set((await loadMemory()).map((m) => m.text))
  const fresh = items.filter((m) => !known.has(m.text))
  if (!fresh.length) return
  await saveMemory([...memoryAtom.get(), ...fresh.map((m) => ({ id: uuid().slice(0, 8), text: m.text, time: Date.now(), ...(m.category ? { category: m.category } : {}), ...(m.label ? { label: m.label } : {}) }))])
  await logMemory(fresh.map((m) => ({ action: 'add' as const, text: m.text, source })))
}
