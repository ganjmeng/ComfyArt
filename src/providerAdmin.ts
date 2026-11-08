/** Admin provider settings. Drafts stay in the page until Save. Secrets are never sent. */

export interface LangText { zh?: string; en?: string }

export interface ImageModel {
  id: string
  label: string
  adapter: string
  capabilities: string[]
  quote: string
  docs: string
  differences: LangText
}

export interface ImageProviderInfo {
  id: string
  label: LangText
  mode: string
  configured: boolean
  secret_env: string
  note: LangText
  models: ImageModel[]
  capabilities: Record<string, { supported: boolean; enabled: boolean; formats: string[]; reason: LangText }>
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

export interface AuditCapability {
  capability: string
  provider: string
  implemented: boolean
  quote: string
  detail: LangText
}

export interface ProviderAdminState {
  admin: boolean
  image: {
    saved: boolean
    revision: number
    active: { provider: string; models?: Record<string, string> } | null
    ignored: boolean
    can_restore: boolean
    providers: ImageProviderInfo[]
  }
  llm: {
    saved: boolean
    revision: number
    active: { provider: string; model: string } | null
    ignored: boolean
    can_restore: boolean
    providers: LlmProviderInfo[]
    probe: string
  }
  audit: {
    summary: {
      checked_at: string
      model_counts: Record<string, number>
      models_listed: number
      capabilities: AuditCapability[]
    }
    note: LangText
  }
}

export class ProviderAdminError extends Error {
  status: number
  issues: string[]
  constructor(status: number, message: string, issues: string[] = []) {
    super(message)
    this.status = status
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
    const issues = Array.isArray(data.issues) ? data.issues.map(String) : []
    throw new ProviderAdminError(res.status, String(data.error || res.statusText), issues)
  }
  return data as ProviderAdminState
}

export const loadProviderAdmin = () => send('/comfyart/provider-admin', 'GET')

export const saveImageProvider = (body: object) => send('/comfyart/provider-admin/image', 'PUT', body)

export const restoreImageProvider = () => send('/comfyart/provider-admin/image/restore', 'POST')

export const saveLlmProvider = (body: object) => send('/comfyart/provider-admin/llm', 'PUT', body)

export const restoreLlmProvider = () => send('/comfyart/provider-admin/llm/restore', 'POST')

let open = false
const listeners = new Set<() => void>()

export function providerAdminOpen() {
  return open
}

export function setProviderAdminOpen(next: boolean) {
  open = next
  listeners.forEach((fn) => fn())
}

export function subscribeProviderAdmin(fn: () => void) {
  listeners.add(fn)
  return () => { listeners.delete(fn) }
}
