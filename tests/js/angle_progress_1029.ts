import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { setLang } from '../../src/i18n'
import { AngleProgress, type AngleProgressBlock, type AngleSlot } from '../../src/ui/AngleProgress'

function card(partial: Partial<AngleProgressBlock>, slots: AngleSlot[]): string {
  const block: AngleProgressBlock = {
    type: 'multi_angle_progress',
    preview: 1,
    final_total: 9,
    final_done: 0,
    phase: 'confirmed',
    batch_retry: false,
    slots,
    ...partial,
  }
  return renderToStaticMarkup(createElement(AngleProgress, { block }))
}

const finals = (states: Record<string, string>): AngleSlot[] => [
  { id: 'preview', kind: 'preview', state: 'delivered' },
  ...Array.from({ length: 9 }, (_, i) => {
    const panel = String(i + 1)
    return { id: `final:${panel}`, kind: 'final', panel, state: states[panel] || 'waiting', retry: states[panel] === 'failed' }
  }),
]

function check(lang: 'zh' | 'en', html: string, parts: string[], absent: string[]) {
  const missing = parts.filter((part) => !html.includes(part))
  const present = absent.filter((part) => html.includes(part))
  return { lang, missing, present, html }
}

const copy = {
  zh: {
    confirmed: '预览 1 + 成品 0/9',
    generating: '生成中 · 预览 1 + 成品 3/9',
    done: '预览 1 + 成品 9/9',
    interrupted: '已中断 · 预览 1 + 成品 1/9',
    delivered: '已交付',
    generatingSlot: '生成中',
    pending: '待查询',
    failed: '生成失败',
    retry: '重试',
  },
  en: {
    confirmed: 'Preview 1 + Finals 0/9',
    generating: 'Generating · Preview 1 + Finals 3/9',
    done: 'Preview 1 + Finals 9/9',
    interrupted: 'Interrupted · Preview 1 + Finals 1/9',
    delivered: 'Delivered',
    generatingSlot: 'Generating',
    pending: 'Awaiting results',
    failed: 'Failed',
    retry: 'Retry',
  },
}

const reports = []
for (const lang of ['zh', 'en'] as const) {
  setLang(lang)
  const c = copy[lang]
  const confirmed = card({ phase: 'confirmed', final_done: 0 }, finals({}))
  const generating = card({ phase: 'generating', final_done: 3 }, finals({ '1': 'delivered', '2': 'delivered', '3': 'delivered', '4': 'generating' }))
  const done = card({ phase: 'done', final_done: 9 }, finals(Object.fromEntries(Array.from({ length: 9 }, (_, i) => [String(i + 1), 'delivered']))))
  const resume = card({ phase: 'partial', final_done: 1 }, finals({ '1': 'delivered', '2': 'pending_query', '6': 'failed' }))
  const states = [confirmed, generating, done, resume]
  reports.push(check(lang, confirmed, [c.confirmed, 'data-phase="confirmed"'], ['0/0', '<progress', '0/6', '>6<']))
  reports.push(check(lang, generating, [c.generating, 'data-state="generating"', c.delivered], ['0/0', '<progress', 'angle-retry-all']))
  reports.push(check(lang, done, [c.done, c.delivered], ['0/0', '<progress', 'angle-retry-']))
  reports.push(check(lang, resume, [
    c.interrupted, c.delivered, c.pending, c.failed, `data-testid="angle-retry-final:6"`, c.retry,
    'data-state="pending_query"',
  ], ['0/0', '<progress', 'angle-retry-all', 'angle-retry-final:2', 'data-state="failed">待查询', 'data-state="failed">Awaiting']))
  if (states.length !== 4) reports.push({ lang, missing: ['four states'], present: [], html: '' })
  const retryButtons = (resume.match(/angle-retry-/g) || []).length
  if (retryButtons !== 1) reports.push({ lang, missing: [`retry buttons ${retryButtons}`], present: [], html: resume })
}

const bad = reports.filter((row) => row.missing.length || row.present.length)
if (bad.length) {
  console.log(JSON.stringify(bad.map(({ lang, missing, present }) => ({ lang, missing, present })), null, 2))
  process.exit(1)
}
console.log(JSON.stringify({ ok: true, cards: reports.length }))
