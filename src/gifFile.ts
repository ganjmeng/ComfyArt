/** #825: GIF file naming. Image Auto/default is 2.6-flare; 2.5 remains a named rollback id. */

export const GIF_FLARE = 'openai/gpt-image-2.6-flare/text-to-image'
export const GIF_SUNBURST = 'openai/gpt-image-2.6-sunburst/text-to-image'

export interface GifSpec {
  output_format: 'gif'
  frame_count: number
  frame_duration_ms: number
}

export function clampFrameCount(value: unknown): number {
  const n = Math.round(Number(value))
  if (!Number.isFinite(n)) return 9
  return Math.min(16, Math.max(2, n))
}

export function clampFrameMs(value: unknown): number {
  const n = Math.round(Number(value))
  if (!Number.isFinite(n)) return 200
  return Math.min(2000, Math.max(20, n))
}

/** Sunburst only when the user named that 2.6 family. Anything else, including 2.5 and Auto, uses 2.6-flare. */
/** Bilingual refusal. Still-to-GIF is not implemented; quoting and generation do not start. */
export const GIF_STILL_REFUSAL = '静图转 GIF 不支持参考图，估价和生成都不会开始。请去掉参考图、底图或图片列表后再做纯文生 GIF，或在提示词里描述画面。 / Still-to-GIF does not support a reference image, so quoting and generation do not start. Remove the reference, base image, or image list and use a text-only GIF, or describe the picture in the prompt.'

function filled(value: unknown): boolean {
  if (value == null || value === false) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.some(filled)
  return true
}

/** True when a GIF job carries image, images, refs, or base. Empty values do not count. */
export function gifHasStill(input: { image?: unknown; images?: unknown; refs?: unknown; base?: unknown } | null | undefined): boolean {
  if (!input) return false
  return filled(input.image) || filled(input.images) || filled(input.refs) || filled(input.base)
}

export function gifModelId(id?: string): string {
  return id && id.includes('2.6-sunburst') ? GIF_SUNBURST : GIF_FLARE
}

export function gifSpec(meta: { gif?: unknown } | null | undefined): GifSpec | null {
  const raw = meta?.gif
  if (!raw || typeof raw !== 'object') return null
  if ((raw as { output_format?: unknown }).output_format !== 'gif') return null
  const rec = raw as { frame_count?: unknown; frame_duration_ms?: unknown }
  return { output_format: 'gif', frame_count: clampFrameCount(rec.frame_count), frame_duration_ms: clampFrameMs(rec.frame_duration_ms) }
}

export function placedFile(filename: string, name: string, video: boolean): { name: string; mimeType: string; isAnimated: boolean } {
  const lower = filename.toLowerCase()
  const gif = !video && lower.endsWith('.gif')
  const svg = !video && lower.endsWith('.svg')
  const webp = !video && lower.endsWith('.webp')
  return {
    name: gif && !name.toLowerCase().endsWith('.gif') ? `${name}.gif` : name,
    mimeType: video ? 'video/mp4' : gif ? 'image/gif' : svg ? 'image/svg+xml' : webp ? 'image/webp' : 'image/png',
    isAnimated: video || gif || webp,
  }
}
