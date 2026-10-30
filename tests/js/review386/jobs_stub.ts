/** Minimal jobs stub for #386 review tests. */
import type { Editor, TLShape } from 'tldraw'

type ImagePlacedFn = () => void
const placed: ImagePlacedFn[] = []

export type ErrorSink = (msg: string) => void
export const errorText = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function onImagePlaced(cb: ImagePlacedFn): () => void {
  placed.push(cb)
  return () => {
    const i = placed.indexOf(cb)
    if (i >= 0) placed.splice(i, 1)
  }
}
export function fireImagePlaced() { for (const cb of [...placed]) cb() }

export type MediaAsset = { props: { src?: string } }
export function mediaAsset(_editor: Editor, shape: TLShape | undefined): MediaAsset | null {
  const g = globalThis as any
  if (typeof g.__mediaAssetImpl === 'function') return g.__mediaAssetImpl(_editor, shape)
  const p = (shape as any)?.props
  if (!p?.assetId && !p?.src) return null
  return { props: { src: p?.src ?? `asset://${p.assetId}` } }
}
