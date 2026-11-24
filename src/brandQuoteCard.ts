/** Brand quote cards close on their own deadline. The check is synchronous so a
 * restored session never paints a Start button for a card that is already due.
 */

export type BrandQuoteFace = {
  brand_confirm?: boolean
  status?: string
  expires_at?: number
}

export function brandConfirmClosed(block: BrandQuoteFace, nowMs: number): boolean {
  if (block.brand_confirm !== true) return false
  if (block.status === 'expired') return true
  const exp = block.expires_at
  if (typeof exp !== 'number' || !Number.isFinite(exp)) return true
  return nowMs >= exp * 1000
}

/** HH:MM in Asia/Shanghai from the stored expires_at. The clock is not recomputed from now. */
export function brandDeadlineClock(expiresAtSec: number): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(expiresAtSec * 1000))
}

export type BrandQuoteAction = 'start' | 'requote'

/** A real price starts. An estimate or an unpriced card asks for a new price and does not say Start. */
export function brandQuoteAction(priceState: string | undefined): BrandQuoteAction {
  return priceState === 'estimate' || priceState === 'unpriced' ? 'requote' : 'start'
}
