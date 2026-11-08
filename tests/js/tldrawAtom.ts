import { useSyncExternalStore } from 'react'

/** LOCAL FIXTURE stand-in. The product Confirm component imports tldraw's atom; this environment cannot load @tldraw/assets. */
type Atom<T> = { get: () => T; set: (next: T) => void; subscribe: (listener: () => void) => () => void }

export function atom<T>(_name: string, initial: T): Atom<T> {
  let value = initial
  const listeners = new Set<() => void>()
  return {
    get: () => value,
    set: (next: T) => { value = next; listeners.forEach((listener) => listener()) },
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener) } },
  }
}

export function useValue<T>(source: Atom<T>): T {
  return useSyncExternalStore(source.subscribe, source.get, source.get)
}
