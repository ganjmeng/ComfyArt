// Music models (upstream v1.0.1 MiniMax Music 3 + ACE-Step 1.5), run on WaveSpeed instead of local workflows.
import type { WsInputs } from './wavespeed'

export const MINIMAX_MUSIC = 'minimax/music-3.0'
export const ACE_STEP = 'wavespeed-ai/ace-step-1.5'
export const MUSIC_MODELS = [
  { id: MINIMAX_MUSIC, label: 'MiniMax Music 3', desc: 'Complete songs with stable structure and strong vocals. Put genre, tempo, key, language and vocal style in the prompt.' },
  { id: ACE_STEP, label: 'ACE-Step 1.5', desc: 'Fast. Takes tempo (bpm), lyrics language and key as settings.' },
]

export interface MusicSpec { model: string; prompt: string; lyrics: string; seconds: number; bpm?: number; language?: string; key?: string }

/** WaveSpeed inputs for a music job. bpm / language / key only go out for ACE-Step; MiniMax reads them from the prompt. */
export function musicInputs(spec: MusicSpec): WsInputs {
  const ace = spec.model === ACE_STEP
  const music = ace ? Object.fromEntries(Object.entries({ bpm: spec.bpm, language: spec.language, key: spec.key }).filter(([, v]) => v !== undefined && v !== '')) : {}
  return {
    feature: 'music', model: spec.model, prompt: spec.prompt, lyrics: spec.lyrics || '[instrumental]', duration: spec.seconds,
    ...(Object.keys(music).length ? { music } : {}),
  }
}
