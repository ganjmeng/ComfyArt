import path from 'node:path'

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../..')

export default {
  input: path.join(root, 'tests/js/chatlink/main.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
}
