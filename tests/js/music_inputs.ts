import { musicInputs, MUSIC_MODELS } from '../../src/music'
const base = { prompt: 'lofi', duration: 30, bpm: 90, language: 'en', key: 'F minor' }
console.log(JSON.stringify({
  models: MUSIC_MODELS.map((m: any) => m.id ?? m.value ?? m),
  minimax: musicInputs({ ...base, model: 'minimax/music-3.0' } as any),
  ace: musicInputs({ ...base, model: 'wavespeed-ai/ace-step-1.5' } as any),
}))
