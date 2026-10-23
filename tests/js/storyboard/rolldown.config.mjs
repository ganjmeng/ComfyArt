// #168: bundle real comfy.ts / jobs.ts / wavespeed.ts with browser-only modules stubbed.
import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const stub = path.join(here, 'stubs.ts')
const stubs = { tldraw: stub, Confirm: stub, localPrefs: stub, ws: stub, wavespeedKey: stub, GeneratorShape: stub, i18n: path.join(here, '../i18n_stub.ts') }
export default {
  input: path.join(here, 'run.ts'), platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id) {
    const base = id === 'tldraw' ? 'tldraw' : id.startsWith('.') ? path.basename(id) : null
    return base && stubs[base] ? stubs[base] : null
  } }],
}
