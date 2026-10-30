/** #384: compact canvas snapshot attached every agent turn; shares the #382 unified token budget. */
import { MEMORY_POLICY } from './memoryStore'
import { countTokens, unifiedBudget, type UnifiedBudget } from './memoryBudget'

export const MAX_SNAPSHOT_NODES: number =
  (MEMORY_POLICY as { max_snapshot_nodes?: number }).max_snapshot_nodes ?? 40
export const MAX_SNAPSHOT_TOKENS: number =
  (MEMORY_POLICY as { max_snapshot_tokens?: number }).max_snapshot_tokens ?? 1500

/** Minimal node shape the snapshot formatter needs (editor mapping stays outside). */
export interface SnapshotNode {
  id: string
  type: string
  name?: string
  /** Generation model id or display label when known. */
  model?: string
}

export interface SnapshotInput {
  nodes: SnapshotNode[]
  selection: string[]
  /** SaaS-ready ownership defaults; unused for filtering today. */
  owner_id?: string
  workspace_id?: string
  project_id?: string
}

export interface SnapshotResult {
  text: string
  included: number
  omitted: number
  tokens: number
  selection: string[]
  typeCounts: Record<string, number>
  empty: boolean
}

export const EMPTY_SNAPSHOT_TEXT = '空画布'

function typeCountsOf(nodes: SnapshotNode[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const n of nodes) counts[n.type] = (counts[n.type] || 0) + 1
  return counts
}

function typeSummary(counts: Record<string, number>): string {
  return Object.entries(counts)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([t, n]) => `${n} ${t}`)
    .join(', ')
}

function nodeLine(n: SnapshotNode): string {
  const bits = [`- ${n.id} [${n.type}]`]
  if (n.model) bits.push(`model=${n.model}`)
  if (n.name) bits.push(JSON.stringify(n.name))
  return bits.join(' ')
}

function headerOf(total: number, shown: SnapshotNode[], selection: string[], omitted: number): string {
  const sel = selection.length ? selection.join(', ') : '(none)'
  const more = omitted > 0 ? `；另有 ${omitted} 个` : ''
  return `Canvas snapshot: ${total} nodes (${typeSummary(typeCountsOf(shown))}); selected: ${sel}${more}`
}

/** Build a compact snapshot string. Truncates to maxNodes and packs under maxTokens; leftover annotated 「另有 N 个」. */
export function formatCanvasSnapshot(
  input: SnapshotInput,
  opts: { maxNodes?: number; maxTokens?: number; /** false = skip attach (mutation for AC2) */ attach?: boolean } = {},
): SnapshotResult {
  const maxNodes = opts.maxNodes ?? MAX_SNAPSHOT_NODES
  const maxTokens = opts.maxTokens ?? MAX_SNAPSHOT_TOKENS
  if (opts.attach === false) {
    return { text: '', included: 0, omitted: input.nodes.length, tokens: 0, selection: [], typeCounts: {}, empty: true }
  }
  const selection = [...new Set((input.selection || []).filter(Boolean))]
  const nodes = (input.nodes || []).filter((n) => n && n.id)
  const typeCounts = typeCountsOf(nodes)
  if (!nodes.length) {
    const text = EMPTY_SNAPSHOT_TEXT
    return { text, included: 0, omitted: 0, tokens: countTokens(text), selection, typeCounts: {}, empty: true }
  }

  // Prefer selected nodes first so a tight token cap still carries the selection.
  const selectedSet = new Set(selection)
  const ordered = [
    ...nodes.filter((n) => selectedSet.has(n.id)),
    ...nodes.filter((n) => !selectedSet.has(n.id)),
  ]
  let included = ordered.slice(0, Math.max(0, maxNodes))
  let omitted = Math.max(0, nodes.length - included.length)

  const render = (list: SnapshotNode[], more: number) => {
    const head = headerOf(nodes.length, list, selection, more)
    return list.length ? `${head}\n${list.map(nodeLine).join('\n')}` : head
  }

  let text = render(included, omitted)
  while (included.length > 0 && countTokens(text) > maxTokens) {
    included = included.slice(0, -1)
    omitted = nodes.length - included.length
    text = render(included, omitted)
  }
  if (!included.length) {
    // Header-only; if still over cap, fall back to a minimal line.
    text = `Canvas snapshot: ${nodes.length} nodes；另有 ${nodes.length} 个`
    if (selection.length) text += `; selected: ${selection.join(', ')}`
    if (countTokens(text) > maxTokens) text = `Canvas snapshot: ${nodes.length} nodes；另有 ${nodes.length} 个`
  }
  return {
    text,
    included: included.length,
    omitted,
    tokens: countTokens(text),
    selection,
    typeCounts,
    empty: false,
  }
}

export type TrimSegment = 'history' | 'memory' | 'snapshot'

export interface PackInput {
  memoryPrompt: string
  snapshot: string
  text?: string
  imageCount?: number
  historyTexts?: string[]
  window?: number
  countImages?: boolean
}

export interface PackResult {
  memoryPrompt: string
  snapshot: string
  historyTexts: string[]
  budget: UnifiedBudget & { snapshot: number }
  trimmed: TrimSegment[]
}

function bumpOmitted(header: string): string {
  const m = header.match(/另有 (\d+) 个/)
  if (m) return header.replace(/另有 \d+ 个/, `另有 ${Number(m[1]) + 1} 个`)
  return `${header}；另有 1 个`
}

/** Keep order: user text (+images) > snapshot > memory > history.
 * Trim history (oldest first), then memory, then snapshot, until total ≤ budget. */
export function packUnifiedContext(input: PackInput): PackResult {
  let memoryPrompt = input.memoryPrompt || ''
  let snapshot = input.snapshot || ''
  let historyTexts = [...(input.historyTexts ?? [])]
  const trimmed: TrimSegment[] = []
  const text = input.text || ''
  const imageCount = input.imageCount ?? 0
  const countImages = input.countImages !== false
  const window = input.window

  const measure = () => unifiedBudget({ memoryPrompt, text, imageCount, historyTexts, window, countImages, snapshot })

  let budget = measure()
  while (!budget.fits && historyTexts.length) {
    historyTexts = historyTexts.slice(1)
    if (!trimmed.includes('history')) trimmed.push('history')
    budget = measure()
  }
  while (!budget.fits && memoryPrompt) {
    const lines = memoryPrompt.split('\n')
    memoryPrompt = lines.length <= 1 ? '' : lines.slice(0, -1).join('\n')
    if (!trimmed.includes('memory')) trimmed.push('memory')
    budget = measure()
  }
  while (!budget.fits && snapshot && snapshot !== EMPTY_SNAPSHOT_TEXT) {
    const lines = snapshot.split('\n')
    if (lines.length <= 1) {
      snapshot = EMPTY_SNAPSHOT_TEXT
    } else {
      lines[0] = bumpOmitted(lines[0])
      lines.pop()
      snapshot = lines.join('\n')
    }
    if (!trimmed.includes('snapshot')) trimmed.push('snapshot')
    budget = measure()
  }
  if (!budget.fits && snapshot === EMPTY_SNAPSHOT_TEXT) {
    snapshot = ''
    if (!trimmed.includes('snapshot')) trimmed.push('snapshot')
    budget = measure()
  }

  return { memoryPrompt, snapshot, historyTexts, budget, trimmed }
}
