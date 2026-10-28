/** #192: one money format for every quote (the estimate next to Send): the quoted amount
 * to at most 4 decimals with trailing zeros trimmed but at least 2 kept, e.g. 0.039, 0.0893, 0.04, 0.10, 0.0035. */
export function usd(n: number): string {
  const s = (Number.isFinite(n) ? n : 0).toFixed(4).replace(/0+$/, '')
  const [i, d = ''] = s.split('.')
  return `${i}.${d.padEnd(2, '0')}`
}

/** #229: two-decimal USD (0.5 -> "0.50"). Kept for any remaining USD display (e.g. balance). */
export const thresholdUsd = (n: number) => (Number.isFinite(n) ? n : 0).toFixed(2)

/** #397 / #393: UI credits only. 1 credit = $0.01; round USD to nearest micro-dollar, then integer ceil to credits.
 * Under 1 credit of nonzero spend → 1; spend 0 → 0. Matches bot/run_budget.ui_credits. */
export function uiCredits(usdAmount: number): number {
  const v = Number.isFinite(usdAmount) ? Math.max(0, usdAmount) : 0
  const micro = Math.round(v * 1_000_000)
  // integer ceil: -(-micro // 10_000) in Python
  return micro === 0 ? 0 : Math.floor((micro + 9999) / 10_000)
}

/** #397: confirm-line in settings is an integer credit count. */
export const thresholdCredits = (n: number) => String(Number.isFinite(n) ? Math.trunc(n) : 0)
