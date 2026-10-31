// #481: behavioral harness for memory-dialog ago() — zh/en boundaries, locks en copy.
import { setLang, t, lang } from './i18n_stub'
import { ago } from '../../src/memoryRelativeTime'

const NOW = 1_700_000_000_000 // fixed epoch for deterministic buckets
const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

const out: Record<string, unknown> = {
  enKeys: {
    updatedAt: null as string | null,
    justNow: null as string | null,
    minutesAgo: null as string | null,
    hoursAgo: null as string | null,
    daysAgo: null as string | null,
  },
  zh: {} as Record<string, string>,
  en: {} as Record<string, string>,
  composed: {} as Record<string, string>,
}

function bucket(label: string, deltaMs: number) {
  return ago(NOW - deltaMs, NOW)
}

setLang('zh')
out.zh = {
  justNow0: bucket('0s', 0),
  justNow30s: bucket('30s', 30_000),
  justNowFuture: ago(NOW + 5 * MIN, NOW), // future → just now
  m59: bucket('59m', 59 * MIN),
  h1: bucket('60m', 60 * MIN),
  h23_59: bucket('23h59', 23 * HOUR + 59 * MIN),
  d1: bucket('24h', 24 * HOUR),
  d2: bucket('48h', 48 * HOUR),
  m5: bucket('5m', 5 * MIN),
  h14: bucket('14h', 14 * HOUR),
}
out.composed = {
  zhJust: `${t('memoryDialog.updatedAt', out.zh.justNow0 as string)}`,
  zh14h: `${t('memoryDialog.updatedAt', out.zh.h14 as string)}`,
  zh5m: `${t('memoryDialog.updatedAt', out.zh.m5 as string)}`,
}

setLang('en')
out.enKeys = {
  updatedAt: t('memoryDialog.updatedAt'),
  justNow: t('memoryDialog.justNow'),
  minutesAgo: t('memoryDialog.minutesAgo'),
  hoursAgo: t('memoryDialog.hoursAgo'),
  daysAgo: t('memoryDialog.daysAgo'),
}
out.en = {
  justNow0: bucket('0s', 0),
  justNow30s: bucket('30s', 30_000),
  justNowFuture: ago(NOW + 5 * MIN, NOW),
  m59: bucket('59m', 59 * MIN),
  h1: bucket('60m', 60 * MIN),
  h23_59: bucket('23h59', 23 * HOUR + 59 * MIN),
  d1: bucket('24h', 24 * HOUR),
  d2: bucket('48h', 48 * HOUR),
  m5: bucket('5m', 5 * MIN),
  h14: bucket('14h', 14 * HOUR),
}
out.composed = {
  ...(out.composed as object),
  enJust: `${t('memoryDialog.updatedAt', out.en.justNow0 as string)}`,
  en14h: `${t('memoryDialog.updatedAt', out.en.h14 as string)}`,
  en5m: `${t('memoryDialog.updatedAt', out.en.m5 as string)}`,
}

// Prove hardcoding justNow for every bucket would differ from real buckets
out.mutationWouldCatch = {
  zhAllJustNow: (['m59', 'h1', 'h23_59', 'd1'] as const).every((k) => (out.zh as any)[k] === (out.zh as any).justNow0) === false,
  enAllJustNow: (['m59', 'h1', 'h23_59', 'd1'] as const).every((k) => (out.en as any)[k] === (out.en as any).justNow0) === false,
  zhHourBoundaryDistinct: (out.zh as any).m59 !== (out.zh as any).h1 && (out.zh as any).h23_59 !== (out.zh as any).d1,
  enHourBoundaryDistinct: (out.en as any).m59 !== (out.en as any).h1 && (out.en as any).h23_59 !== (out.en as any).d1,
}

out.langAfter = lang
console.log(JSON.stringify(out))
