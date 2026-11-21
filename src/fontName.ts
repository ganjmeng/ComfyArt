/** CSS generic families stay unquoted. Every other name is quoted so a leading digit or a comma stays one family. */
const GENERIC_FAMILIES = new Set([
  'serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 'system-ui',
  'ui-serif', 'ui-sans-serif', 'ui-monospace', 'ui-rounded', 'emoji', 'math',
])

export function cssFamily(font: string): string {
  return font.split(',').map((f) => f.replace(/["']/g, '').trim()).filter(Boolean).map((f) => (GENERIC_FAMILIES.has(f) ? f : `"${f}"`)).join(', ')
}

/** Family stored for an uploaded font file: drop the extension and characters that split a CSS font stack. */
export function fontFamilyFromFilename(name: string): string {
  return name.replace(/\.(ttf|otf|woff2?)$/i, '').replace(/[,"']+/g, ' ').trim()
}
