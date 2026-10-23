// #156: bundle the real ExportDialog + pptx.ts with browser/editor pieces stubbed (no network, no model).
import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const stubs = {
  tldraw: 'tldraw.ts', react: 'react.ts', 'react/jsx-runtime': 'jsx.ts', 'react/jsx-dev-runtime': 'jsx.ts',
  jobs: 'jobs.ts', psd: 'psd.ts', ArtboardShape: 'artboard.ts', Modal: 'ui.ts', Chips: 'ui.ts', i18n: '../i18n_stub.ts',
  palette: 'palette.ts', TextShape: 'shapes.ts', VectorShape: 'shapes.ts', richText: 'shapes.ts',
}
export default {
  input: path.join(here, 'run.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{ name: 'stubs', resolveId(id) {
    const base = id.startsWith('.') ? path.basename(id) : id
    return stubs[base] ? path.join(here, stubs[base]) : null
  } }],
}
