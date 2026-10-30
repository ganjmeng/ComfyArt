import { atom } from 'tldraw'
import { OWNER_DEFAULT, WORKSPACE_DEFAULT } from './memoryStore_stub'

export type NoticeKind = 'task' | 'suggestion' | 'comment' | 'schedule'
export interface Notice {
  id: string; kind: NoticeKind; title: string; body?: string; time: number
  read?: boolean; project: string; chat?: string; srcs?: string[]
  owner_id?: string; workspace_id?: string
}

export const noticesAtom = atom<Notice[]>('notices', [])
let seq = 0

export function currentProject(): string {
  return (globalThis as any).__project ?? 'p1'
}

export function notify(n: Omit<Notice, 'id' | 'time' | 'project'> & { project?: string }) {
  const notice: Notice = {
    id: `n${++seq}`,
    time: Date.now(),
    project: n.project ?? currentProject(),
    ...n,
    owner_id: n.owner_id || OWNER_DEFAULT,
    workspace_id: n.workspace_id || WORKSPACE_DEFAULT,
  }
  noticesAtom.set([notice, ...noticesAtom.get()])
  return Promise.resolve()
}

export const markRead = async (ids?: string[]) => {
  noticesAtom.set(noticesAtom.get().map((n) => (!ids || ids.includes(n.id) ? { ...n, read: true } : n)))
}
export const removeNotice = async (id: string) => {
  noticesAtom.set(noticesAtom.get().filter((n) => n.id !== id))
}
export const clearNotices = async () => { noticesAtom.set([]) }
export const loadNotices = async () => {}
export const pushEnabled = () => false
export const setPush = async () => false
