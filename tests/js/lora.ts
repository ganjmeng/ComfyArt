// #202: LoRA URL validation, schema gating, saved-list persistence and zh/en error copy.
import { setLang } from './i18n_stub'
import { files } from './comfy_stub'
import { forgetLora, loadSavedLoras, loraLabel, loraUrl, saveLora, savedLorasAtom, supportsLora } from '../../src/loras'
import { wsErrorText } from '../../src/wsErrors'

const HF = 'https://huggingface.co/acme/style-lora/resolve/main/ink_style.safetensors'
const inputs = [HF, HF.replace('/resolve/', '/blob/'), 'https://civitai.com/api/download/models/123456', 'https://civitai.com/models/9876/some-style?modelVersionId=123456',
  'https://evil.example/a.safetensors', 'https://civitai.com/models/9876', 'not a url']
const out: Record<string, unknown> = { inputs, urls: inputs.map(loraUrl) }
const m = (inputs?: string[], auto = false) => ({ id: 'x', label: 'x', desc: '', files: [], inputs, auto })
out.supports = { withLoras: supportsLora(m(['prompt', 'loras'])), without: supportsLora(m(['prompt'])), auto: supportsLora(m(undefined, true)), missing: supportsLora(undefined) }
await loadSavedLoras()
await saveLora({ name: HF, strength: 100 })
await saveLora({ name: 'https://civitai.com/api/download/models/123456', strength: 60 })
await saveLora({ name: HF, strength: 100 })
await saveLora({ name: 'https://civitai.com/api/download/models/123456', strength: 60 })
out.saved = savedLorasAtom.get()
savedLorasAtom.set(null)
await loadSavedLoras()
out.reloaded = savedLorasAtom.get()
await forgetLora('https://civitai.com/api/download/models/123456')
out.afterForget = JSON.parse(files['comfyart/lora-saved.json'])
out.labels = [loraLabel(HF), loraLabel('https://civitai.com/api/download/models/123456')]
for (const lang of ['zh', 'en'] as const) {
  setLang(lang)
  out[lang] = { loraUrl: wsErrorText('loraUrl'), loraUnsupported: wsErrorText('loraUnsupported') }
}
console.log(JSON.stringify(out))
