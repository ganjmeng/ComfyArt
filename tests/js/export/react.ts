// useState returns the values queued by the test, in call order (format, scale, background, busy).
export const state: unknown[] = []
let i = 0
// #505: setter calls are recorded (hook index, value) so the harness can wait for the dialog's own "busy -> false"
// (run()'s finally) instead of a fixed sleep; the export button's onClick is `() => void run()` and returns nothing.
export const sets: [number, unknown][] = []
export function resetHooks(values: unknown[]) { state.length = 0; state.push(...values); i = 0; sets.length = 0 }
export function useState<T>(init: T): [T, (v: T) => void] { const k = i++; return [(k < state.length ? state[k] : init) as T, (v: T) => { sets.push([k, v]) }] }
export default { useState }
