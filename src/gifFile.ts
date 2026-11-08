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
