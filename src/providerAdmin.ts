/** Per-tool provider settings. Drafts stay on the page until Save. Secrets are never sent. */

import { readLocal, writeLocal } from './localPrefs'

/** Safe save-fail fixture for design/QA shots (gap 4). Opt-in only.
 *  URL `?providerSaveFail=1` or localStorage `comfyart.provider.saveFailMock` = "1".
 *  Forces saveTool / saveToolBatch to reject WITHOUT calling the network — prefs stay untouched.
 *  Plain Error (not ProviderAdminError) → ProviderAdmin failText uses provider.saveFailed. */
const SAVE_FAIL_MOCK_KEY = 'comfyart.provider.saveFailMock'

export function providerSaveFailFixture(): boolean {
  try {
    const q = new URL(location.href).searchParams.get('providerSaveFail')
    if (q === '1' || q === 'true') return true
  } catch { /* SSR / non-browser */ }
  return readLocal(SAVE_FAIL_MOCK_KEY) === '1'
}

export function setProviderSaveFailFixture(on: boolean) {
  if (!on) {
    try { localStorage.removeItem(SAVE_FAIL_MOCK_KEY) } catch { /* */ }
    return
  }
  writeLocal(SAVE_FAIL_MOCK_KEY, '1')
}

function rejectSaveFixture(): Promise<never> {
  return Promise.reject(new Error('provider-save-fail-fixture'))
}


export interface LangText { zh?: string; en?: string }
export interface EndPoint { provider: string; model: string }
export interface ToolRoute { primary: EndPoint; backup: EndPoint | null; fallback: boolean }
export interface ToolChoice { provider: string; model: string; label: LangText; enabled: boolean; quote: string; reason: string; backup?: boolean; backup_reason?: string }
export interface ToolRow {
  id: string
  group: 'image' | 'video' | 'other' | string
  label: LangText
  blurb: LangText
  connected: boolean
  active: ToolRoute | null
  draft: ToolRoute | null
  revision: number
  can_restore: boolean
  choices: ToolChoice[]
  key_ok: boolean
  usable: boolean
  blocked: string
  gif_default?: { provider: string; model: string } | null
  effective: { provider: string; model: string; source: 'saved' | 'default'; fallback: boolean; backup: EndPoint | null }
}
export interface LlmModel {
  id: string
  label: LangText
  adapter: string
  passthrough: boolean
  request_model: string
  quote: string
  note: LangText
  differences: LangText[]
}
export interface LlmProviderInfo {
  id: string
  label: LangText
  mode: string
  base_url: string
  configured: boolean
  secret_env: string
  docs: string
  models: LlmModel[]
}
export interface ProviderAdminState {
  admin: boolean
  tools: ToolRow[]
  llm: {
    saved: boolean
    revision: number
    active: { provider: string; model: string } | null
    effective?: { provider: string; model: string; base_url?: string } | null
    can_restore: boolean
    providers: LlmProviderInfo[]
    probe: string
  }
  policy: { fallback_default: boolean; max_attempts: string; eligible: string[]; human: string[] }
  saved_tool?: string
  activated?: boolean
  usable?: boolean
  blocked?: string
  applied?: string[]
  skipped?: string[]
  restored_tool?: string
}

export class ProviderAdminError extends Error {
  status: number
  code: string
  issues: string[]
  constructor(status: number, message: string, code = '', issues: string[] = []) {
    super(message)
    this.status = status
    this.code = code
    this.issues = issues
  }
}

async function send(path: string, method: string, body?: object): Promise<ProviderAdminState> {
  const res = await fetch(path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new ProviderAdminError(res.status, String(data.error || data.message || res.statusText), String(data.error || ''), Array.isArray(data.issues) ? data.issues.map(String) : [])
  }
  return data as ProviderAdminState
}

export const loadProviderAdmin = () => send('/comfyart/provider-admin', 'GET')
export const saveTool = (id: string, body: object) => (
  providerSaveFailFixture() ? rejectSaveFixture() : send(`/comfyart/provider-admin/tool/${id}`, 'PUT', body)
)
export const restoreTool = (id: string) => send(`/comfyart/provider-admin/tool/${id}/restore`, 'POST')
export const saveToolBatch = (body: object) => (
  providerSaveFailFixture() ? rejectSaveFixture() : send('/comfyart/provider-admin/tools/batch', 'PUT', body)
)
export const saveLlmProvider = (body: object) => send('/comfyart/provider-admin/llm', 'PUT', body)
export const restoreLlmProvider = () => send('/comfyart/provider-admin/llm/restore', 'POST')

export async function checkLlm(body: object): Promise<{ message: string; calls: number; quote: string; key_ok?: boolean; base_url?: string; model?: string }> {
  const res = await fetch('/comfyart/provider-admin/llm/check', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ProviderAdminError(res.status, String(data.error || res.statusText))
  return data
}

export async function rehearseLlm(body: object): Promise<{ message: string; calls: number; network: boolean; connected: boolean; kind: string }> {
  const res = await fetch('/comfyart/provider-admin/llm/rehearse', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ProviderAdminError(res.status, String(data.error || res.statusText))
  return data
}

let open = false
const listeners = new Set<() => void>()
export function providerAdminOpen() { return open }
export function setProviderAdminOpen(next: boolean) { open = next; listeners.forEach((fn) => fn()) }
export function subscribeProviderAdmin(fn: () => void) {
  listeners.add(fn)
  return () => { listeners.delete(fn) }
}
