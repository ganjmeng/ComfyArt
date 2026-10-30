// #384 behavior harness: canvas snapshot per turn + shared #382 unified budget. Mock only.
import { files } from './comfy_stub'
import {
  EMPTY_SNAPSHOT_TEXT, formatCanvasSnapshot, MAX_SNAPSHOT_NODES, MAX_SNAPSHOT_TOKENS, packUnifiedContext,
  type SnapshotNode,
} from '../../src/canvasSnapshot'
import { countTokens, IMAGE_TOKENS, MAX_INJECT, MAX_INJECT_TOKENS, unifiedBudget } from '../../src/memoryBudget'

const T = async (name: string, fn: () => any | Promise<any>) => {
  ;(globalThis as any).__got = (globalThis as any).__got || {}
  ;(globalThis as any).__got[name] = await fn()
}

const node = (id: string, type: string, model?: string, name?: string): SnapshotNode => ({
  id, type, ...(model ? { model } : {}), ...(name ? { name } : {}),
})

const sample5 = (): SnapshotNode[] => [
  node('img:1', 'image', 'Flux Dev'),
  node('img:2', 'image', 'Flux Schnell'),
  node('img:3', 'image', 'SDXL'),
  node('txt:1', 'text', undefined, '标题'),
  node('frm:1', 'frame', undefined, '画板'),
]

await T('constants', () => ({
  MAX_SNAPSHOT_NODES, MAX_SNAPSHOT_TOKENS, MAX_INJECT, MAX_INJECT_TOKENS, IMAGE_TOKENS, EMPTY_SNAPSHOT_TEXT,
}))

// AC1: 5 nodes / select 2 → snapshot carries counts, models, exact selection
await T('ac1_five_nodes', () => {
  const nodes = sample5()
  const selection = ['img:1', 'frm:1']
  const snap = formatCanvasSnapshot({ nodes, selection, owner_id: 'local', workspace_id: 'local', project_id: 'p1' })
  const mutAllSel = formatCanvasSnapshot({ nodes, selection: nodes.map((n) => n.id) }) // mutation: selection = all
  return {
    text: snap.text,
    included: snap.included,
    omitted: snap.omitted,
    tokens: snap.tokens,
    selection: snap.selection,
    typeCounts: snap.typeCounts,
    hasModels: /Flux Dev/.test(snap.text) && /SDXL/.test(snap.text),
    hasTypes: /3 image/.test(snap.text) && /1 text/.test(snap.text) && /1 frame/.test(snap.text),
    selectionExact: snap.selection.length === 2 && snap.selection.includes('img:1') && snap.selection.includes('frm:1'),
    // mutation red: using all node ids as selection
    mutSelectionAll: {
      selLen: mutAllSel.selection.length,
      red: mutAllSel.selection.length === nodes.length,
    },
  }
})

// AC2: every turn attaches a fresh snapshot reflecting latest canvas
await T('ac2_every_turn', () => {
  let nodes = sample5()
  const turns: { text: string; count: number }[] = []
  // turn 1
  turns.push({ text: formatCanvasSnapshot({ nodes, selection: ['img:1'] }).text, count: nodes.length })
  // turn 2 — delete one
  nodes = nodes.filter((n) => n.id !== 'img:3')
  turns.push({ text: formatCanvasSnapshot({ nodes, selection: ['img:1'] }).text, count: nodes.length })
  // turn 3
  turns.push({ text: formatCanvasSnapshot({ nodes, selection: ['img:1'] }).text, count: nodes.length })

  // mutation: only attach on first turn
  const mut = [0, 1, 2].map((i) => {
    const n = i === 0 ? sample5() : sample5().filter((x) => x.id !== 'img:3')
    return formatCanvasSnapshot({ nodes: n, selection: ['img:1'] }, { attach: i === 0 }).text
  })
  return {
    turns,
    everyTurnAttached: turns.every((t) => t.text.length > 0 && /Canvas snapshot|空画布/.test(t.text)),
    counts: turns.map((t) => t.count),
    turn3Has4: turns[2].count === 4 && /4 nodes/.test(turns[2].text),
    mutFirstOnly: {
      attached: mut.map((t) => t.length > 0),
      red: mut[0].length > 0 && mut[1].length === 0 && mut[2].length === 0,
    },
  }
})

