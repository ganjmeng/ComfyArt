/** #826: canvas shows a PNG preview. The .svg file is only an attachment download. */

export const SVG_FLARE = 'openai/gpt-image-2.6-flare/text-to-image'
export const SVG_SUNBURST = 'openai/gpt-image-2.6-sunburst/text-to-image'

/** 1×1 gray PNG. Used when a raster cannot be produced. Never an SVG URL. */
export const RASTER_FAIL_PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='

export interface SvgSpec {
  output_format: 'svg'
  n: 1
}

export interface SvgRef {
  filename: string
  subfolder?: string
  type?: string
  svg_preview?: string
  svg_state?: string
  svg_message?: string
}

export function svgModelId(id?: string): string {
  return id && id.includes('2.6-sunburst') && !id.endsWith('/edit') ? SVG_SUNBURST : SVG_FLARE
}

export function svgSpec(meta: { svg?: unknown } | null | undefined): SvgSpec | null {
  const raw = meta?.svg
  if (!raw || typeof raw !== 'object') return null
  if ((raw as { output_format?: unknown }).output_format !== 'svg') return null
  return { output_format: 'svg', n: 1 }
}

/** A direct /api/view of a .svg is not a canvas image source. Thumbs and PNG previews are. */
export function canvasSrcAllowed(src: string): boolean {
  if (!src) return false
  if (src.startsWith('data:image/png') || src.startsWith('blob:') || src.startsWith('/comfyart/thumb?')) return true
  try {
    const name = new URL(src, 'http://local').searchParams.get('filename') || ''
    return !name.toLowerCase().endsWith('.svg')
  } catch {
    return !/\.svg(\?|#|$)/i.test(src)
  }
}

/** Browser raster load target. An SVG view URL becomes the thumb route, which returns a PNG. */
export function rasterLoadSrc(src: string): string {
  if (canvasSrcAllowed(src)) return src
  return `/comfyart/thumb?${new URLSearchParams({ url: src, max: '1024' })}`
}

export function svgAsset(ref: SvgRef): {
  inlineSvg: false
  displaySrc: string
  downloadUrl: string
  downloadName: string
  state: string
  message: string
  mimeType: 'image/png'
} | null {
  if (!ref.filename.toLowerCase().endsWith('.svg')) return null
  const sub = ref.subfolder || ''
  const type = ref.type || 'output'
  const svgView = `/api/view?${new URLSearchParams({ filename: ref.filename, subfolder: sub, type })}`
  const displaySrc = ref.svg_preview
    ? `/api/view?${new URLSearchParams({ filename: ref.svg_preview, subfolder: sub, type })}`
    : `/comfyart/thumb?${new URLSearchParams({ url: svgView, max: '1024' })}`
  return {
    inlineSvg: false,
    displaySrc,
    downloadUrl: `/comfyart/svg_download?${new URLSearchParams({ url: svgView })}`,
    downloadName: ref.filename,
    state: ref.svg_state || '',
    message: ref.svg_message || '',
    mimeType: 'image/png',
  }
}
