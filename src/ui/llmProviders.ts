import { t } from '../i18n'
import type { BotSettings, LlmStatus } from '../bot'

export type LlmProviderId = 'wavespeed' | 'deepseek' | 'siliconflow' | 'openrouter' | 'openai' | 'ollama' | 'custom'

export interface LlmProviderOption {
  id: LlmProviderId
  url: string
  mark: string
  letter?: boolean
  recommended: string[]
}

export const LLM_PROVIDERS: LlmProviderOption[] = [
  { id: 'wavespeed', url: 'https://llm.wavespeed.ai/v1', mark: 'WS', letter: true, recommended: ['deepseek/deepseek-v4.1-flash-1017'] },
  { id: 'deepseek', url: 'https://api.deepseek.com/v1', mark: 'deepseek', recommended: ['deepseek-flash', 'deepseek-chat'] },
  { id: 'siliconflow', url: 'https://api.siliconflow.com/v1', mark: '硅', letter: true, recommended: [] },
  { id: 'openrouter', url: 'https://openrouter.ai/api/v1', mark: 'OR', letter: true, recommended: [] },
  { id: 'openai', url: 'https://api.openai.com/v1', mark: 'OA', letter: true, recommended: [] },
  { id: 'ollama', url: 'http://localhost:11434/v1', mark: 'OL', letter: true, recommended: [] },
  { id: 'custom', url: '', mark: 'API', letter: true, recommended: [] },
]

export const LLM_PROVIDER_IDS = LLM_PROVIDERS.map((p) => p.id)

export const normLlmUrl = (v: unknown) => String(v ?? '').trim().replace(/\/+$/, '')

const hostOf = (url: unknown): { host: string; port: number | null } => {
  try {
    const u = new URL(String(url ?? '').trim())
    const port = u.port ? Number(u.port) : (u.protocol === 'https:' ? 443 : u.protocol === 'http:' ? 80 : null)
    return { host: u.hostname.toLowerCase(), port: Number.isFinite(port as number) ? port : null }
  } catch {
    return { host: '', port: null }
  }
}

const HOSTS: Record<string, LlmProviderId> = {
  'llm.wavespeed.ai': 'wavespeed',
  'api.deepseek.com': 'deepseek',
  'api.siliconflow.com': 'siliconflow',
  'api.siliconflow.cn': 'siliconflow',
  'openrouter.ai': 'openrouter',
  'api.openai.com': 'openai',
}

export function inferLlmProvider(url: string, stored?: string): LlmProviderId {
  const s = String(stored ?? '').trim()
  if ((LLM_PROVIDER_IDS as string[]).includes(s)) return s as LlmProviderId
  const { host, port } = hostOf(url)
  if ((host === 'localhost' || host === '127.0.0.1') && port === 11434) return 'ollama'
  if (host && HOSTS[host]) return HOSTS[host]
  return normLlmUrl(url) ? 'custom' : 'wavespeed'
}

export function providerById(id: string): LlmProviderOption {
  return LLM_PROVIDERS.find((p) => p.id === id) ?? LLM_PROVIDERS[LLM_PROVIDERS.length - 1]!
}

export function providerLabel(id: string): string {
  return t(`botSettings.provider.${id}`)
}

export function pickDefaultModel(opts: { saved: string; ids: string[]; provider: string }): string {
  const saved = opts.saved.trim()
  if (saved) return saved // keep a saved id even when it is not in this list (AC7)
  const recs = providerById(opts.provider).recommended
  for (const id of recs) {
    if (opts.ids.includes(id)) return id
  }
  return ''
}

export function llmSourceLabel(status: LlmStatus, settings?: BotSettings): string {
  if (status.source === 'admin') return t('botSettings.llmSourceAdmin')
  if (status.source === 'settings') {
    const url = String(settings?.['bot-local-llm-url'] ?? status.url ?? '')
    const provider = inferLlmProvider(url, String(settings?.llm_provider ?? status.provider ?? ''))
    const name = provider !== 'custom' ? providerLabel(provider) : (status.host || hostOf(url).host || providerLabel('custom'))
    return t('botSettings.llmSourceCustom', name)
  }
  const display = status.officialDisplayName || status.official_display_name || String(settings?.official_llm_display_name ?? '')
  return t('botSettings.llmSourceOfficial', display)
}
