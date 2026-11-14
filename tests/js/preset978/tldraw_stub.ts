/** #978 harness: only the runtime helpers agent.ts / skills.ts touch. Types are erased. */
export function atom<T>(_name: string, value: T) {
  let v = value
  return { get: () => v, set: (next: T) => { v = next } }
}
export function createShapeId(id?: string) { return (id ?? 'shape:978') as never }
