// Build a self-contained offline component preview. Not a product/backend test.
// OUT_DIR=/absolute/path [BEFORE_CSS=/absolute/before.css] node tests/js/buildConfirmVisualPreview.mjs
import { rolldown } from 'rolldown'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const dir = process.env.OUT_DIR
if (!dir || !path.isAbsolute(dir)) throw new Error('OUT_DIR must be an absolute output directory')
mkdirSync(dir, { recursive: true })
const build = await rolldown({
  input: path.join(root, 'tests/js/confirmVisualPreview.tsx'),
  platform: 'browser',
  transform: { define: {
    'process.env.NODE_ENV': '"production"',
    'import.meta.env': '{ DEV: false, PROD: true, MODE: "production" }',
  } },
})
const { output } = await build.generate({ format: 'iife', codeSplitting: false })
const js = output.find(part => part.type === 'chunk').code.replaceAll('</script', '<\\/script')
const common = ['base', 'home', 'overlays', 'shell'].map(name => readFileSync(path.join(root, `src/styles/${name}.css`), 'utf8')).join('\n')
for (const mode of process.env.BEFORE_CSS ? ['before', 'after'] : ['after']) {
  const css = readFileSync(mode === 'before' ? process.env.BEFORE_CSS : path.join(root, 'src/styles/controls.css'), 'utf8')
  const html = `<!DOCTYPE html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ComfyArt Confirm component ${mode}</title><style>${common}\n${css}\nbody{margin:0;background:var(--ca-float);color:var(--ca-text);font:14px/1.5 sans-serif}aside{position:fixed;z-index:3000;top:16px;left:16px;right:16px;font:12px/18px sans-serif;pointer-events:none}</style><aside>实际 Confirm 组件预览 · MOCK 报价，无后端调用 · ${mode}</aside><div id="root"></div><script>${js}</script></html>`
  writeFileSync(path.join(dir, `${mode}.html`), html)
}
await build.close()
console.log(`Offline component preview written to ${dir}`)
