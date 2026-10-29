// #381 behavior harness for src/memory.ts: real calls against in-memory userdata + localStorage stubs.
import { files, g } from './comfy_stub'
import { serverMemoryStore } from '../../src/memoryStore'
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
const restart = () => { M.memoryAtom.set([]); M.memoryLogAtom.set([]); (M as any).memoryChoiceAtom?.set(null); failRead = false; failWrite = false; (M as any).memoryToastAtom?.set(null) }
const mem = (id: string, text: string, category = 'about') => ({ id, text, time: 1, category })
// Store stand-in with the server's contract (api/memory.py): [] when never written, rev-checked writes, local defaults
// stamped on records, op_id dedupe; `failRead` / `failWrite` simulate a 500 / an offline POST. `beforeWrite` lets a case slip in another writer (other tab / the agent) between read and write.
class Conflict extends Error {}
let beforeWrite: (() => void) | null = null
let failRead = false
let failWrite = false
const opsSeen: string[] = []
let conflicts = 0
const META = 'comfyart/memory-meta.json'
const fileRev = () => (META in files ? JSON.parse(files[META]).rev ?? 0 : 0)
const stampFake = (m: any) => ({ ...m, owner_id: m.owner_id || 'local', workspace_id: m.workspace_id || 'local' })
const externalDelete = (id: string) => { files[MEM] = JSON.stringify(stored().filter((m: any) => m.id !== id)); files[META] = JSON.stringify({ ...(META in files ? JSON.parse(files[META]) : {}), rev: fileRev() + 1 }) }
const external = (add: any) => { files[MEM] = JSON.stringify([...stored(), stampFake(add)]); files[META] = JSON.stringify({ ...(META in files ? JSON.parse(files[META]) : {}), rev: fileRev() + 1 }) }
const fakeStore = {
  read: async () => {
    if (failRead) throw new M.MemoryReadError('500')
    const { rev: _r, ...meta } = META in files ? JSON.parse(files[META]) : {}
    return { memory: MEM in files ? JSON.parse(files[MEM]).map(stampFake) : [], log: LOG in files ? JSON.parse(files[LOG]) : [], meta, rev: fileRev() }
  },
  write: async (next: any, base: number, opId: string) => {
    await Promise.resolve()
    if (failWrite) throw new M.MemoryWriteError('offline')
    opsSeen.push(opId)
    if (beforeWrite) { const f = beforeWrite; beforeWrite = null; f() }
    if (base !== fileRev()) { conflicts++; const C = (M as any).MemoryConflict ?? Conflict; throw new C('stale') }
    const rev = base + 1
    files[MEM] = JSON.stringify(next.memory.map(stampFake)); files[LOG] = JSON.stringify(next.log); files[META] = JSON.stringify({ ...next.meta, rev })
    return { memory: JSON.parse(files[MEM]), log: next.log, meta: { ...next.meta, rev }, rev }
  },
}
;(M as any).setMemoryStore?.(fakeStore)
const out: Record<string, unknown> = {}
const kind = (e: unknown) => (e instanceof M.MemoryWriteError ? 'MemoryWriteError' : e instanceof M.MemoryReadError ? 'MemoryReadError' : e instanceof M.MemoryConflict ? 'MemoryConflict' : `other:${(e as Error)?.message}`)
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
      for (let i = 0; i < 3; i++) { restart(); await M.loadMemory(); if (has('ensureArtiDemoMemories')) await (M as any).ensureArtiDemoMemories(); r.push([M.memoryAtom.get().length, stored().length, (M as any).memoryErrorAtom?.get() ? 1 : 0]) }
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
    // EL MUST 1: offline write → explicit failure + 保存失败 toast; nothing looks saved (atom and store unchanged)
    await T('offline_write', async () => {
      reset([mem('a', 'A')])
      await M.loadMemory()
      failWrite = true
      const results: string[] = []
      for (const op of [() => M.remember([{ text: 'new', category: 'taste' }], 'ui'), () => M.removeMemory('a', 'ui'), () => M.updateMemory('a', 'A2', 'ui')]) {
        try { await op(); results.push('resolved') } catch (e) { results.push(kind(e)) }
      }
      const toast = (M as any).memoryToastAtom?.get()
      failWrite = false
      return { results, atom: M.memoryAtom.get().map((m: any) => m.text), file: stored().map((m: any) => m.text), toast: toast?.text ?? null, kind: toast?.kind ?? null }
    })
    // the real HTTP store: offline POST is resent once with the SAME op_id (idempotent), then fails loudly
    await T('server_offline', async () => {
      const bodies: any[] = []
      g.__check = (b: any) => { bodies.push(b); throw new TypeError('Failed to fetch') }
      let err = ''
      try { await serverMemoryStore.write({ memory: [], log: [], meta: {} }, 0, 'op-x') } catch (e) { err = kind(e) }
      g.__check = (b: any) => { bodies.push(b); return { ok: true, status: 200, json: async () => ({ memory: [], log: [], meta: {}, rev: 1 }) } }
      let n = 0
      g.__check = (b: any) => { bodies.push(b); if (n++ === 0) throw new TypeError('timeout after commit'); return { ok: true, status: 200, json: async () => ({ memory: [], log: [], meta: {}, rev: 1, replayed: true }) } }
      const ok = await serverMemoryStore.write({ memory: [], log: [], meta: {} }, 0, 'op-y')
      g.__check = undefined
      return { err, attempts: bodies.filter((b) => b.op_id === 'op-x').length, sameOp: bodies.every((b) => b.op_id === 'op-x' || b.op_id === 'op-y'), retriedRev: ok.rev }
    })
    // EL MUST 2: read error → server is truth: error state, nothing shown, deleted memory never comes back
    await T('read_error', async () => {
      reset([mem('a', 'A'), mem('b', 'B')])
      await M.loadMemory()
      await M.removeMemory('a', 'ui')
      ls['comfyart.memory.local'] = JSON.stringify([mem('a', 'A'), mem('b', 'B')])  // an old local copy must be ignored
      restart(); failRead = true
      const got = await M.loadMemory()
      const during = { atom: M.memoryAtom.get().length, error: (M as any).memoryErrorAtom?.get() ?? null, returned: got.length }
      failRead = false
      await M.loadMemory()
      return { during, after: M.memoryAtom.get().map((m: any) => m.id), errorAfter: (M as any).memoryErrorAtom?.get() ?? null }
    })
    await T('server_read_500', async () => {
      try { await serverMemoryStore.read(); return 'resolved' } catch (e) { return kind(e) }
    })
    // EL MUST 3: conflict → the edit is re-applied on the fresh read, never the stale snapshot resent
    await T('conflict_replay', async () => {
      reset([mem('a', 'A'), mem('b', 'B')])
      await M.loadMemory()
      beforeWrite = () => externalDelete('b')  // another tab deletes b between our read and write
      await M.updateMemory('a', 'A-edit', 'ui')
      const ops = new Set(opsSeen.slice(-2)).size
      return { file: stored().map((m: any) => m.text), atom: M.memoryAtom.get().map((m: any) => m.text), distinctOps: ops }
    })
    // ---- the REAL client store (serverMemoryStore → api()) against a fake HTTP server with api/memory.py's contract ----
    const srv = { memory: [] as any[], log: [] as any[], meta: {} as any, rev: 0, ops: [] as string[], posts: [] as any[], gets: 0, offline: false, readFail: false, before: null as null | (() => void) }
    const resp = (status: number, body: any) => ({ ok: status < 400, status, json: async () => body })
    const state = () => ({ memory: srv.memory, log: srv.log, meta: srv.meta, rev: srv.rev })
    g.__server = async (_url: string, init?: { body: string }) => {
      if (!init) { srv.gets++; return srv.readFail ? resp(500, {}) : resp(200, state()) }
      const b = JSON.parse(init.body); srv.posts.push(b)
      if (srv.offline) throw new TypeError('Failed to fetch')
      if (srv.before) { const f = srv.before; srv.before = null; f() }
      if (srv.ops.includes(b.op_id)) return resp(200, { ...state(), replayed: true })
      if (b.base_rev !== srv.rev) return resp(409, { error: 'conflict' })
      Object.assign(srv, { memory: b.memory, log: b.log, meta: b.meta, rev: srv.rev + 1 }); srv.ops.push(b.op_id)
      return resp(200, state())
    }
    const real = async (seed: any[], fn: () => Promise<unknown>) => {
      Object.assign(srv, { memory: seed, log: [], meta: { demoCleanup381: true }, rev: 7, ops: [], posts: [], gets: 0, offline: false, readFail: false, before: null })
      for (const k of Object.keys(ls)) delete ls[k]
      restart(); ;(M as any).setMemoryStore?.(serverMemoryStore)
      try { return await fn() } finally { ;(M as any).setMemoryStore?.(fakeStore) }
    }
    // EL#1 (real store): offline write must fail loudly; it must not look saved and must not vanish later
    await T('real_offline', () => real([mem('a', 'A')], async () => {
      await M.loadMemory()
      srv.offline = true  // POSTs throw like a dropped connection
      let res = 'resolved'
      try { await M.remember([{ text: 'new', category: 'taste' }], 'ui') } catch (e) { res = kind(e) }
      const atomDuring = M.memoryAtom.get().map((m: any) => m.text)
      const toast = (M as any).memoryToastAtom?.get()?.text ?? null
      srv.offline = false
      restart(); await M.loadMemory()
      return { res, atomDuring, toast, server: srv.memory.map((m: any) => m.text), posts: srv.posts.length }
    }))
    // EL#2 (real store): read error → no local mirror, no resurrection; after recovery writes succeed (no 409 loop)
    await T('real_read_error', () => real([mem('b', 'B')], async () => {
      ls['comfyart.memory.local'] = JSON.stringify([mem('a', 'deleted-elsewhere'), mem('b', 'B')])
      ls['comfyart.memory-meta.local'] = JSON.stringify({ demoCleanup381: true })  // 83393be's mirror keys
      srv.readFail = true
      await M.loadMemory().catch(() => null)
      const during = { atom: M.memoryAtom.get().map((m: any) => m.text), error: !!(M as any).memoryErrorAtom?.get() }
      srv.readFail = false
      await M.loadMemory()
      let w = 'ok'
      try { await M.remember([{ text: 'C', category: 'taste' }], 'ui') } catch (e) { w = kind(e) }
      return { during, after: M.memoryAtom.get().map((m: any) => m.text).sort(), write: w, server: srv.memory.map((m: any) => m.text).sort(), conflicts409: srv.posts.length - srv.ops.length }
    }))
    // EL#3 (real store): after a 409 the client re-reads and re-applies the edit; it never resends the stale body
    await T('real_conflict', () => real([mem('a', 'A'), mem('b', 'B')], async () => {
      await M.loadMemory()
      srv.before = () => { srv.memory = srv.memory.filter((m: any) => m.id !== 'b'); srv.rev++ }  // another tab deletes b
      let w = 'ok'
      // saveMemory (83393be's whole-list write) was the stale-resend path; it is gone now, updateMemory is the edit API
      const edit = has('saveMemory') ? () => (M as any).saveMemory(M.memoryAtom.get().map((m: any) => (m.id === 'a' ? { ...m, text: 'A-edit' } : m))) : () => M.updateMemory('a', 'A-edit', 'ui')
      try { await edit() } catch (e) { w = kind(e) }
      const bodies = srv.posts.map((p: any) => JSON.stringify({ m: p.memory, r: p.base_rev }))
      return { write: w, server: srv.memory.map((m: any) => m.text), posts: srv.posts.length, distinctBodies: new Set(bodies).size, revs: srv.posts.map((p: any) => p.base_rev), getsAfterConflict: srv.gets }
    }))
    g.__server = undefined
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
    conflicts = 0
    await Promise.all(ops().map((op) => op()))
    const conc = snap()
    return { equal: JSON.stringify(serial) === JSON.stringify(conc), serial: serial.length, concurrent: conc.length, lost: serial.filter((x) => !conc.includes(x)).length, selfConflicts: conflicts }
  })
  // #423: write-side dedupe for the agent's memory add
  await T('upsert_423', async () => {
    reset([mem('a', '常用画幅：16:9'), mem('b', '偏好极简')])
    await M.loadMemory()
    const r = await M.upsertMemory([{ text: '偏好极简' }, { text: '常用画幅：9:16' }, { text: '品牌色：克莱因蓝' }, { text: '品牌色：克莱因蓝' }], 'agent')
    return { added: r.added.map((m) => m.text), updated: r.updated.map((u) => [u.memory.id, u.old, u.memory.text]), unchanged: r.unchanged.map((m) => m.id), file: stored().map((m: any) => m.text) }
  })
  console.log(JSON.stringify(out))
}
void main()
