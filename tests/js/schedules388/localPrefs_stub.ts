const m = new Map<string, string>()
export const readLocal = (k: string) => m.get(k) ?? null
export const writeLocal = (k: string, v: string) => { m.set(k, v) }
