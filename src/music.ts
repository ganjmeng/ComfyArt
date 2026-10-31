// Music models (upstream v1.0.1 MiniMax Music 3 + ACE-Step 1.5, #509 YuE2), run on WaveSpeed instead of local workflows.
import { NO_LYRICS } from './customMarkers'
import { CUSTOM_MUSIC, customModelsAtom, workflowConfigAtom } from './customWorkflows'
import { t } from './i18n'
import { cloudModel, type DurationRange, type WsInputs } from './wavespeed'

export const MINIMAX_MUSIC = 'minimax/music-3.0'
export const ACE_STEP = 'wavespeed-ai/ace-step-1.5'
export const YUE2 = 'wavespeed-ai/yue2-3b/text-to-music'
/** Built-ins whose WaveSpeed schema has no duration field: no slider, no duration sent. */
export const NO_DURATION = new Set([MINIMAX_MUSIC, YUE2])

export interface MusicModel { id: string; label: string; desc: string }
export const MUSIC_MODELS: MusicModel[] = [
  { id: MINIMAX_MUSIC, label: 'MiniMax Music 3', desc: 'Complete songs with stable structure and strong vocals. Put genre, tempo, key, language and vocal style in the prompt.' },
  { id: ACE_STEP, label: 'ACE-Step 1.5', desc: 'Fast. Takes tempo (bpm), lyrics language and key as settings.' },
  { id: YUE2, label: 'YuE2', desc: 'Plans melody and chords first, then sings the lyrics. Put language, genre, vocal, tempo and instruments in the prompt. The length follows the lyrics.' },
]

/** Built-in models, plus the user's custom music model (custom:music) when one is assigned. */
export function musicModels(): MusicModel[] {
  const file = workflowConfigAtom.get().music
  return file ? [...MUSIC_MODELS, { id: CUSTOM_MUSIC, label: file.replace(/\.json$/, ''), desc: t('customWorkflows.customModelDesc') }] : MUSIC_MODELS
}

/** #509: the slider's range from the model's WaveSpeed schema; null when it has no duration field (YuE2,
 * MiniMax music-3.0: the length follows the lyrics) or the catalog does not know the model. */
export function musicDuration(id: string): DurationRange | null {
  if (NO_DURATION.has(id)) return null
  const model = id === CUSTOM_MUSIC ? customModelsAtom.get().music : id
  return (model && cloudModel(model)?.duration_range) || null
}

/** Seconds clamped into the model's range and snapped to its step; unchanged when there is no range. */
export function clampMusicSeconds(id: string, seconds: number): number {
  const range = musicDuration(id)
  if (!range) return seconds
  const snapped = range.min + Math.round((seconds - range.min) / range.step) * range.step
  return Math.min(range.max, Math.max(range.min, snapped))
}

/** #509: empty lyrics go out as [instrumental] (upstream behaviour, awaiting product). To block them instead, set true. */
export const BLOCK_EMPTY_LYRICS = false

/** What a music job is missing before any request or charge: the style prompt (always required; YuE2 sends it as
 * style), or lyrics when BLOCK_EMPTY_LYRICS. null when it may be submitted. */
export function musicMissing(spec: { prompt: string; lyrics: string }): 'prompt' | 'lyrics' | null {
  if (!spec.prompt.trim()) return 'prompt'
  if (BLOCK_EMPTY_LYRICS && !spec.lyrics.trim()) return 'lyrics'
  return null
}

export interface MusicSpec { model: string; prompt: string; lyrics: string; seconds: number; bpm?: number; language?: string; key?: string; seed?: number }

/** WaveSpeed inputs for a music job. bpm / language / key only go out for ACE-Step; MiniMax and YuE2 read them from
 * the prompt. YuE2: the backend maps prompt -> style; lyrics and seed pass through; a duration is never sent. */
export function musicInputs(spec: MusicSpec): WsInputs {
  const ace = spec.model === ACE_STEP
  const music = ace ? Object.fromEntries(Object.entries({ bpm: spec.bpm, language: spec.language, key: spec.key }).filter(([, v]) => v !== undefined && v !== '')) : {}
  const duration = NO_DURATION.has(spec.model) ? undefined : clampMusicSeconds(spec.model, spec.seconds)
  return {
    feature: 'music', model: spec.model, prompt: spec.prompt, lyrics: spec.lyrics || NO_LYRICS,
    ...(duration !== undefined ? { duration } : {}),
    ...(spec.seed !== undefined ? { seed: spec.seed } : {}),
    ...(spec.model === CUSTOM_MUSIC ? { custom: 'music' } : {}),
    ...(Object.keys(music).length ? { music } : {}),
  }
}

/** musicInputs for a job about to be queued; throws (no request, no charge) when musicMissing says it is incomplete. */
export function musicJobInputs(spec: MusicSpec): WsInputs {
  const missing = musicMissing(spec)
  if (missing) throw new Error(t(missing === 'prompt' ? 'audio.needMusicPrompt' : 'audio.needLyrics'))
  return musicInputs(spec)
}
