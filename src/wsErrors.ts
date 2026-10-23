// #155: WaveSpeed failures are shown as readable zh/en messages, never the raw WaveSpeed error text.
import { t } from './i18n'

export const TOP_UP_URL = 'https://wavespeed.ai/top-up'
const KINDS = ['insufficientCredit', 'moderation', 'rateLimit', 'invalidKey', 'network', 'failed', 'timeout'] as const
export type WsErrorKind = typeof KINDS[number]

/** The readable message for a backend error kind, or null when the error is not a tagged WaveSpeed failure. */
export function wsErrorText(kind: unknown, charged?: unknown): string | null {
  if (typeof kind !== 'string' || !(KINDS as readonly string[]).includes(kind)) return null
  // #174: a timed-out task may still be billed; show the quoted amount when known, never auto-retry
  if (kind === 'timeout') return typeof charged === 'number' && Number.isFinite(charged) ? t('wsErr.timeout', fmtUsd(charged)) : t('wsErr.timeoutNoAmount')
  return kind === 'insufficientCredit' ? t('wsErr.insufficientCredit', TOP_UP_URL) : t(`wsErr.${kind}`)
}

/** `{ error: { message, kind } }` bodies from /comfyart/wavespeed/* and /comfyart/ocr. */
const fmtUsd = (n: number) => String(Math.round(n * 1e4) / 1e4)

export function wsBodyError(body: any, fallback: string): string {
  const err = body?.error
  return wsErrorText(err?.kind, err?.charged_usd) ?? (typeof err === 'string' ? err : err?.message ?? fallback)
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
