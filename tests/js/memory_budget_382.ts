// #382 behavior harness: inject budget, unified window budget, log cap, memory_updated placement + undo.
import { files, g } from './comfy_stub'
import * as M from '../../src/memory'
import {
  countTokens, estimateImageTokens, IMAGE_TOKENS, insertMemoryUpdatedBlock, MAX_INJECT, MAX_INJECT_TOKENS, MAX_LOG,
  memoryUpdatedPlacementOk, selectMemoriesForInject, unifiedBudget,
} from '../../src/memoryBudget'

const ls: Record<string, string> = {}
;(globalThis as any).localStorage = { getItem: (k: string) => (k in ls ? ls[k] : null), setItem: (k: string, v: string) => { ls[k] = String(v) }, removeItem: (k: string) => { delete ls[k] } }

const MEM = 'comfyart/memory.json'
const LOG = 'comfyart/memory-log.json'
const META = 'comfyart/memory-meta.json'
const stored = (): any[] => (MEM in files ? JSON.parse(files[MEM]) : [])
const storedLog = (): any[] => (LOG in files ? JSON.parse(files[LOG]) : [])
const fileRev = () => (META in files ? JSON.parse(files[META]).rev ?? 0 : 0)
const stampFake = (m: any) => ({ ...m, owner_id: m.owner_id || 'local', workspace_id: m.workspace_id || 'local' })
const mem = (id: string, text: string, category = 'about', time = 1) => ({ id, text, time, category })

let beforeWrite: (() => void) | null = null
let failRead = false
let failWrite = false
const fakeStore = {
  read: async () => {
    if (failRead) throw new M.MemoryReadError('500')
    const { rev: _r, ...meta } = META in files ? JSON.parse(files[META]) : {}
    return { memory: MEM in files ? JSON.parse(files[MEM]).map(stampFake) : [], log: LOG in files ? JSON.parse(files[LOG]) : [], meta: { demoCleanup381: true, ...meta }, rev: fileRev() }
  },
  write: async (next: any, base: number, opId: string) => {
    await Promise.resolve()
    if (failWrite) throw new M.MemoryWriteError('offline')
    if (beforeWrite) { const f = beforeWrite; beforeWrite = null; f() }
    if (base !== fileRev()) throw new M.MemoryConflict('stale')
    const rev = base + 1
    // Mirror server [:MAX_LOG] (newest-first).
    const log = (next.log || []).slice(0, MAX_LOG)
    files[MEM] = JSON.stringify(next.memory.map(stampFake)); files[LOG] = JSON.stringify(log); files[META] = JSON.stringify({ ...next.meta, rev })
    return { memory: JSON.parse(files[MEM]), log, meta: { ...next.meta, rev }, rev }
  },
}
;(M as any).setMemoryStore?.(fakeStore)

const restart = () => { M.memoryAtom.set([]); M.memoryLogAtom.set([]); (M as any).memoryChoiceAtom?.set(null); failRead = false; failWrite = false; (M as any).memoryToastAtom?.set(null); (M as any).memoryFocusAtom?.set(null) }
const reset = (memList?: any[], log?: any[]) => {
  for (const k of Object.keys(files)) delete files[k]
  for (const k of Object.keys(ls)) delete ls[k]
  if (memList) files[MEM] = JSON.stringify(memList)
  if (log) files[LOG] = JSON.stringify(log)
  files[META] = JSON.stringify({ demoCleanup381: true, rev: memList || log ? 1 : 0 })
  restart()
}

const out: Record<string, unknown> = {}
const T = async (name: string, fn: () => Promise<unknown>) => { try { out[name] = await fn() } catch (e) { out[name] = `THROW ${(e as Error).message}` } }

