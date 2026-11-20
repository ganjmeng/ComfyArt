import path from 'node:path'

const here = path.dirname(new URL(import.meta.url).pathname)
const root = path.resolve(here, '../../..')
const stubs = {
  tldraw: 'tldraw.ts',
  comfy: 'comfy.ts',
  quoteAnswer: 'quoteAnswer.ts',
  jobs: 'jobs.ts',
  notices: 'notices.ts',
  ws: 'ws.ts',
  i18n: 'i18n.ts',
  wsErrors: 'wsErrors.ts',
  schedulePending: 'schedulePending.ts',
}

export default {
  input: path.join(here, 'chain.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{
    name: 'bot-stubs',
    resolveId(id) {
      if (id === 'tldraw') return path.join(here, 'stubs/tldraw.ts')
      if (!id.startsWith('.')) return null
      const base = path.basename(id).replace(/\.ts$/, '')
      return stubs[base] ? path.join(here, 'stubs', stubs[base]) : null
    },
  }],
}
