import { type RefKind } from './comfy'

// Local video graphs were removed: all video generation and editing runs on WaveSpeed.
export const VIDEO_TARGETS: [string, number][] = [['1080p', 1920], ['2K', 2560], ['4K', 3840]]

/** Nearest-up WaveSpeed target_resolution for a user-picked long side (VIDEO_TARGETS). Never smaller than the pick; no exact post-scale. */
export function videoTargetResolution(long: number): '1080p' | '2k' | '4k' {
  if (long >= 3840) return '4k'
  if (long >= 2560) return '2k'
  return '1080p'
}

const snap32 = (v: number) => Math.max(32, Math.round(v / 32) * 32)
export const VIDEO_AREAS: Record<string, number> = { '768p': 1344 * 768, '1080p': 1920 * 1088 }
const H3_AREA = VIDEO_AREAS['768p']

export function videoSize(aspect: number, area = H3_AREA): [number, number] {
  return [snap32(Math.sqrt(area * aspect)), snap32(Math.sqrt(area / aspect))]
}

export interface MediaRef { file: string; kind: RefKind }

export const MAX_VIDEO_REF_KINDS: Record<RefKind, number> = { image: 9, video: 3, audio: 3 }

export interface Scene { prompt: string; duration: number }
