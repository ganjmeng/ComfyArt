// #381 behavior harness for src/memory.ts: real calls against in-memory userdata + localStorage stubs.
import { files } from './comfy_stub'
import * as M from '../../src/memory'
import { artiCapOn } from '../../src/home/artiCaps'

const ls: Record<string, string> = {}
;(globalThis as any).localStorage = { getItem: (k: string) => (k in ls ? ls[k] : null), setItem: (k: string, v: string) => { ls[k] = String(v) }, removeItem: (k: string) => { delete ls[k] } }

const MEM = 'comfyart/memory.json'
const LOG = 'comfyart/memory-log.json'
const SEEDS = ['你长期从事咖啡与茶饮品牌的视觉内容创作，常涉及品牌识别、海报、包装及周边视觉。', '你习惯用简短直接的方式下达任务，不附加长篇背景，中英文交流都是如此。', '信息类任务里，你只要文字输出，不自动生成图片。', '关键步骤希望先出方案再动手；不确定时先问你。', '偏好极简、几何构成与克莱因蓝方向，少装饰、强留白。']
const stored = (): any[] => (MEM in files ? JSON.parse(files[MEM]) : [])
const storedLog = (): any[] => (LOG in files ? JSON.parse(files[LOG]) : [])
const reset = (mem?: any[], extra: Record<string, string> = {}) => {
  for (const k of Object.keys(files)) delete files[k]
  for (const k of Object.keys(ls)) delete ls[k]
  if (mem) files[MEM] = JSON.stringify(mem)
  Object.assign(files, extra)
  restart()
}
/** a page reload: in-memory atoms are gone, persisted files stay */
const restart = () => { M.memoryAtom.set([]); M.memoryLogAtom.set([]); (M as any).memoryChoiceAtom?.set(null) }
const mem = (id: string, text: string, category = 'about') => ({ id, text, time: 1, category })
// Store stand-in with the server's contract (api/memory.py): null when never written, rev-checked writes, local defaults
// stamped on records. `beforeWrite` lets a case slip in another writer (other tab / the agent) between read and write.
class Conflict extends Error {}
let beforeWrite: (() => void) | null = null
const META = 'comfyart/memory-meta.json'
const fileRev = () => (META in files ? JSON.parse(files[META]).rev ?? 0 : 0)
const stampFake = (m: any) => ({ ...m, owner_id: m.owner_id || 'local', workspace_id: m.workspace_id || 'local' })
const external = (add: any) => { files[MEM] = JSON.stringify([...stored(), stampFake(add)]); files[META] = JSON.stringify({ ...(META in files ? JSON.parse(files[META]) : {}), rev: fileRev() + 1 }) }
const fakeStore = {
  read: async () => {
    const st = { memory: MEM in files ? JSON.parse(files[MEM]).map(stampFake) : null, log: LOG in files ? JSON.parse(files[LOG]) : null, meta: META in files ? JSON.parse(files[META]) : null }
    const loc = (k: string, d: any) => (ls[k] ? JSON.parse(ls[k]) : d)
    return { memory: st.memory ?? loc('comfyart.memory.local', []), log: st.log ?? loc('comfyart.memory-log.local', []), meta: st.meta ?? loc('comfyart.memory-meta.local', {}), rev: fileRev() }
  },
  write: async (next: any, base: number) => {
    await Promise.resolve()
    if (beforeWrite) { const f = beforeWrite; beforeWrite = null; f() }
    if (base !== fileRev()) { const C = (M as any).MemoryConflict ?? Conflict; throw new C('stale') }
    const rev = base + 1
    files[MEM] = JSON.stringify(next.memory.map(stampFake)); files[LOG] = JSON.stringify(next.log); files[META] = JSON.stringify({ ...next.meta, rev })
    ls['comfyart.memory.local'] = files[MEM]
    return { memory: JSON.parse(files[MEM]), log: next.log, meta: { ...next.meta, rev }, rev }
  },
}
;(M as any).setMemoryStore?.(fakeStore)
const out: Record<string, unknown> = {}
const T = async (name: string, fn: () => Promise<unknown>) => { try { out[name] = await fn() } catch (e) { out[name] = `THROW ${(e as Error).message}` } }

