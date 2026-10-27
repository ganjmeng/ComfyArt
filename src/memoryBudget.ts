/** #382: memory inject budget — top-N by relevance, token cap on the memory segment,
 * unified window budget that also estimates images. Mirrors bot/local_llm.py count_tokens
 * and bot/run_budget.py image_tokens so FE and BE agree. */
import { MEMORY_POLICY } from './memoryStore'

export const MAX_INJECT: number = MEMORY_POLICY.max_inject
export const MAX_INJECT_TOKENS: number = MEMORY_POLICY.max_inject_tokens
export const IMAGE_TOKENS: number = MEMORY_POLICY.image_tokens
export const INPUT_BUDGET_PERCENT: number = MEMORY_POLICY.input_budget_percent
export const FALLBACK_CONTEXT_WINDOW: number = MEMORY_POLICY.fallback_context_window
export const MAX_LOG: number = MEMORY_POLICY.max_log

/** Minimal shape the budget helpers need (avoids a cycle with memory.ts). */
export interface MemoryLike { id: string; text: string; category?: string; time?: number; label?: string }

/** Same rule as bot/local_llm.py count_tokens: CJK/kana/hangul = 1; other chars = 1/4 (ceil). */
export function countTokens(text: string): number {
  if (!text) return 0
  let cjk = 0, other = 0
  for (const ch of text) {
    const o = ch.codePointAt(0)!
    if ((o >= 0x3400 && o <= 0x9fff) || (o >= 0xf900 && o <= 0xfaff)
      || (o >= 0x3040 && o <= 0x30ff) || (o >= 0xac00 && o <= 0xd7af)
      || (o >= 0xff00 && o <= 0xffef)) cjk++
    else other++
  }
  return cjk + Math.floor((other + 3) / 4)
}

export function estimateImageTokens(n: number): number {
  return Math.max(0, Math.floor(n)) * IMAGE_TOKENS
}

/** 70% of the model window (local_llm.input_token_budget). */
export function inputTokenBudget(window: number = FALLBACK_CONTEXT_WINDOW): number {
  const size = window > 0 ? window : FALLBACK_CONTEXT_WINDOW
  return Math.floor((size * INPUT_BUDGET_PERCENT) / 100)
}

/** Tokenize for relevance: latin words lowercased + each CJK char as its own token. */
export function tokenize(text: string): string[] {
  const out: string[] = []
  const re = /[A-Za-z0-9_]+|[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]/gu
  let m: RegExpExecArray | null
  while ((m = re.exec(text))) {
    const chunk = m[0]
    if (/^[A-Za-z0-9_]+$/.test(chunk)) out.push(chunk.toLowerCase())
    else for (const ch of chunk) out.push(ch)
  }
  return out
}

export function scoreRelevance(text: string, query: string): number {
  const q = new Set(tokenize(query))
  if (!q.size) return 0
  let hits = 0
  for (const tok of new Set(tokenize(text))) if (q.has(tok)) hits++
  return hits
}

export interface SelectOpts { maxItems?: number; maxTokens?: number }

/** Top-N by relevance (then recency), then pack until the memory-segment token budget fills.
 * Empty query → recency only (still capped). Score-0 items are dropped when a query is set. */
export function selectMemoriesForInject<T extends MemoryLike>(list: T[], query = '', opts: SelectOpts = {}): T[] {
  const maxItems = opts.maxItems ?? MAX_INJECT
  const maxTokens = opts.maxTokens ?? MAX_INJECT_TOKENS
  if (!list.length || maxItems <= 0 || maxTokens <= 0) return []
  const q = query.trim()
  const ranked = [...list]
    .map((m, i) => ({ m, score: q ? scoreRelevance(m.text, q) : 1, i }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || (b.m.time ?? 0) - (a.m.time ?? 0) || b.i - a.i)
    .slice(0, maxItems)
    .map((x) => x.m)
  const picked: T[] = []
  let used = 0
  const header = countTokens('Remembered about the user (respect these):\n')
  for (const m of ranked) {
    const line = countTokens(`- ${m.text}\n`)
    const next = picked.length === 0 ? header + line : used + line
    if (next > maxTokens) break
    picked.push(m)
    used = next
  }
  return picked
}

export interface UnifiedBudgetInput {
  memoryPrompt: string
  text?: string
  imageCount?: number
  historyTexts?: string[]
  window?: number
  /** When false, image tokens are omitted (mutation for AC2). Default true. */
  countImages?: boolean
}

export interface UnifiedBudget {
  memory: number
  text: number
  images: number
  history: number
  total: number
  budget: number
  fits: boolean
}

/** Unified token budget: memory + user text + image estimates + history ≤ 70% window. */
export function unifiedBudget(input: UnifiedBudgetInput): UnifiedBudget {
  const memory = countTokens(input.memoryPrompt || '')
  const text = countTokens(input.text || '')
  const images = (input.countImages === false ? 0 : estimateImageTokens(input.imageCount ?? 0))
  const history = (input.historyTexts ?? []).reduce((n, t) => n + countTokens(t || ''), 0)
  const budget = inputTokenBudget(input.window)
  const total = memory + text + images + history
  return { memory, text, images, history, total, budget, fits: total <= budget }
}

export type BlockLike = { type: string; [k: string]: unknown }

/** Insert a memory_updated block between the last thinking block and the first text reply.
 * If there is no thinking, it is placed immediately before the first text (or appended). */
export function insertMemoryUpdatedBlock(
  blocks: BlockLike[],
  payload: { memory_ids: string[]; texts?: string[] },
): BlockLike[] {
  const block: BlockLike = { type: 'memory_updated', memory_ids: payload.memory_ids, texts: payload.texts ?? [] }
  const cleaned = blocks.filter((b) => b.type !== 'memory_updated')
  let thinkEnd = -1
  for (let i = 0; i < cleaned.length; i++) if (cleaned[i].type === 'thinking') thinkEnd = i
  const textStart = cleaned.findIndex((b) => b.type === 'text')
  if (thinkEnd >= 0) {
    const after = thinkEnd + 1
    // Prefer sitting right before the first text that follows thinking.
    const slot = textStart > thinkEnd ? textStart : after
    return [...cleaned.slice(0, slot), block, ...cleaned.slice(slot)]
  }
  if (textStart >= 0) return [...cleaned.slice(0, textStart), block, ...cleaned.slice(textStart)]
  return [...cleaned, block]
}

/** True iff exactly one memory_updated sits between a thinking block and a later text block. */
export function memoryUpdatedPlacementOk(blocks: { type: string }[]): boolean {
  const types = blocks.map((b) => b.type)
  const mu = types.indexOf('memory_updated')
  if (mu < 0) return false
  if (types.filter((t) => t === 'memory_updated').length !== 1) return false
  return types.slice(0, mu).includes('thinking') && types.slice(mu + 1).includes('text')
}
