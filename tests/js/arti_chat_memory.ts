// #385 behavior harness: chat memory intents (mock ask) + apply through real memory APIs.
import { files, g } from './comfy_stub'
import * as M from '../../src/memory'
import {
  applyChatMemoryIntent,
  intentFromLlmJson,
  parseChatMemoryIntent,
  runChatMemoryEdit,
  type AskFn,
} from '../../src/home/artiChatMemory'

const ls: Record<string, string> = {}
;(globalThis as any).localStorage = {
  getItem: (k: string) => (k in ls ? ls[k] : null),
  setItem: (k: string, v: string) => { ls[k] = String(v) },
  removeItem: (k: string) => { delete ls[k] },
}

const MEM = 'comfyart/memory.json'
const LOG = 'comfyart/memory-log.json'
const META = 'comfyart/memory-meta.json'
const stored = (): any[] => (MEM in files ? JSON.parse(files[MEM]) : [])
const storedLog = (): any[] => (LOG in files ? JSON.parse(files[LOG]) : [])
const fileRev = () => (META in files ? JSON.parse(files[META]).rev ?? 0 : 0)
const stamp = (m: any) => ({ ...m, owner_id: m.owner_id || 'local', workspace_id: m.workspace_id || 'local' })

const fakeStore = {
  read: async () => {
    const { rev: _r, ...meta } = META in files ? JSON.parse(files[META]) : {}
    return { memory: MEM in files ? JSON.parse(files[MEM]).map(stamp) : [], log: LOG in files ? JSON.parse(files[LOG]) : [], meta, rev: fileRev() }
  },
  write: async (next: any, base: number, opId: string) => {
    if (base !== fileRev()) throw new M.MemoryConflict('stale')
    const rev = base + 1
    files[MEM] = JSON.stringify(next.memory.map(stamp))
    files[LOG] = JSON.stringify(next.log)
    files[META] = JSON.stringify({ ...next.meta, rev })
    return { memory: JSON.parse(files[MEM]), log: next.log, meta: { ...next.meta, rev }, rev }
  },
}
;(M as any).setMemoryStore?.(fakeStore)

const reset = (mem: any[] = [], log: any[] = []) => {
  for (const k of Object.keys(files)) delete files[k]
  for (const k of Object.keys(ls)) delete ls[k]
  if (mem.length) files[MEM] = JSON.stringify(mem.map(stamp))
  if (log.length) files[LOG] = JSON.stringify(log)
  files[META] = JSON.stringify({ demoCleanup381: true, rev: mem.length || log.length ? 1 : 0 })
  M.memoryAtom.set([])
  M.memoryLogAtom.set([])
  M.memoryChoiceAtom.set(null)
  M.memoryErrorAtom.set(false)
}

const mem = (id: string, text: string, category = 'taste') => ({ id, text, time: 1, category })

/** Deterministic mock ask for the three AC phrases (+ failure). */
const mockAsk: AskFn = async (prompt) => {
  const msg = prompt.split('User message:\n').pop()?.trim() ?? ''
  if (msg === '我是插画师') return JSON.stringify({ action: 'add', text: '我是插画师', category: 'about' })
  if (msg === '把蓝色改成绿色') return JSON.stringify({ action: 'correct', old: '我喜欢蓝色', new: '我喜欢绿色' })
  if (msg === '忘记我喜欢蓝色' || msg === '忘记我喜欢绿色') {
    const text = msg.includes('绿色') ? '我喜欢绿色' : '我喜欢蓝色'
    return JSON.stringify({ action: 'forget', text })
  }
  if (msg === '???') return 'not-json'
  return JSON.stringify({ action: 'none' })
}

const out: Record<string, unknown> = {}
const T = async (name: string, fn: () => Promise<unknown>) => {
  try { out[name] = await fn() } catch (e) { out[name] = `THROW ${(e as Error).message}` }
}