async function main() {
  const has = (k: string) => typeof (M as any)[k] === 'function'
  const onlyConcurrency = process.env.ONLY === 'concurrency'

  if (!onlyConcurrency) {
    // (1) empty open → 0 written; delete-all + refresh x3 → 0
    await T('empty_open', async () => {
      reset()
      await M.loadMemory()
      if (has('ensureArtiDemoMemories')) await (M as any).ensureArtiDemoMemories() // what the old empty state did
      return { atom: M.memoryAtom.get().length, file: stored().length }
    })
    await T('delete_all_refresh3', async () => {
      reset([mem('a', 'A'), mem('b', 'B')])
      await M.loadMemory()
      for (const m of [...M.memoryAtom.get()]) await M.removeMemory(m.id, 'ui')
      const r = []
      for (let i = 0; i < 3; i++) { restart(); await M.loadMemory(); if (has('ensureArtiDemoMemories')) await (M as any).ensureArtiDemoMemories(); r.push([M.memoryAtom.get().length, stored().length, JSON.parse(ls['comfyart.memory.local'] ?? '[]').length]) }
      return r
    })
    await T('no_local_resurrection', async () => {
      // userdata says 0 (after deleting the last one); localStorage still has an old copy
      reset([], {})
      ls['comfyart.memory.local'] = JSON.stringify([mem('old', 'OLD')])
      await M.loadMemory()
      return { atom: M.memoryAtom.get().length, file: stored().length }
    })
    // (2) migration: 5 seeds + 1 seed edited by one char + 3 user → 4 remain, verbatim; run-once
    await T('migration', async () => {
      const users = [mem('u1', '我是插画师', 'about'), { id: 'u2', text: '喜欢暖色', time: 7, category: 'taste', label: '色彩' }, mem('u3', '先出草图', 'work')]
      const edited = mem('s6', SEEDS[2].replace('文字', '文本'), 'work')
      reset([...SEEDS.map((t, i) => mem(`seed${i}`, t, 'work')), edited, ...users])
      await M.loadMemory()
      const after1 = stored()
      const logAfter1 = storedLog().filter((l) => l.source === 'demo-cleanup-381').length
      for (let i = 0; i < 3; i++) { restart(); await M.loadMemory() }
      // user later saves a seed text themselves: run-once means it is theirs and stays
      await M.remember([{ text: SEEDS[0], category: 'about' }], 'user')
      for (let i = 0; i < 3; i++) { restart(); await M.loadMemory() }
      return {
        kept: after1.map((m: any) => m.id),
        verbatim: JSON.stringify(after1.filter((m: any) => m.id.startsWith('u')).map(({ owner_id: _o, workspace_id: _w, ...m }: any) => m)) === JSON.stringify(users),
        stamped: after1.every((m: any) => m.owner_id === 'local' && m.workspace_id === 'local'),
        editedKept: after1.some((m: any) => m.id === 's6'),
        logAfterFirst: logAfter1,
        logAfterRestarts: storedLog().filter((l) => l.source === 'demo-cleanup-381').length,
        logText: storedLog().find((l) => l.source === 'demo-cleanup-381')?.text,
        userSeedSurvives: stored().some((m: any) => m.text === SEEDS[0]),
      }
    })
    // (3) id delete / multi-match / correct old:''
    await T('delete_by_id', async () => {
      reset([mem('a', '喜欢蓝色'), mem('b', '喜欢蓝色调的海报'), mem('c', '其他')])
      await M.loadMemory()
      await M.removeMemory('a', 'ui')
      return stored().map((m: any) => m.id)
    })
    await T('substring_not_matched', async () => {
      reset([mem('a', '喜欢蓝色调的海报'), mem('b', '蓝色')])
      await M.loadMemory()
      await M.forget(['蓝色'], 'agent')
      return stored().map((m: any) => m.id)
    })
    await T('multi_match', async () => {
      reset([mem('a', '喜欢蓝色'), mem('b', '喜欢蓝色'), mem('c', '其他')])
      await M.loadMemory()
      const before = files[MEM]
      const f: any = await M.forget(['喜欢蓝色'], 'agent')
      const c: any = await M.correct([{ old: '喜欢蓝色', new: '喜欢红色' }], 'agent')
      return { unchanged: files[MEM] === before, forgetCandidates: (f?.candidates ?? []).map((m: any) => m.id), correctCandidates: (c?.candidates ?? []).map((m: any) => m.id), chooser: (M as any).memoryChoiceAtom?.get()?.candidates?.length ?? 0 }
    })
    await T('correct_empty_old', async () => {
      reset([mem('a', 'A'), mem('b', 'B')])
      await M.loadMemory()
      const before = files[MEM]
      const r: any = await M.correct([{ old: '', new: 'X' }], 'agent')
      return { unchanged: files[MEM] === before, changed: r?.changed?.length ?? r?.length ?? 0, rejected: !!r?.rejected }
    })
    // (5) deleted memory absent from next prompt
    await T('prompt_after_delete', async () => {
      reset([mem('a', '讨厌渐变'), mem('b', '喜欢留白', 'taste')])
      await M.loadMemory()
      const before = M.memoryPrompt().includes('讨厌渐变')
      await M.removeMemory('a', 'ui')
      restart(); await M.loadMemory()
      return { before, after: M.memoryPrompt().includes('讨厌渐变'), keeps: M.memoryPrompt().includes('喜欢留白') }
    })
    // another writer lands between our read and our write → stale write rejected, step re-run on fresh data, nothing lost
    await T('external_writer', async () => {
      reset([mem('a', 'A')])
      await M.loadMemory()
      beforeWrite = () => external(mem('x', 'from-agent'))
      await M.remember([{ text: 'from-ui', category: 'taste' }], 'ui')
      beforeWrite = () => external(mem('y', 'from-tab2'))
      await M.removeMemory('a', 'ui')
      return stored().map((m: any) => m.text).sort()
    })
    // /arti switches mirror api/settings
    await T('arti_caps', async () => {
      const s = JSON.parse(process.env.SETTINGS || '{}')
      return { memory: artiCapOn('memory', s), skills: artiCapOn('skills', s), memOn: artiCapOn('memory', { ...s, 'proactive-memory': true }) }
    })
  }

  // (4) 50 proactive remember + 50 UI edits, concurrent vs serial
  await T('concurrency', async () => {
    const base = Array.from({ length: 50 }, (_, i) => mem(`u${i}`, `u${i}`))
    const ops = () => Array.from({ length: 50 }, (_, i) => [
      () => M.remember([{ text: `p${i}`, category: 'taste' }], 'proactive'),
      () => M.updateMemory(`u${i}`, `u${i}-edited`, 'ui'),
    ]).flat()
    const snap = () => stored().map((m: any) => m.text).sort()
    reset(base); await M.loadMemory()
    for (const op of ops()) await op()
    const serial = snap()
    reset(base); await M.loadMemory()
    await Promise.all(ops().map((op) => op()))
    const conc = snap()
    return { equal: JSON.stringify(serial) === JSON.stringify(conc), serial: serial.length, concurrent: conc.length, lost: serial.filter((x) => !conc.includes(x)).length }
  })
  console.log(JSON.stringify(out))
}
void main()
