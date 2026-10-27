/** #381: the one memory store interface. All memory reads/writes go through `memoryStore()`; nothing else touches the
 * memory files. The server (`api/memory.py`) closes read-modify-write: a write carries the `rev` it was based on and is
 * checked + written under a server lock, so a stale write gets `MemoryConflict` and the caller re-reads and re-applies.
 * localStorage is only a mirror for home / mock runs where the server route is unreachable. */
import { api } from './comfy'
import { readLocal, writeLocal } from './localPrefs'
import type { Memory, MemoryLog } from './memory'

/** Fixed local defaults (no tenancy / auth yet). owner_id = user_id, workspace_id = project_id; nothing filters on them today. */
export const OWNER_DEFAULT = 'local'
export const WORKSPACE_DEFAULT = 'local'

export interface MemoryMeta { demoCleanup381?: boolean; rev?: number }
export interface MemoryState { memory: Memory[]; log: MemoryLog[]; meta: MemoryMeta; rev: number }
export type MemoryWrite = Omit<MemoryState, 'rev'>
export interface MemoryStore {
  read(): Promise<MemoryState>
  /** Throws MemoryConflict when the store moved past `baseRev`. */
  write(next: MemoryWrite, baseRev: number): Promise<MemoryState>
}
export class MemoryConflict extends Error {}

export const stampRecord = (m: Memory): Memory => ({ ...m, owner_id: m.owner_id || OWNER_DEFAULT, workspace_id: m.workspace_id || WORKSPACE_DEFAULT })

const LOCAL = { memory: 'comfyart.memory.local', log: 'comfyart.memory-log.local', meta: 'comfyart.memory-meta.local' }
function local<T>(key: string, fallback: T): T {
  const raw = readLocal(key)
  if (!raw) return fallback
  try { return JSON.parse(raw) as T } catch { return fallback }
}
const localState = (rev = 0): MemoryState => ({ memory: local<Memory[]>(LOCAL.memory, []), log: local<MemoryLog[]>(LOCAL.log, []), meta: local<MemoryMeta>(LOCAL.meta, {}), rev })
function mirror(s: MemoryWrite) {
  writeLocal(LOCAL.memory, JSON.stringify(s.memory))
  writeLocal(LOCAL.log, JSON.stringify(s.log))
  writeLocal(LOCAL.meta, JSON.stringify(s.meta))
}

interface Wire { memory: Memory[] | null; log: MemoryLog[] | null; meta: MemoryMeta | null; rev: number }
/** null = never written on the server → the local mirror decides; [] is a real "0 memories" (no resurrection). */
const fromWire = (w: Wire): MemoryState => {
  const l = localState(w.rev)
  return { memory: w.memory ?? l.memory, log: w.log ?? l.log, meta: w.meta ?? l.meta, rev: w.rev }
}

export const serverMemoryStore: MemoryStore = {
  async read() {
    try {
      const res = await api('/comfyart/memory')
      if (!res.ok) return localState()
      return fromWire(await res.json())
    } catch {
      return localState()
    }
  },
  async write(next, baseRev) {
    const body = { ...next, memory: next.memory.map(stampRecord) }
    let res: Response
    try {
      res = await api('/comfyart/memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...body, base_rev: baseRev }) })
    } catch {
      mirror(body)  // server unreachable (home / mock): local only
      return { ...body, rev: baseRev }
    }
    if (res.status === 409) throw new MemoryConflict('memory changed since it was read')
    if (!res.ok) throw new Error(`memory write failed: ${res.status}`)
    const saved = fromWire(await res.json())
    mirror(saved)
    return saved
  },
}

let current: MemoryStore = serverMemoryStore
export const memoryStore = () => current
/** Test seam: swap the backing store. */
export function setMemoryStore(store: MemoryStore) { current = store }
