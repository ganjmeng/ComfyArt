import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const stubs = {
  tldraw: path.join(here, 'tldraw_stub.ts'),
  i18n: path.join(here, 'i18n_stub.ts'),
}
const shared = path.join(here, 'stubs.ts')
for (const name of ['bot', 'generate', 'jobs', 'library', 'llm', 'memory', 'chatFrame', 'canvasSnapshot',
  'models', 'actions', 'EmbedShapes', 'GeneratorShape', 'CommentShape', 'comfy']) stubs[name] = shared
export default {
  input: path.join(here, process.env.ENTRY || 'main.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id) {
    if (!id.startsWith('.')) return stubs[id] ?? null
    return stubs[path.basename(id)] ?? null
  } }],
}
