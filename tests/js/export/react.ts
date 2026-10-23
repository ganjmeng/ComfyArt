// useState returns the values queued by the test, in call order (format, scale, background, busy).
export const state: unknown[] = []
let i = 0
export function resetHooks(values: unknown[]) { state.length = 0; state.push(...values); i = 0 }
export function useState<T>(init: T): [T, (v: T) => void] { const k = i++; return [(k < state.length ? state[k] : init) as T, () => {}] }
export default { useState }
