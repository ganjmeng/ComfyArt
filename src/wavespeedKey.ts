import { atom } from 'tldraw'

import { api } from './comfy'

// The backend only ever returns whether a key is set, where it comes from and its last 4 characters.
export interface KeyStatus { configured: boolean; source: 'env' | 'settings' | 'none'; last4: string; balance: number | null; error?: 'invalid' | 'network' | 'error' }

export const keyStatusAtom = atom<KeyStatus | null>('wavespeed key', null)
export const keySettingsOpenAtom = atom('wavespeed key settings', false)
export const WAVESPEED_KEYS_URL = 'https://wavespeed.ai/accesskey'

export const outOfCredit = (s: KeyStatus | null) => !!s?.configured && s.balance !== null && s.balance <= 0

export async function refreshKeyStatus(): Promise<KeyStatus | null> {
  const res = await api('/comfyart/wavespeed/key').catch(() => null)
  if (!res?.ok) return keyStatusAtom.get()
  const status = (await res.json()) as KeyStatus
  keyStatusAtom.set(status)
  return status
}

export class KeyError extends Error {
  constructor(message: string, readonly reason: string) { super(message) }
}

export async function saveKey(key: string): Promise<KeyStatus> {
  const res = await api('/comfyart/wavespeed/key', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key }) })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new KeyError(body?.error?.message ?? `save failed: ${res.status}`, body?.error?.reason ?? 'error')
  keyStatusAtom.set(body as KeyStatus)
  return body as KeyStatus
}

export async function deleteKey(): Promise<void> {
  const res = await api('/comfyart/wavespeed/key', { method: 'DELETE' })
  if (res.ok) keyStatusAtom.set((await res.json()) as KeyStatus)
}
