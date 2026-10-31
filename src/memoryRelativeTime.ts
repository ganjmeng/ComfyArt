import { t } from './i18n'

/** Relative label for the memory-dialog header (#481). `now` is injectable for tests. */
export function ago(time: number, now = Date.now()): string {
  const min = Math.floor((now - time) / 60000)
  if (min < 1) return t('memoryDialog.justNow')
  if (min < 60) return t('memoryDialog.minutesAgo', min)
  const h = Math.floor(min / 60)
  return h < 24 ? t('memoryDialog.hoursAgo', h) : t('memoryDialog.daysAgo', Math.floor(h / 24))
}
