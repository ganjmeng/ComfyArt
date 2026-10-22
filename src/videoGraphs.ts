import { type RefKind } from './comfy'

// Local video graphs were removed: all video generation and editing runs on WaveSpeed.
export const VIDEO_TARGETS: [string, number][] = [['1080p', 1920], ['2K', 2560], ['4K', 3840]]

const snap32 = (v: number) => Math.max(32, Math.round(v / 32) * 32)
export const VIDEO_AREAS: Record<string, number> = { '768p': 1344 * 768, '1080p': 1920 * 1088 }
const H3_AREA = VIDEO_AREAS['768p']

export function videoSize(aspect: number, area = H3_AREA): [number, number] {
  return [snap32(Math.sqrt(area * aspect)), snap32(Math.sqrt(area / aspect))]
}

export interface MediaRef { file: string; kind: RefKind }

export const MAX_VIDEO_REF_KINDS: Record<RefKind, number> = { image: 9, video: 3, audio: 3 }

export interface Scene { prompt: string; duration: number }
