import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const stubs = { comfy: 'comfy.ts', jobs: 'jobs.ts', workflows: 'workflows.ts', tldraw: 'tldraw.ts', i18n: '../i18n_stub.ts' }
export default {
  input: path.join(here, 'main.tsx'),
  platform: 'browser',
  transform: { define: { 'process.env.NODE_ENV': '"development"' } },
  output: { format: 'iife', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id, from) {
    if (from && from.startsWith(here) && !from.endsWith('main.tsx')) return null
    const base = id === 'tldraw' ? 'tldraw' : id.startsWith('.') ? path.basename(id) : null
    return base && stubs[base] ? path.join(here, stubs[base]) : null
  } }],
}
