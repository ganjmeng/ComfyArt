/** Stub exportImage for #386 review tests — no canvas, no GPU. */
export async function exportImage() {
  const g = globalThis as any
  g.__exportCalls = (g.__exportCalls ?? 0) + 1
  if (typeof g.__exportImpl === 'function') return g.__exportImpl()
  return { blob: new Blob(['png'], { type: 'image/png' }) }
}
export class ArtboardShapeUtil {}
export const artboardStyle = () => ({})
