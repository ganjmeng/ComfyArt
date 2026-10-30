import { atom } from 'tldraw'
export const noticesAtom = atom<unknown[]>('notices', [])
export function currentProject() { return (globalThis as any).__project ?? 'p1' }
export async function notify(n: unknown) {
  const g = globalThis as any
  g.__notices = g.__notices ?? []
  g.__notices.push(n)
}
