import { atom } from 'tldraw'

import { api } from './comfy'

// The backend only ever returns whether a key is set, where it comes from and its last 4 characters.
export interface KeyStatus { configured: boolean; source: 'env' | 'settings' | 'none'; last4: string; balance: number | null; error?: 'invalid' | 'network' | 'error' }

export const keyStatusAtom = atom<KeyStatus | null>('wavespeed key', null)
export const keySettingsOpenAtom = atom('wavespeed key settings', false)
export const WAVESPEED_KEYS_URL = 'https://wavespeed.ai/accesskey'
export const WAVESPEED_HISTORY_URL = 'https://wavespeed.ai/history'

export const outOfCredit = (s: KeyStatus | null) => !!s?.configured && s.balance !== null && s.balance <= 0
/** True only after status has loaded and no key is configured. null (still loading) is not "missing". #305 */
export const keyMissing = (s: KeyStatus | null) => !!s && !s.configured


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
  // #305: clear Agent no-key probe + models.enabled without wiping the open chat
  void import('./bot').then((m) => m.refreshBot({ refresh: true })).catch(() => {})
  void import('./wavespeed').then((m) => m.loadCloudModels()).catch(() => {})
  return body as KeyStatus
}

export async function deleteKey(): Promise<void> {
  const res = await api('/comfyart/wavespeed/key', { method: 'DELETE' })
  if (res.ok) {
    keyStatusAtom.set((await res.json()) as KeyStatus)
    void import('./bot').then((m) => m.refreshBot({ refresh: true })).catch(() => {})
    void import('./wavespeed').then((m) => m.loadCloudModels()).catch(() => {})
  }
}

/** #159: source 'estimate' = the price API failed and `price` is the catalog estimate for `tier` (shown as 「估算价」/'Estimated'). */
export interface Estimate { price: number | null; confirm_usd: number; confirm: boolean; source?: 'quote' | 'estimate' | 'unpriced' | 'none'; tier?: string; duration_estimated?: boolean }

/** Estimated cost of a cloud job (backend caches WaveSpeed's /model/price quote for 5 minutes). */
export async function estimateCost(inputs: Record<string, unknown>): Promise<Estimate | null> {
  const res = await fetch('/comfyart/wavespeed/estimate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ inputs }) })
  return res.ok ? res.json() : null
}

/** #397: confirm line in integer UI credits (default 50 = former $0.50). */
export async function getConfirmCredits(): Promise<number> {
  const res = await fetch('/comfyart/wavespeed/confirm')
  return res.ok ? (await res.json()).confirm_credits : 50
}

export async function setConfirmCredits(credits: number): Promise<number> {
  const res = await fetch('/comfyart/wavespeed/confirm', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm_credits: credits }) })
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.error?.message || String(res.status))
  return (await res.json()).confirm_credits
}


