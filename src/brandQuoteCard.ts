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
