import { atom } from 'tldraw'

import { readUserJson, writeUserJson } from './comfy'
import { uuid } from './id'
import { readLocal, writeLocal } from './localPrefs'
import { OWNER_DEFAULT, WORKSPACE_DEFAULT } from './memoryStore'

export type NoticeKind = 'task' | 'suggestion' | 'comment' | 'schedule'
export interface Notice { id: string; kind: NoticeKind; title: string; body?: string; time: number; read?: boolean; project: string; chat?: string; srcs?: string[]; owner_id?: string; workspace_id?: string }

const FILE = 'comfyart/notices.json'
const MAX_NOTICES = 200
const PUSH_KEY = 'comfyart.notify'
const channel = new BroadcastChannel('comfyart-notices')

export const noticesAtom = atom<Notice[]>('notices', [])

export function currentProject(): string {
  return new URL(location.href).searchParams.get('project') ?? ''
}

export function pushEnabled() {
  return readLocal(PUSH_KEY) === '1'
}

export async function setPush(on: boolean) {
  const next = on && (await Notification.requestPermission()) === 'granted'
  writeLocal(PUSH_KEY, next ? '1' : '0')
  return next
}

const read = () => readUserJson<Notice[]>(FILE, [])

export async function loadNotices() {
  noticesAtom.set(await read())
}

async function update(fn: (list: Notice[]) => Notice[]) {
  const list = fn(await read()).slice(0, MAX_NOTICES)
  noticesAtom.set(list)
  await writeUserJson(FILE, list)
  channel.postMessage('changed')
}

channel.onmessage = () => void loadNotices()

export function notify(n: Omit<Notice, 'id' | 'time' | 'project'> & { project?: string }) {
  const notice: Notice = {
    id: uuid().slice(0, 8), time: Date.now(), project: currentProject(),
    ...n,
    owner_id: n.owner_id || OWNER_DEFAULT, workspace_id: n.workspace_id || WORKSPACE_DEFAULT,
  }
  if (document.hidden && pushEnabled() && Notification.permission === 'granted') {
    new Notification(notice.title, { body: notice.body, icon: notice.srcs?.[0] })
  }
  return update((list) => [notice, ...list])
}

export const markRead = (ids?: string[]) => update((list) => list.map((n) => (!ids || ids.includes(n.id) ? { ...n, read: true } : n)))
export const removeNotice = (id: string) => update((list) => list.filter((n) => n.id !== id))
export const clearNotices = () => update(() => [])