async function main() {
  await T('parser_add', async () => intentFromLlmJson({ action: 'add', text: '我是插画师', category: 'about' }))
  await T('parser_correct', async () => intentFromLlmJson({ action: 'correct', old: '蓝', new: '绿' }))
  await T('parser_forget', async () => intentFromLlmJson({ action: 'forget', text: '蓝' }))
  await T('parser_bad', async () => intentFromLlmJson(null))
  await T('parser_empty_add', async () => intentFromLlmJson({ action: 'add', text: '  ' }))

  await T('ac2_add', async () => {
    reset()
    await M.loadMemory()
    const r = await runChatMemoryEdit('我是插画师', M.memoryAtom.get(), 'chat', mockAsk)
    const list = M.memoryAtom.get()
    return {
      changed: r.changed,
      action: r.intent.action,
      count: list.length,
      category: list[0]?.category,
      text: list[0]?.text,
      owner: list[0]?.owner_id,
      workspace: list[0]?.workspace_id,
      logAction: storedLog()[0]?.action,
    }
  })

  await T('ac2_correct', async () => {
    reset([mem('b1', '我喜欢蓝色', 'taste')])
    await M.loadMemory()
    const before = M.memoryAtom.get().length
    const r = await runChatMemoryEdit('把蓝色改成绿色', M.memoryAtom.get(), 'chat', mockAsk)
    const list = M.memoryAtom.get()
    return {
      changed: r.changed,
      action: r.intent.action,
      countBefore: before,
      countAfter: list.length,
      text: list[0]?.text,
      logAction: storedLog()[0]?.action,
    }
  })

  await T('ac2_forget', async () => {
    reset([mem('b1', '我喜欢蓝色', 'taste'), mem('b2', '我是插画师', 'about')])
    await M.loadMemory()
    const r = await runChatMemoryEdit('忘记我喜欢蓝色', M.memoryAtom.get(), 'chat', mockAsk)
    const list = M.memoryAtom.get()
    return {
      changed: r.changed,
      action: r.intent.action,
      count: list.length,
      remaining: list.map((m) => m.text),
      logAction: storedLog()[0]?.action,
    }
  })

  await T('ac3_empty', async () => {
    reset([mem('b1', '我喜欢蓝色')])
    await M.loadMemory()
    const r = await runChatMemoryEdit('   ', M.memoryAtom.get(), 'chat', mockAsk)
    return { changed: r.changed, reason: r.intent.action === 'none' ? r.intent.reason : null, count: M.memoryAtom.get().length }
  })

  await T('ac3_parse_fail', async () => {
    reset([mem('b1', '我喜欢蓝色')])
    await M.loadMemory()
    const r = await runChatMemoryEdit('???', M.memoryAtom.get(), 'chat', mockAsk)
    return { changed: r.changed, reason: r.intent.action === 'none' ? r.intent.reason : null, count: M.memoryAtom.get().length }
  })

  await T('ac4_log_three', async () => {
    reset()
    await M.loadMemory()
    await runChatMemoryEdit('我是插画师', M.memoryAtom.get(), 'chat', mockAsk)
    // seed a blue preference then correct then forget the green one
    await M.remember([{ text: '我喜欢蓝色', category: 'taste' }], 'seed')
    await runChatMemoryEdit('把蓝色改成绿色', M.memoryAtom.get(), 'chat', mockAsk)
    await runChatMemoryEdit('忘记我喜欢绿色', M.memoryAtom.get(), 'chat', mockAsk)
    const log = M.memoryLogAtom.get()
    return {
      len: log.length,
      actions: log.map((l) => l.action),
      newestFirst: log.length >= 2 ? log[0].time >= log[1].time : true,
      texts: log.map((l) => l.text),
    }
  })

  await T('mutation_taste_only_would_fail_shape', async () => {
    // documents the anti-pattern the AC mutation checks: always taste/add
    reset()
    await M.loadMemory()
    await M.remember([{ text: '我是插画师', category: 'taste' }], 'chat')
    return { category: M.memoryAtom.get()[0]?.category, action: storedLog()[0]?.action }
  })

  console.log(JSON.stringify(out))
}

main().catch((e) => { console.error(e); process.exit(1) })
