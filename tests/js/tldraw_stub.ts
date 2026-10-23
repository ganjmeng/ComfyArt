export function atom<T>(_n: string, v: T) { let x = v; return { get: () => x, set: (n: T) => { x = n } } }
