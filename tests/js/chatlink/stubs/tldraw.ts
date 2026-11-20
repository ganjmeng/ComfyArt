export function atom<T>(_name: string, value: T) {
  let current = value
  return { get: () => current, set: (next: T) => { current = next } }
}

export function react(_name: string, _fn: () => void) {
  return () => {}
}
