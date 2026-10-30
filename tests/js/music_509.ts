// #509: schema-driven music length, YuE2 inputs, custom:music tagging (src/music.ts under node).
import { CUSTOM_MUSIC, customModelsAtom, workflowConfigAtom } from '../../src/customWorkflows'
import { ACE_STEP, clampMusicSeconds, MINIMAX_MUSIC, musicDuration, musicInputs, musicModels, MUSIC_MODELS, YUE2 } from '../../src/music'
import { loadCloudModels } from '../../src/wavespeed'

const range = { min: 5, max: 240, step: 1, default: 60 }
const g = globalThis as any
g.fetch = async () => ({ ok: true, json: async () => ({ enabled: true, features: { music: { default: MINIMAX_MUSIC, available: true, models: [
  { id: MINIMAX_MUSIC, inputs: ['prompt', 'lyrics'] },
  { id: ACE_STEP, inputs: ['tags', 'lyrics', 'duration', 'seed'], duration_range: range },
  // even if a catalog ever reported a range for these, they stay slider-less (product ruling)
  { id: YUE2, inputs: ['style', 'lyrics', 'seed'], duration_range: { min: 1, max: 900, step: 1 } },
  { id: 'acme/custom-music', inputs: ['prompt', 'duration'], duration_range: { min: 10, max: 600, step: 10 } },
] } } }) })

const main = async () => {
  const before = musicDuration(ACE_STEP)
  await loadCloudModels()
  workflowConfigAtom.set({ music: 'my-song.json' })
  customModelsAtom.set({ music: 'acme/custom-music' })
  const base = { prompt: 'lofi', lyrics: '', seconds: 600 }
  console.log(JSON.stringify({
    builtIn: MUSIC_MODELS.map((m) => m.id),
    picker: musicModels().map((m) => m.id),
    before,
    range: { ace: musicDuration(ACE_STEP), minimax: musicDuration(MINIMAX_MUSIC), yue2: musicDuration(YUE2), custom: musicDuration(CUSTOM_MUSIC) },
    clamp: { aceHigh: clampMusicSeconds(ACE_STEP, 600), aceLow: clampMusicSeconds(ACE_STEP, 1), custom: clampMusicSeconds(CUSTOM_MUSIC, 33), yue2: clampMusicSeconds(YUE2, 600) },
    inputs: {
      ace: musicInputs({ ...base, model: ACE_STEP }),
      minimax: musicInputs({ ...base, model: MINIMAX_MUSIC }),
      yue2: musicInputs({ ...base, model: YUE2, lyrics: '[verse] 你好\n[chorus] 再见', seed: 7 }),
      yue2Empty: musicInputs({ ...base, model: YUE2 }),
      custom: musicInputs({ ...base, model: CUSTOM_MUSIC }),
    },
  }))
}
main()
