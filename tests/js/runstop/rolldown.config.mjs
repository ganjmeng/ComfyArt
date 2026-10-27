import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
// #393: the real RunStop card (src/ui/ChatMessage.tsx), real tldraw; only i18n is stubbed (switchable lang)
const stubs = { i18n: '../i18n_stub.ts' }
export default {
  input: path.join(here, 'main.tsx'),
  platform: 'browser',
  transform: { define: { 'process.env.NODE_ENV': '"development"' } },
  output: { format: 'iife', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id) {
    const base = id.startsWith('.') ? path.basename(id) : null
    return base && stubs[base] ? path.join(here, stubs[base]) : null
  } }],
}
