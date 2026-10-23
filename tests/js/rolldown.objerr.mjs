// Bundles the four real fetch sites; every other import becomes an inert stub so only the error path runs.
import fs from 'node:fs'
import path from 'node:path'
const here = path.dirname(new URL(import.meta.url).pathname)
const real = new Set(['elements', 'projects', 'bot', 'llm', 'wsErrors', 'object_errors', 'i18n_stub', 'objerr_comfy_stub'])
const stubs = { comfy: 'objerr_comfy_stub.ts', i18n: 'i18n_stub.ts' }
const NOOP = 'const n = new Proxy(function () {}, { get: (_t, k) => (k === Symbol.toPrimitive ? () => "" : k === "then" ? undefined : n), apply: () => n, construct: () => n })\n'
export default {
  input: path.join(here, 'object_errors.ts'),
  platform: 'node',
  output: { format: 'esm', file: process.env.OUT },
  plugins: [{ name: 'objerr-stubs',
    resolveId(id, importer) {
      if (!importer || id.startsWith('\0') || importer.startsWith('\0')) return null
      const base = id.startsWith('.') ? path.basename(id).replace(/\.tsx?$/, '') : id
      if (stubs[base]) return path.join(here, stubs[base])
      if (id.startsWith('.') && real.has(base)) return null
      if (id.endsWith('.json')) return null
      const src = fs.readFileSync(importer, 'utf8')
      const names = new Set()
      for (const m of src.matchAll(/import\s+(?:type\s+)?\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]/g)) {
        if (m[2] !== id) continue
        for (const part of m[1].split(',')) { const p = part.trim(); if (p && !p.startsWith('type ')) names.add(p.split(/\s+as\s+/)[0].trim()) }
      }
      return '\0stub:' + [...names].join(',')
    },
    load(id) {
      if (!id.startsWith('\0stub:')) return null
      const names = id.slice(6).split(',').filter(Boolean)
      return NOOP + names.map((x) => `export const ${x} = n`).join('\n') + '\nexport default n\n'
    } }],
}
