// minimal reactive atom + useValue (the real ones come from tldraw)
import { useSyncExternalStore } from 'react'
export function atom<T>(_n: string, v: T) {
  let x = v
  const subs = new Set<() => void>()
  return { get: () => x, set: (n: T) => { x = n; subs.forEach((f) => f()) }, subscribe: (f: () => void) => { subs.add(f); return () => subs.delete(f) } }
}
export function useValue<T>(a: { get: () => T; subscribe: (f: () => void) => () => void }): T {
  return useSyncExternalStore(a.subscribe, a.get)
}
