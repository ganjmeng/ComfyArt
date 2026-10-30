/** #386: Arti notification feed for canvas-review cards. Storage goes through this interface
 * (JSON today → DB later). Records carry owner_id + workspace_id (+ project_id). */
import { atom } from 'tldraw'

import { readUserJson, writeUserJson } from './comfy'
import { uuid } from './id'
import { OWNER_DEFAULT, WORKSPACE_DEFAULT } from './memoryStore'
import { currentProject } from './notices'

export interface ReviewCard {
  id: string
  kind: 'review'
  title: string
  issues: string[]
  time: number
  project_id: string
  owner_id: string
  workspace_id: string
  read?: boolean
}

export interface ReviewFeedStore {
  read(): Promise<ReviewCard[]>
  write(cards: ReviewCard[]): Promise<void>
}

const FILE = 'comfyart/review-feed.json'
const MAX = 50

const stamp = (c: Omit<ReviewCard, 'id' | 'time' | 'owner_id' | 'workspace_id' | 'project_id'> & Partial<Pick<ReviewCard, 'id' | 'time' | 'owner_id' | 'workspace_id' | 'project_id'>>): ReviewCard => ({
  id: c.id ?? uuid().slice(0, 8),
  kind: 'review',
  title: c.title,
  issues: c.issues,
  time: c.time ?? Date.now(),
  project_id: c.project_id ?? currentProject(),
  owner_id: c.owner_id ?? OWNER_DEFAULT,
  workspace_id: c.workspace_id ?? WORKSPACE_DEFAULT,
  ...(c.read != null ? { read: c.read } : {}),
})

export const fileReviewFeedStore: ReviewFeedStore = {
  async read() {
    const list = await readUserJson<ReviewCard[]>(FILE, [])
    return Array.isArray(list) ? list.map((c) => stamp(c)) : []
  },
  async write(cards) {
    await writeUserJson(FILE, cards.slice(0, MAX).map((c) => stamp(c)))
  },
}

let store: ReviewFeedStore = fileReviewFeedStore
export const reviewFeedStore = () => store
export function setReviewFeedStore(next: ReviewFeedStore) { store = next }

/** In-memory mirror for the Arti panel (localStorage is cache only — source of truth is the store). */
export const reviewFeedAtom = atom<ReviewCard[]>('review feed', [])

export async function loadReviewFeed() {
  reviewFeedAtom.set(await store.read())
}

export async function postReviewCard(input: { title: string; issues: string[]; project_id?: string }) {
  if (!input.issues.length) return null
  const card = stamp({ kind: 'review', title: input.title, issues: input.issues, project_id: input.project_id })
  const list = [card, ...await store.read()].slice(0, MAX)
  await store.write(list)
  reviewFeedAtom.set(list)
  return card
}

export async function clearReviewFeed() {
  await store.write([])
  reviewFeedAtom.set([])
}

export async function dismissReviewCard(id: string) {
  const list = (await store.read()).filter((c) => c.id !== id)
  await store.write(list)
  reviewFeedAtom.set(list)
}
