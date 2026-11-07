// #721: pass-through sites map raw multi-line errors to friendly copy (zh/en).
// localizeError / promptError are exercised via the same helpers they call (mapUnknownError / wsErr.*),
// plus source-contract checks in the pytest file.
import { setLang, t } from './i18n_stub'
import { mapUnknownError, OWN_ERROR_ALLOWLIST, wsBodyError, wsErrorText } from '../../src/wsErrors'

const RAW = 'WaveSpeedAI KSampler #9: CUDA OOM — see console/dashboard\n  at Node.execute (engine.py:44)\nInternal Error xyz https://wavespeed.ai/console'
const BANNED = /wavespeedai|kie|\u63a7\u5236\u53f0|\u540e\u53f0|console|dashboard|\u751f\u6210\u8bb0\u5f55|\u5386\u53f2\u8bb0\u5f55|Internal Error xyz|engine\.py|CUDA OOM|\[object Object\]/i

/** Mirrors src/comfy.ts promptError after #721 (kept in sync by source-contract test). */
function promptErrorMirror(body: any, status: number): string {
  const lines = Object.entries<any>(body?.node_errors ?? {}).flatMap(([id, ne]) =>
    (ne?.errors ?? []).map((er: any) => `${ne.class_type ?? ''} #${id}: ${er.message}${er.details ? ` — ${er.details}` : ''}`))
  if (lines.length) return t('wsErr.generic')
  const top = body?.error
  const readable = wsErrorText(top?.kind, top?.charged_usd, top?.task_id)
  if (readable) return readable
  return t('wsErr.failed')
}

/** Mirrors localizeError unknown/failed branches after #721. */
function localizeMirror(msg: string): string {
  if (/^WaveSpeed task (?:failed: .*|finished without output)$/s.test(msg)) return t('wsErr.failed')
  if (OWN_ERROR_ALLOWLIST.has(msg)) return msg
  // already-friendly short copy (wsErr.failed etc.) — pass through exact locale values
  if (msg === t('wsErr.failed') || msg === t('wsErr.generic')) return msg
  return mapUnknownError(msg)
}

const out: Record<string, any> = { bannedCheck: true }
for (const lang of ['zh', 'en'] as const) {
  setLang(lang)
  const generic = t('wsErr.generic')
  const failed = t('wsErr.failed')
  const bodyStr = wsBodyError({ error: RAW }, 'fallback-should-not-win')
  const bodyMsg = wsBodyError({ error: { message: RAW } }, 'fallback-should-not-win')
  const bodyTagged = wsBodyError({ error: { kind: 'failed', message: RAW } }, 'x')
  const bodyTimeoutId = wsBodyError({ error: { kind: 'timeout', charged_usd: 0.32, task_id: 'tid-721', message: RAW } }, 'x')
  const locRaw = localizeMirror(RAW)
  const locFailed = localizeMirror(`WaveSpeed task failed: ${RAW}`)
  const locAllow = localizeMirror('mask file not found')
  const locFriendly = localizeMirror(failed)
  const errText = localizeMirror(RAW) // errorText → localizeError
  const mapped = mapUnknownError(RAW)
  const exec = wsErrorText(undefined) ?? mapUnknownError(RAW)
  const peNodes = promptErrorMirror({
    node_errors: { '9': { class_type: 'KSampler', errors: [{ message: 'CUDA OOM', details: 'see console/dashboard Internal Error xyz' }] } },
  }, 500)
  const peQueue = promptErrorMirror({ error: { message: 'invalid prompt', details: 'bad graph from console' } }, 400)
  const peStatus = promptErrorMirror({}, 502)
  const peTagged = promptErrorMirror({ error: { kind: 'rateLimit', message: RAW } }, 429)
  const site = {
    generic, failed, bodyStr, bodyMsg, bodyTagged, bodyTimeoutId,
    locRaw, locFailed, locAllow, locFriendly, errText, mapped, exec,
    peNodes, peQueue, peStatus, peTagged,
  }
  for (const [k, v] of Object.entries(site)) {
    if (typeof v === 'string' && BANNED.test(v) && k !== 'locAllow') {
      out.bannedCheck = false
      out.bannedHit = { lang, k, v }
    }
  }
  out[lang] = site
}
console.log(JSON.stringify(out))
