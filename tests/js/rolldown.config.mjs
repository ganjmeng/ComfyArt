import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const stubs = { comfy: 'comfy_stub.ts', i18n: 'i18n_stub.ts', tldraw: 'tldraw_stub.ts' }
export default {
  input: path.join(here, process.env.ENTRY || 'workflow_install.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id) {
    const base = id === 'tldraw' ? 'tldraw' : id.startsWith('.') ? path.basename(id) : null
    return base && stubs[base] ? path.join(here, stubs[base]) : null
  } }],
}
