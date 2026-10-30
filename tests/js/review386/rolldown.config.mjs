import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const root = path.join(here, '..')
const stubs = {
  comfy: path.join(root, 'comfy_stub.ts'),
  i18n: path.join(root, 'i18n_stub.ts'),
  tldraw: path.join(root, 'tldraw_stub.ts'),
  llm: path.join(root, 'llm_stub.ts'),
  ArtboardShape: path.join(root, 'artboard_stub.ts'),
  jobs: path.join(here, 'jobs_stub.ts'),
  bot: path.join(here, 'bot_stub.ts'),
  ws: path.join(here, 'ws_stub.ts'),
  memory: path.join(here, 'memory_stub.ts'),
  memoryStore: path.join(here, 'memoryStore_stub.ts'),
  skills: path.join(here, 'skills_stub.ts'),
  notices: path.join(here, 'notices_stub.ts'),
}
export default {
  input: path.join(here, process.env.ENTRY || 'main.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id) {
    if (id === 'tldraw') return stubs.tldraw
    if (!id.startsWith('.')) return null
    const base = path.basename(id)
    return stubs[base] ?? null
  } }],
}
