import { t } from './i18n'
import { VIDEO_AREAS } from './videoGraphs'

export const RESOLUTIONS = ['1K', '2K', 'custom']
export const QUALITIES: [string, string][] = [['fast', t('generate.turbo')], ['standard', t('generate.standard')], ['high', t('generate.highQuality')]]
export const SHOTS: [string, string, string][] = [
  ['', t('common.auto'), ''], ['fixed', t('generate.static'), 'static locked-off camera'], ['advance', t('generate.pushIn'), 'slow push-in toward the subject'],
  ['zoom_out', t('generate.pullOut'), 'slow pull-back revealing the scene'], ['orbit', t('generate.orbit'), 'camera orbits around the subject'],
  ['follow', t('generate.follow'), 'tracking shot following the subject'], ['handheld', t('generate.handheld'), 'handheld camera with natural shake'],
  ['left', t('generate.panLeft'), 'camera pans left'], ['right', t('generate.panRight'), 'camera pans right'], ['up', t('generate.tiltUp'), 'camera tilts up'], ['down', t('generate.tiltDown'), 'camera tilts down'],
]

export const STYLES: [string, string, string][] = [
  ['', t('common.none'), ''], ['photo', t('generate.photo'), 'professional photography, natural light, sharp focus'], ['cinematic', t('generate.cinematic'), 'cinematic still, dramatic lighting, film grain'],
  ['illustration', t('common.illustration'), 'editorial illustration, clean shapes'], ['3d', '3D', 'high quality 3D render, soft studio light'], ['anime', t('common.anime'), 'anime style, cel shading'],
  ['minimal', t('generate.minimal'), 'minimalist design, generous negative space'], ['retro', t('generate.retro'), 'retro vintage print, muted colors, halftone texture'],
]
export const RATIOS = ['1:1', '3:2', '2:3', '4:3', '3:4', '16:9', '9:16', '4:5', '5:4', '21:9']
export const VIDEO_RATIOS = ['16:9', '9:16', '1:1', '4:3', '3:4', '21:9']
export const DURATIONS = [5, 10, 15]

/** #128: the shortest allowed duration not below the requested seconds, capped at the longest one. */
export function fitDuration(want: unknown, allowed?: number[]): number {
  const opts = (allowed?.length ? allowed : DURATIONS).map(Number).filter((d) => d > 0).sort((a, b) => a - b)
  const n = Number(want)
  if (!Number.isFinite(n) || n <= 0) return opts[0]
  return opts.find((d) => d >= n) ?? opts[opts.length - 1]
}

/** #128: what the confirm dialog / tool result says when the requested duration is not one the model takes. */
export function durationNote(asked: unknown, actual: number, allowed?: number[], say: (key: string, ...a: (string | number)[]) => string = t): string {
  const n = Number(asked)
  if (!Number.isFinite(n) || n <= 0 || n === actual) return ''
  const opts = (allowed?.length ? allowed : DURATIONS).map(Number)
  const key = n < Math.min(...opts) ? 'genOptions.durationMin' : n > Math.max(...opts) ? 'genOptions.durationMax' : 'genOptions.durationUp'
  return say(key, n, actual)
}
export const VIDEO_RESOLUTIONS = Object.keys(VIDEO_AREAS)
