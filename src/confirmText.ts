import { lang, t, tl, type Lang } from './i18n'
import { uiCredits } from './usd'

export interface ConfirmGif {
  frame_count: number
  frame_duration_ms: number
  asked_frame_count?: number
  asked_frame_duration_ms?: number
}
export interface ConfirmDetail { tier?: string; unpriced?: boolean; estimate?: boolean; live?: boolean; gif?: ConfirmGif }

function gifClause(gif: ConfirmGif, to?: Lang): string {
  const tr = (key: string, ...args: (string | number)[]) => (to ? tl(to, key, ...args) : t(key, ...args))
  const frames = typeof gif.asked_frame_count === 'number' ? tr('jobs.gifFramesAdjusted', gif.frame_count, gif.asked_frame_count) : tr('jobs.gifFrames', gif.frame_count)
  const ms = typeof gif.asked_frame_duration_ms === 'number' ? tr('jobs.gifMsAdjusted', gif.frame_duration_ms, gif.asked_frame_duration_ms) : tr('jobs.gifMs', gif.frame_duration_ms)
  return to === 'zh' || (!to && lang === 'zh') ? `${frames}，${ms}` : `${frames}, ${ms}`
}

/** Visible confirm sentence. GIF numbers are the request's effective values; credits come from the quote field. */
export function confirmDesc(price: number | null, segSplits?: number, segCapped?: boolean, detail?: ConfirmDetail, to?: Lang): string {
  const tr = (key: string, ...args: (string | number)[]) => (to ? tl(to, key, ...args) : t(key, ...args))
  const p = String(uiCredits(price ?? 0))  // #397: credits only in the confirm dialog (never dollars)
  const clause = detail?.gif && typeof detail.gif.frame_count === 'number' && typeof detail.gif.frame_duration_ms === 'number' ? gifClause(detail.gif, to) : ''
  if (detail?.unpriced || price == null) return clause ? tr('jobs.confirmUnpricedGif', clause) : tr('jobs.confirmUnpriced', detail?.tier || tr('jobs.thisTier'))
  if (detail?.estimate && typeof segSplits !== 'number') return clause ? tr('jobs.confirmEstimateGif', p, clause) : (detail.tier ? tr('jobs.confirmEstimateTier', p, detail.tier) : tr('jobs.confirmEstimate', p))
  if (typeof segSplits !== 'number') return clause ? tr('jobs.confirmCostGif', p, clause) : tr('jobs.confirmCost', p)
  return segCapped ? tr('jobs.confirmSegMax', p, segSplits!) : tr('jobs.confirmSegLeft', p, segSplits!)
}