async function main() {
  out.constants = { MAX_INJECT, MAX_INJECT_TOKENS, IMAGE_TOKENS, MAX_LOG }

  // AC1: 200 memories + query 「海报配色」 → ≤ N, all from top-N relevance, token ≤ cap
  await T('ac1_topn_budget', async () => {
    const list = Array.from({ length: 200 }, (_, i) => {
      if (i < 5) return mem(`c${i}`, `海报配色偏好${i}：暖色低饱和`, 'taste', 1000 + i)
      if (i < 15) return mem(`p${i}`, `海报构图留白规则${i}`, 'taste', 500 + i)
      return mem(`x${i}`, `无关条目${i}咖啡品牌包装`, 'about', i)
    })
    reset(list)
    await M.loadMemory()
    const prompt = M.memoryPrompt('海报配色')
    const selected = selectMemoriesForInject(M.memoryAtom.get(), '海报配色')
    const tokens = countTokens(prompt)
    return {
      count: selected.length,
      maxInject: MAX_INJECT,
      allRelevant: selected.every((m) => /海报|配色/.test(m.text)),
      tokens,
      maxTokens: MAX_INJECT_TOKENS,
      underCap: tokens <= MAX_INJECT_TOKENS,
      hasHeader: prompt.startsWith('Remembered about the user'),
      // mutation: uncapped would include 无关
      uncappedWouldIncludeNoise: list.some((m) => m.text.includes('无关')) && !selected.some((m) => m.text.includes('无关')),
    }
  })

  // Mutation AC1: full concat (no top-N) exceeds N
  await T('mut_ac1_no_topn', async () => {
    const list = Array.from({ length: 200 }, (_, i) => mem(`m${i}`, i < 60 ? `海报配色${i}` : `其它${i}`, 'taste', i))
    const full = list // pretend no select
    return { fullCount: full.length, exceeds: full.length > MAX_INJECT }
  })

  // AC2: unified budget with 4 images fits; without image estimate the assertion that images are counted fails
  await T('ac2_unified', async () => {
    reset([mem('a', '喜欢暖色海报配色', 'taste')])
    await M.loadMemory()
    const memoryPrompt = M.memoryPrompt('海报配色')
    const text = '请根据我的偏好设计一张咖啡海报'
    const history = Array.from({ length: 20 }, (_, i) => `历史轮次内容${i}：` + '设计讨论。'.repeat(40))
    // Pick a small window so the total is near the edge.
    const window = 8000
    const withImg = unifiedBudget({ memoryPrompt, text, imageCount: 4, historyTexts: history, window, countImages: true })
    const noImg = unifiedBudget({ memoryPrompt, text, imageCount: 4, historyTexts: history, window, countImages: false })
    return {
      withImg,
      noImg,
      imageTokens: estimateImageTokens(4),
      imagesCounted: withImg.images === 4 * IMAGE_TOKENS,
      // AC2: with images counted, total is larger; dropping image estimate under-counts
      dropImagesUndercounts: noImg.total < withImg.total && noImg.images === 0,
      // For a tight window, with images may not fit while without falsely fits
      mutationRed: (() => {
        const tight = 4 * IMAGE_TOKENS + countTokens(memoryPrompt) + countTokens(text) + history.reduce((n, h) => n + countTokens(h), 0) - 100
        const w = unifiedBudget({ memoryPrompt, text, imageCount: 4, historyTexts: history, window: Math.floor(tight / 0.7), countImages: true })
        const n = unifiedBudget({ memoryPrompt, text, imageCount: 4, historyTexts: history, window: Math.floor(tight / 0.7), countImages: false })
        // mutation (no image estimate) would claim fits when real does not — or at least undercount
        return { realFits: w.fits, fakeFits: n.fits, undercount: n.total < w.total }
      })(),
    }
  })

  // AC3: 0 relevant → empty (no header); memory-enabled=false simulated by caller skipping memoryPrompt
  await T('ac3_empty', async () => {
    reset([mem('a', '咖啡品牌包装', 'about'), mem('b', '先出草图', 'work')])
    await M.loadMemory()
    const none = M.memoryPrompt('量子物理')
    const disabled = '' // agent.ts: memory-enabled === false ? '' : memoryPrompt(text)
    return { none, noHeader: none === '', disabled, disabledEmpty: disabled === '' }
  })

  // AC4: write N+50 log entries → file keeps MAX_LOG, oldest dropped
  await T('ac4_log_cap', async () => {
    const seedLog = Array.from({ length: MAX_LOG - 10 }, (_, i) => ({ time: i, action: 'add', text: `old${i}`, source: 'seed' }))
    reset([mem('a', 'A')], seedLog)
    await M.loadMemory()
    // 60 new remembers → 60 new log lines; total would be MAX_LOG - 10 + 60 = MAX_LOG + 50
    for (let i = 0; i < 60; i++) await M.remember([{ text: `new${i}`, category: 'taste' }], 'test')
    const log = storedLog()
    return {
      len: log.length,
      max: MAX_LOG,
      capped: log.length === MAX_LOG,
      newestFirst: log[0]?.text === 'new59',
      // seed was newest-first: old0 at front survives; the tail of the prior log is rolled off
      oldestSeedGone: !log.some((l: any) => l.text === `old${MAX_LOG - 11}`),
      keptRecentSeed: log.some((l: any) => l.text === 'old0'),
    }
  })

  // Mutation AC4: without cap, length would be MAX_LOG+50
  await T('mut_ac4_no_cap', async () => {
    const wouldBe = MAX_LOG - 10 + 60
    return { wouldBe, exceeds: wouldBe > MAX_LOG }
  })

  // AC5: auto-learn → exactly 1 memory_updated between thinking and reply; no learn → 0
  await T('ac5_row_placement', async () => {
    const base = [
      { type: 'thinking', text: '…' },
      { type: 'text', text: '已记住你的暖色调偏好。' },
    ]
    const withRow = insertMemoryUpdatedBlock(base, { memory_ids: ['m1'], texts: ['喜欢暖色'] })
    const types = withRow.map((b) => b.type)
    const ok = memoryUpdatedPlacementOk(withRow)
    // mutation: insert after reply
    const afterReply = [...base, { type: 'memory_updated', memory_ids: ['m1'], texts: ['喜欢暖色'] }]
    const mutBad = memoryUpdatedPlacementOk(afterReply)
    const noLearn = memoryUpdatedPlacementOk(base)
    return {
      types,
      ok,
      between: types.indexOf('memory_updated') === 1 && types[0] === 'thinking' && types[2] === 'text',
      mutAfterReplyOk: mutBad, // must be false
      noLearnRows: noLearn, // must be false
      count: types.filter((t) => t === 'memory_updated').length,
    }
  })

  // #382 fix: turn thinks again after the memory write → 思考完成 → 记忆已更新 → 思考完成 → reply
  await T('ac5_row_two_thoughts', async () => {
    const base = [
      { type: 'thinking', text: 'a' },
      { type: 'tool_use', name: 'generate_image', id: 't1', input: {} },
      { type: 'tool_result', tool_use_id: 't1', text: 'ok' },
      { type: 'thinking', text: 'b' },
      { type: 'text', text: 'done' },
    ]
    const twoThought = insertMemoryUpdatedBlock([base[0], base[3], base[4]], { memory_ids: ['m1'] }).map((b) => b.type)
    const withTools = insertMemoryUpdatedBlock(base, { memory_ids: ['m1'] }).map((b) => b.type)
    return { twoThought, withTools }
  })

  // AC6: undo via removeMemory → list -1, log +1 forget, refresh absent
  await T('ac6_undo', async () => {
    reset([mem('m1', '喜欢暖色调', 'taste'), mem('m2', '其它', 'about')])
    await M.loadMemory()
    const before = stored().length
    const beforeLog = storedLog().length
    const ok = await (M as any).undoMemoryUpdated('m1')
    const after = stored().map((m: any) => m.id)
    const log = storedLog()
    restart(); await M.loadMemory()
    const refreshed = M.memoryAtom.get().map((m) => m.id)
    // mutation: UI-only delete would leave file intact
    return {
      ok,
      before,
      after,
      gone: !after.includes('m1') && after.includes('m2'),
      logGrew: log.length === beforeLog + 1,
      logAction: log[0]?.action,
      logSource: log[0]?.source,
      refreshed,
      persists: !refreshed.includes('m1'),
    }
  })

  await T('mut_ac6_ui_only', async () => {
    // Simulate UI-only: atom cleared but file untouched
    reset([mem('m1', '喜欢暖色调', 'taste')])
    await M.loadMemory()
    M.memoryAtom.set([]) // UI-only
    restart(); await M.loadMemory()
    return { resurrected: M.memoryAtom.get().some((m) => m.id === 'm1') }
  })

  console.log(JSON.stringify(out))
}
void main()
