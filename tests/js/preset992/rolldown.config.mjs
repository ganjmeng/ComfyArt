import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const stubs = {
  tldraw: path.join(here, '../preset978/tldraw_stub.ts'),
  i18n: path.join(here, '../preset978/i18n_stub.ts'),
}
const shared = path.join(here, '../preset978/stubs.ts')
for (const name of ['bot', 'generate', 'jobs', 'library', 'llm', 'memory', 'chatFrame', 'canvasSnapshot',
  'models', 'actions', 'EmbedShapes', 'GeneratorShape', 'CommentShape', 'comfy']) stubs[name] = shared
export default {
  input: path.join(here, 'main.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id) {
    const base = path.basename(id).replace(/\.ts$/, '')
    if (process.env.CA992_SKILL_RAW && base === 'skillRaw748') return process.env.CA992_SKILL_RAW
    if (!id.startsWith('.')) return stubs[id] ?? null
    return stubs[path.basename(id)] ?? null
  } }],
}
