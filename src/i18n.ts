import en from './locales/en.json'
import zh from './locales/zh.json'
import { BRAND } from './brand'
import { readLocal, writeLocal } from './localPrefs'

export type Lang = 'zh' | 'en'

const MESSAGES: Record<Lang, Record<string, string>> = { zh, en }

const KEY = 'comfyart.lang'

export let lang: Lang = 'en'

function storedLang(): Lang | null {
  const v = readLocal(KEY)
  return v === 'zh' || v === 'en' ? v : null
}

export async function initLocale() {
  const stored = storedLang()
  if (stored) lang = stored
  else {
    const res = await fetch('/api/settings/Comfy.Locale').catch(() => null)
    const value = res?.ok ? await res.json().catch(() => null) : null
    lang = String(value || navigator.language).toLowerCase().startsWith('zh') ? 'zh' : 'en'
  }
  document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'
  document.title = BRAND.pageTitle
}

export function setLang(next: Lang) {
  writeLocal(KEY, next)
  location.reload()
}

function fill(text: string, args: (string | number)[]): string {
  return text
    .replace(/\{brand\}/g, BRAND.name)
    .replace(/\{(\d+)\}/g, (m, i) => (Number(i) < args.length ? String(args[Number(i)]) : m))
}

export function t(key: string, ...args: (string | number)[]): string {
  const text = MESSAGES[lang][key] ?? MESSAGES.en[key] ?? key
  return fill(text, args)
}

/** t() in a fixed language (#128: tool results carry both zh and en for the agent's reply). */
export function tl(to: Lang, key: string, ...args: (string | number)[]): string {
  const text = MESSAGES[to][key] ?? MESSAGES.en[key] ?? key
  return fill(text, args)
}

export function timeAgo(time: number): string {
  const m = Math.floor((Date.now() - time) / 60000)
  if (m < 1) return t('common.justNow')
  if (m < 60) return t('common.minAgo', m)
  if (m < 1440) return t('common.hAgo', Math.floor(m / 60))
  return new Date(time).toLocaleString()
}
