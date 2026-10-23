// Object-shaped `{ error: {...} }` bodies must surface as readable zh/en text, never "[object Object]".
import { setLang } from './i18n_stub'
import { g } from './objerr_comfy_stub'
import { readLines } from '../../src/elements'
import { call } from '../../src/projects'
import { loadSettings } from '../../src/bot'
import { ask } from '../../src/llm'

const bodies: Record<string, unknown> = {
  tagged: { error: { message: 'WaveSpeed request failed (500) Internal Error xyz', kind: 'failed' } },
  untagged: { error: { code: 500, detail: { reason: 'boom' } } },
  nested: { error: { message: { text: 'boom' } } },
  plain: { error: 'project not found' },
}
const sites: Record<string, () => Promise<unknown>> = {
  elements: () => readLines('/api/view?filename=a.png'),
  projects: () => call('/comfyart/projects/x'),
  bot: () => loadSettings(),
  llm: () => ask('hi', 'sys', []),
}
const out: Record<string, any> = {}
for (const lang of ['zh', 'en'] as const) {
  setLang(lang)
  out[lang] = {}
  for (const [site, run] of Object.entries(sites)) {
    out[lang][site] = {}
    for (const [name, body] of Object.entries(bodies)) {
      g.__body = body
      try { await run(); out[lang][site][name] = 'NO THROW' } catch (e) { out[lang][site][name] = (e as Error).message }
    }
  }
}
console.log(JSON.stringify(out))
