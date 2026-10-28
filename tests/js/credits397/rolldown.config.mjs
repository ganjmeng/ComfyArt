import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const layer = path.join(here, '../layer')
const stubs = { tldraw: path.join(layer, 'tldraw.ts'), i18n: path.join(here, '../i18n_stub.ts') }
export default {
  input: path.join(here, 'main.tsx'),
  platform: 'browser',
  transform: { define: { 'process.env.NODE_ENV': '"development"' } },
  output: { format: 'iife', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id, from) {
    if (from && from.startsWith(here) && !from.endsWith('main.tsx')) return null
    if (id === 'tldraw') return stubs.tldraw
    if (id.startsWith('.') && path.basename(id) === 'i18n') return stubs.i18n
    return null
  } }],
}