// AC3: 300 nodes → truncated + 「另有 N 个」; tokens ≤ max. Mutation: no node cap → red
await T('ac3_trunc', () => {
  const nodes = Array.from({ length: 300 }, (_, i) => node(`n:${i}`, i % 2 ? 'image' : 'text', i % 2 ? `M${i}` : undefined))
  const snap = formatCanvasSnapshot({ nodes, selection: ['n:0', 'n:1'] })
  const noCap = formatCanvasSnapshot({ nodes, selection: ['n:0'] }, { maxNodes: 9999, maxTokens: 999999 })
  return {
    included: snap.included,
    omitted: snap.omitted,
    tokens: snap.tokens,
    underCap: snap.included <= MAX_SNAPSHOT_NODES,
    hasMore: /另有 \d+ 个/.test(snap.text),
    tokensOk: snap.tokens <= MAX_SNAPSHOT_TOKENS,
    mutNoCap: {
      included: noCap.included,
      tokens: noCap.tokens,
      red: noCap.included > MAX_SNAPSHOT_NODES || noCap.tokens > MAX_SNAPSHOT_TOKENS,
    },
  }
})

// AC4: snapshot counted in shared budget; trim history → memory → snapshot
await T('ac4_budget', () => {
  const nodes = sample5()
  const snap = formatCanvasSnapshot({ nodes, selection: ['img:1'] })
  const memoryPrompt = Array.from({ length: 30 }, (_, i) => `- mem${i}: ` + '偏好描述。'.repeat(20)).join('\n')
  const history = Array.from({ length: 40 }, (_, i) => `历史${i}：` + '设计讨论。'.repeat(30))
  const text = '请根据画布继续设计'
  const window = 4000
  const withSnap = unifiedBudget({ memoryPrompt, snapshot: snap.text, text, historyTexts: history, window })
  const noSnap = unifiedBudget({ memoryPrompt, snapshot: '', text, historyTexts: history, window }) // mutation: not counted
  const packed = packUnifiedContext({ memoryPrompt, snapshot: snap.text, text, historyTexts: history, window })
  return {
    withSnap,
    noSnap,
    snapshotCounted: withSnap.snapshot > 0 && withSnap.total > noSnap.total,
    mutNotCounted: {
      undercount: noSnap.total < withSnap.total && noSnap.snapshot === 0,
      red: noSnap.total < withSnap.total,
    },
    packed: {
      fits: packed.budget.fits,
      trimmed: packed.trimmed,
      orderOk: (() => {
        const t = packed.trimmed
        const iH = t.indexOf('history')
        const iM = t.indexOf('memory')
        const iS = t.indexOf('snapshot')
        // history before memory before snapshot when all present; missing segments ok
        if (iH >= 0 && iM >= 0 && iH > iM) return false
        if (iM >= 0 && iS >= 0 && iM > iS) return false
        if (iH >= 0 && iS >= 0 && iH > iS) return false
        return packed.budget.fits
      })(),
      snapshotKeptOrTrimmedLast: packed.trimmed[0] !== 'snapshot' || packed.trimmed.length === 1,
    },
  }
})

// AC5: empty canvas → 「空画布」
await T('ac5_empty', () => {
  const snap = formatCanvasSnapshot({ nodes: [], selection: [] })
  return {
    text: snap.text,
    empty: snap.empty,
    tokens: snap.tokens,
    ok: snap.text === EMPTY_SNAPSHOT_TEXT && snap.empty === true,
  }
})

console.log(JSON.stringify((globalThis as any).__got))
