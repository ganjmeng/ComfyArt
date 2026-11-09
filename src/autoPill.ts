/** #825: generation-card / process-rail Auto · model label (mirrors api/auto_models.pill_*). */
import { tl, type Lang } from './i18n'

export type ModelChoice = {
  model?: string
  auto?: boolean
  category?: string
  skill?: string
  reason?: { zh?: string; en?: string } | string
  fallback?: string
  note?: string
}

const SHORT: Record<string, string> = {
  'openai/gpt-image-2.6-sunburst/text-to-image': 'GPT Image 2.6 Sunburst',
  'openai/gpt-image-2.6-sunburst/edit': 'GPT Image 2.6 Sunburst',
  'openai/gpt-image-2.6-flare/text-to-image': 'GPT Image 2.6 Flare',
  'openai/gpt-image-2.6-flare/edit': 'GPT Image 2.6 Flare',
  'openai/gpt-image-2.5-sunburst/edit': 'GPT Image 2.5 Sunburst',
  'openai/gpt-image-2.5-flare/text-to-image': 'GPT Image 2.5 Flare',
  'openai/gpt-image-2.5-flare/edit': 'GPT Image 2.5 Flare',
  'google/nano-banana-2.1/text-to-image': 'Nano Banana 2.1',
  'google/nano-banana-2.1/edit': 'Nano Banana 2.1',
  'google/nano-banana-pro/edit': 'Nano Banana Pro',
  'bytedance/seedream-v5.0-pro': 'Seedream 5.0 Pro',
  'bytedance/seedream-v5.0-pro/edit': 'Seedream 5.0 Pro',
  'recraft-ai/recraft-v3': 'Recraft V3',
}

const ACRONYMS = new Set(['gpt', 'ai', 'ui', 'io', 'api', 'cpu', 'gpu', 'vae'])

/** Hyphen/underscore → spaces; capitalize words but keep GPT (not Gpt). */
function humanizeIdSegment(seg: string): string {
  return seg
    .replace(/[-_]/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => {
      const low = w.toLowerCase()
      if (ACRONYMS.has(low)) return low.toUpperCase()
      return w.charAt(0).toUpperCase() + w.slice(1)
    })
    .join(' ')
}

export function shortModelName(model?: string | null, catalogLabel?: string | null): string {
  if (catalogLabel?.trim()) return catalogLabel.trim()
  if (!model) return ''
  if (SHORT[model]) return SHORT[model]
  const parts = String(model).split('/').filter(Boolean)
  if (parts.length >= 2) return humanizeIdSegment(parts[parts.length - 2]!)
  return String(model)
}

function reasonText(choice: ModelChoice, lang: string): string {
  const r = choice.reason
  if (!r) return ''
  if (typeof r === 'string') return r
  const key = lang.toLowerCase().startsWith('en') ? 'en' : 'zh'
  return String(r[key as 'zh' | 'en'] || r.zh || r.en || '')
}

function tipLang(lang: string): Lang {
  return lang.toLowerCase().startsWith('en') ? 'en' : 'zh'
}

function isSkillChoice(choice: ModelChoice): boolean {
  return !!choice.skill || choice.category === 'skill' || choice.category === 'skill_fallback'
}

/** Mirrors api/auto_models.skill_pin_reason / chatMessage.skillPinnedModel. */
export function skillPinReason(skill: string): { zh: string; en: string } {
  return {
    zh: tl('zh', 'chatMessage.skillPinnedModel', skill),
    en: tl('en', 'chatMessage.skillPinnedModel', skill),
  }
}

/** Visible label. Auto → 'Auto · <name>'; manual → name only; Auto with no model yet → 'Auto'; legacy empty → null. */
export function autoPillLabel(choice: ModelChoice | null | undefined, catalogLabel?: string | null): string | null {
  if (!choice || typeof choice !== 'object') return null
  const model = choice.model
  const auto = !!choice.auto
  const name = shortModelName(model, catalogLabel)
  if (auto && !model) return 'Auto'
  if (!model && !auto) return null
  if (auto) return name ? `Auto · ${name}` : 'Auto'
  return name || null
}

/** Hover/tap reason. Manual: null. Table Auto: i18n prefix + category. Skill pin: no prefix. */
export function autoPillTooltip(choice: ModelChoice | null | undefined, lang: string): string | null {
  if (!choice || !choice.auto) return null
  const L = tipLang(lang)
  const prefix = isSkillChoice(choice) ? '' : tl(L, 'chatMessage.autoPickedPrefix')
  const category = reasonText(choice, L)
  const failed = choice.fallback
  const model = choice.model
  if (failed && model) {
    const body = L === 'en'
      ? `${category} · Preferred ${shortModelName(failed)} failed, used ${shortModelName(model)}`
      : `${category} · 首选 ${shortModelName(failed)} 失败，改用 ${shortModelName(model)}`
    return `${prefix}${body}`.trim()
  }
  if (!category) return null
  return `${prefix}${category}`
}

/** Parse model_choice from a tool_result JSON text (MCP payload). */
export function modelChoiceOfResult(text?: string | null): ModelChoice | null {
  if (!text) return null
  try {
    const data = JSON.parse(text) as { model_choice?: ModelChoice }
    return data?.model_choice && typeof data.model_choice === 'object' ? data.model_choice : null
  } catch {
    return null
  }
}

/** True when the tool input is Auto (omitted / auto token / auto_model). */
export function inputIsAuto(input?: Record<string, unknown> | null): boolean {
  if (!input) return true
  if (input.auto_model === true) return true
  const m = input.model ?? input.edit_model
  if (m == null || m === '') return true
  if (typeof m === 'string' && ['auto', 'auto:video'].includes(m.trim().toLowerCase())) return true
  return false
}
