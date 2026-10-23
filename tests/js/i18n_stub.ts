import en from '../../src/locales/en.json'
import zh from '../../src/locales/zh.json'
const MESSAGES: Record<string, Record<string, string>> = { zh, en }
export let lang: 'zh' | 'en' = 'en'
export function setLang(next: 'zh' | 'en') { lang = next }
export function t(key: string, ...args: (string | number)[]): string {
  const text = MESSAGES[lang][key] ?? MESSAGES.en[key] ?? key
  return args.length ? text.replace(/\{(\d+)\}/g, (m, i) => (i < args.length ? String(args[i]) : m)) : text
}
export function tl(to: 'zh' | 'en', key: string, ...args: (string | number)[]): string {
  const text = MESSAGES[to][key] ?? MESSAGES.en[key] ?? key
  return args.length ? text.replace(/\{(\d+)\}/g, (m, i) => (i < args.length ? String(args[i]) : m)) : text
}
