/** #381: the one memory store interface. All memory reads/writes go through `memoryStore()`; nothing else touches the
 * memory file. The server (`api/memory.py`) is the only truth:
 * - read: any failure throws `MemoryReadError` (no local copy is ever shown, so a deleted memory cannot come back);
 * - write: carries the `rev` it was based on (stale → `MemoryConflict`, the caller re-reads and re-applies its edit) and
 *   an `op_id` idempotency key, so a POST that timed out after the server committed can be resent safely. A write that
 *   still fails throws `MemoryWriteError`; nothing is shown as saved. */
import policy from '../api/memory_policy.json'
import { api } from './comfy'
import type { Memory, MemoryLog } from './memory'
import { uuid } from './id'

/** Fixed local defaults (no tenancy / auth yet). owner_id = user_id, workspace_id = project_id; nothing filters on them today. */
export const OWNER_DEFAULT: string = policy.owner_default
export const WORKSPACE_DEFAULT: string = policy.workspace_default
export const MEMORY_POLICY = policy

export interface MemoryMeta { demoCleanup381?: boolean }
export interface MemoryState { memory: Memory[]; log: MemoryLog[]; meta: MemoryMeta; rev: number }
export type MemoryWrite = Omit<MemoryState, 'rev'>
export interface MemoryStore {
  /** Throws MemoryReadError when the server cannot answer. */
  read(): Promise<MemoryState>
  /** Throws MemoryConflict when the store moved past `baseRev`, MemoryWriteError when the write did not land. */
  write(next: MemoryWrite, baseRev: number, opId: string): Promise<MemoryState>
}
export class MemoryConflict extends Error {}
export class MemoryReadError extends Error {}
export class MemoryWriteError extends Error {}

export const stampRecord = (m: Memory): Memory => ({ ...m, owner_id: m.owner_id || OWNER_DEFAULT, workspace_id: m.workspace_id || WORKSPACE_DEFAULT })
export const newOpId = () => `${Date.now().toString(36)}-${uuid()}`
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
/** Exponential backoff with full jitter. */
export const backoff = (attempt: number) => Math.random() * Math.min(policy.backoff_max_ms, policy.backoff_base_ms * 2 ** attempt)

interface Wire { memory: Memory[]; log: MemoryLog[]; meta: MemoryMeta; rev: number }
const fromWire = (w: Wire): MemoryState => ({ memory: w.memory ?? [], log: w.log ?? [], meta: w.meta ?? {}, rev: w.rev ?? 0 })

export const serverMemoryStore: MemoryStore = {
  async read() {
    let res: Response
    try { res = await api('/comfyart/memory') } catch (e) { throw new MemoryReadError(String(e)) }
    if (!res.ok) throw new MemoryReadError(`memory read failed: ${res.status}`)
    return fromWire(await res.json())
  },
  async write(next, baseRev, opId) {
    const body = JSON.stringify({ memory: next.memory.map(stampRecord), log: next.log, meta: next.meta, base_rev: baseRev, op_id: opId })
    for (let attempt = 0; ; attempt++) {
      let res: Response
      try {
        res = await api('/comfyart/memory', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body })
      } catch (e) {
        // offline or timed out: the server may or may not have committed. Same op_id → a resend is idempotent.
        if (attempt < policy.network_retries) { await sleep(backoff(attempt)); continue }
        throw new MemoryWriteError(String(e))
      }
      if (res.status === 409) throw new MemoryConflict('memory changed since it was read')
      if (!res.ok) throw new MemoryWriteError(`memory write failed: ${res.status}`)
      return fromWire(await res.json())
    }
  },
}

let current: MemoryStore = serverMemoryStore
export const memoryStore = () => current
/** Test seam: swap the backing store. */
export function setMemoryStore(store: MemoryStore) { current = store }
