// #155: WaveSpeed failures are shown as readable zh/en messages, never the raw WaveSpeed error text.
import { t } from './i18n'

export const TOP_UP_URL = 'https://wavespeed.ai/top-up'
const KINDS = ['insufficientCredit', 'moderation', 'rateLimit', 'invalidKey', 'network', 'failed'] as const
export type WsErrorKind = typeof KINDS[number]

/** The readable message for a backend error kind, or null when the error is not a tagged WaveSpeed failure. */
export function wsErrorText(kind: unknown): string | null {
  if (typeof kind !== 'string' || !(KINDS as readonly string[]).includes(kind)) return null
  return kind === 'insufficientCredit' ? t('wsErr.insufficientCredit', TOP_UP_URL) : t(`wsErr.${kind}`)
}

/** `{ error: { message, kind } }` bodies from /comfyart/wavespeed/* and /comfyart/ocr. */
export function wsBodyError(body: any, fallback: string): string {
  const err = body?.error
  return wsErrorText(err?.kind) ?? (typeof err === 'string' ? err : err?.message ?? fallback)
}
