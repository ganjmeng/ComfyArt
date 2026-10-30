// #389 behavior harness: pure dedupe helpers (no editor, no network).
import { mergeRefIds, removeRefId } from '../../src/refDedupe'
const r: Record<string, unknown> = {}
r.ac1 = mergeRefIds(['A'], [], ['A'])
r.ac2 = mergeRefIds(['A'], [], ['A'])
r.ac2b = mergeRefIds([], [], ['A', 'A'])
r.ac3 = mergeRefIds(['A', 'B'], [], ['A'])
const rm = removeRefId('A', ['A'], [], ['A'])
r.ac4 = mergeRefIds(['A'], rm.hidden, rm.extra)
r.ac5 = mergeRefIds([], [], ['shape:1', 'shape:2'])
console.log(JSON.stringify(r))
