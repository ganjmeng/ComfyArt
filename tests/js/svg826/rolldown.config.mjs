import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
export default {
  input: path.join(here, 'main.tsx'),
  platform: 'browser',
  transform: { define: { 'process.env.NODE_ENV': '"development"' } },
  output: { format: 'iife', file: process.env.OUT, codeSplitting: false },
}
