/** Test stub for src/llm.ts — no network, no paid API. */
export function stripThink(raw: string): string { return String(raw ?? '') }
export function parseJson(raw: string): Record<string, unknown> | null {
  try {
    const t = String(raw ?? '')
    const i = t.indexOf('{')
    if (i < 0) return null
    let d = 0, q = false
    for (let j = i; j < t.length; j++) {
      const c = t[j]
      if (q) { if (c === '\\') j++; else if (c === '"') q = false }
      else if (c === '"') q = true
      else if (c === '{') d++
      else if (c === '}' && --d === 0) return JSON.parse(t.slice(i, j + 1))
    }
    return JSON.parse(t.slice(i))
  } catch { return null }
}
export async function ask(): Promise<string> {
  throw new Error('llm_stub.ask: inject AskFn in tests — no paid calls')
}
