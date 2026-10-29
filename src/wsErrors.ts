// #155: WaveSpeed failures are shown as readable zh/en messages, never the raw WaveSpeed error text.
import { t } from './i18n'
import { uiCredits } from './usd'

export const TOP_UP_URL = 'https://wavespeed.ai/top-up'
/** #408: upstream's 「Back to ComfyUI」 now opens the WaveSpeed console task history (we have no ComfyUI host). */
export const WS_HISTORY_URL = 'https://wavespeed.ai/predictions'
export const openWsHistory = () => void window.open(WS_HISTORY_URL, '_blank', 'noopener,noreferrer')
const KINDS = ['insufficientCredit', 'moderation', 'rateLimit', 'invalidKey', 'network', 'failed', 'timeout', 'loraUrl', 'loraUnsupported', 'loraTooMany', 'stopped'] as const
export type WsErrorKind = typeof KINDS[number]

/** The readable message for a backend error kind, or null when the error is not a tagged WaveSpeed failure. */
export function wsErrorText(kind: unknown, charged?: unknown): string | null {
  if (typeof kind !== 'string' || !(KINDS as readonly string[]).includes(kind)) return null
  // #174: a timed-out task may still be billed; show the quoted amount when known, never auto-retry
  if (kind === 'timeout') return typeof charged === 'number' && Number.isFinite(charged) ? t('wsErr.timeout', fmtUsd(charged)) : t('wsErr.timeoutNoAmount')
  // #408: a stopped task was already submitted, so WaveSpeed may have billed it; say the quoted amount (credits), never 0
  if (kind === 'stopped') return typeof charged === 'number' && Number.isFinite(charged) ? t('wsErr.stopped', uiCredits(charged)) : t('wsErr.stoppedNoAmount')
  return kind === 'insufficientCredit' ? t('wsErr.insufficientCredit', TOP_UP_URL) : t(`wsErr.${kind}`)
}

/** `{ error: { message, kind } }` bodies from /comfyart/wavespeed/* and /comfyart/ocr. */
const fmtUsd = (n: number) => String(Math.round(n * 1e4) / 1e4)

export function wsBodyError(body: any, fallback: string): string {
  const err = body?.error
  // never stringify an object into "[object Object]": only string text passes through, otherwise the localized fallback
  return wsErrorText(err?.kind, err?.charged_usd) ?? (typeof err === 'string' && err.trim() ? err : typeof err?.message === 'string' && err.message.trim() ? err.message : fallback)
}

export const RELAY_NOTE = 'user_message is already in the user\'s language; reply with it word for word (keep any link), do not paraphrase or quote a raw error'

/** Agent tool result for a failed generation: the agent must relay our zh/en copy verbatim (#155 follow-up). */
export function agentError(message: string) {
  return { error: message, user_message: message, note: RELAY_NOTE }
}

/** Thrown tool errors carry the same relay instruction. */
export function agentErrorText(message: string): string {
  return `${message}\n[${RELAY_NOTE.replace('user_message', 'this message')}]`
}
