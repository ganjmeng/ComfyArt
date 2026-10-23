// #155: WaveSpeed error kinds -> readable zh/en messages (never the raw WaveSpeed text).
import { setLang } from './i18n_stub'
import { wsBodyError, wsErrorText } from '../../src/wsErrors'

const kinds = ['insufficientCredit', 'moderation', 'rateLimit', 'invalidKey', 'network', 'failed']
const raw = { error: { message: 'WaveSpeed request failed (500) Internal Error xyz', kind: 'failed' } }
const out: Record<string, unknown> = {}
for (const lang of ['zh', 'en'] as const) {
  setLang(lang)
  out[lang] = {
    kinds: Object.fromEntries(kinds.map((k) => [k, wsErrorText(k)])),
    raw: wsBodyError(raw, 'x'),
    untagged: wsBodyError({ error: { message: 'mask file not found' } }, 'x'),
    plain: wsBodyError({ error: 'src must be a /api/view URL' }, 'x'),
    unknown: wsErrorText('nope'),
  }
}
console.log(JSON.stringify(out))
