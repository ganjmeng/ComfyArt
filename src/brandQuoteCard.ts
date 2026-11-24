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

/** Both the estimate card and the expired card post this. The server re-quotes. */
export function brandRequoteRequest(chatId: string, askId: string): { path: string; body: { ask_id: string } } {
  return {
    path: `/comfyart/bot/chats/${encodeURIComponent(chatId)}/brand-requote`,
    body: { ask_id: askId },
  }
}

export type BrandCardFace = 'superseded' | 'expired' | 'pending' | 'other'

export type BrandCardView = {
  face: BrandCardFace
  /** Empty when the card is the one-line replaced notice. */
  buttons: Array<'start' | 'requote' | 'cancel'>
  /** HH:MM from this card's own expires_at. Empty when the card has no deadline line. */
  deadline: string
  /** The card sentence. An estimate keeps the server prompt, including 「约」. */
  sentence: string
}

type BrandCardBlock = BrandQuoteFace & {
  replaced_by?: string
  price_state?: string
  prompt?: string
  selected?: string[]
  ask_id?: string
}

/** The server records replaced_by only after the new card is stored. Refresh reads that field. */
export function brandQuoteSuperseded(block: { brand_confirm?: boolean; replaced_by?: string }): boolean {
  return block.brand_confirm === true && typeof block.replaced_by === 'string' && block.replaced_by.length > 0
}

export function brandCardPresentation(block: BrandCardBlock, nowMs: number): BrandCardView {
  const sentence = block.prompt ?? ''
  if (brandQuoteSuperseded(block)) {
    return { face: 'superseded', buttons: [], deadline: '', sentence }
  }
  const requoteChosen = (block.selected ?? []).includes('requote')
  if (brandConfirmClosed(block, nowMs) && !requoteChosen) {
    return { face: 'expired', buttons: ['requote'], deadline: '', sentence }
  }
  const open = block.status === 'pending' || (block.brand_confirm === true && requoteChosen)
  if (!open) return { face: 'other', buttons: [], deadline: '', sentence }
  const action = block.brand_confirm ? brandQuoteAction(block.price_state) : 'start'
  const deadline = block.brand_confirm === true && typeof block.expires_at === 'number' && Number.isFinite(block.expires_at)
    ? brandDeadlineClock(block.expires_at)
    : ''
  return {
    face: 'pending',
    buttons: action === 'requote' ? ['requote', 'cancel'] : ['start', 'cancel'],
    deadline,
    sentence,
  }
}

export type PlacedBrandCard = BrandCardView & {
  askId: string
  messageIndex: number
  blockIndex: number
}

/** Cards in conversation order. A re-quote appends; it does not reuse the old card's index. */
export function brandQuotePositions(
  messages: { blocks: BrandCardBlock[] }[],
  nowMs: number,
): PlacedBrandCard[] {
  const placed: PlacedBrandCard[] = []
  messages.forEach((message, messageIndex) => {
    message.blocks.forEach((block, blockIndex) => {
      if (block.brand_confirm !== true) return
      placed.push({
        askId: block.ask_id ?? '',
        messageIndex,
        blockIndex,
        ...brandCardPresentation(block, nowMs),
      })
    })
  })
  return placed
}
