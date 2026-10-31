// #509 QA: the inputs a music job actually hands to the WaveSpeed hook (wsBuilt -> withCustomModel), with a mock
// custom workflow and without one; empty prompts are refused before anything is built or fetched.
import { files } from './comfy_stub'
import { CUSTOM_MUSIC as CUSTOM_MUSIC_ID, customModelsAtom, withCustomModel, workflowConfigAtom } from '../../src/customWorkflows'
import { ACE_STEP, BLOCK_EMPTY_LYRICS, MINIMAX_MUSIC, musicJobInputs, musicMissing, YUE2 } from '../../src/music'
import { loadCloudModels, wsBuilt } from '../../src/wavespeed'

const g = globalThis as any
const fetched: string[] = []
g.fetch = async (url: string) => { fetched.push(url); return { ok: true, json: async () => ({ enabled: true, features: { music: { default: MINIMAX_MUSIC, available: true, models: [
  { id: MINIMAX_MUSIC, inputs: ['prompt', 'lyrics'] },
  { id: ACE_STEP, inputs: ['tags', 'lyrics', 'duration', 'seed'], duration_range: { min: 5, max: 240, step: 1, default: 60 } },
  { id: YUE2, inputs: ['style', 'lyrics', 'seed'] },
  { id: 'acme/custom-music', inputs: ['prompt', 'duration'], duration_range: { min: 10, max: 600, step: 10 } },
] } } }) } }

/** What the comfy WS hook receives: assetGen's audioGraph (wsBuilt(musicJobInputs)) ws node inputs, through withCustomModel. */
const sent = async (spec: Record<string, unknown>) => {
  const built = wsBuilt(musicJobInputs({ lyrics: '', seconds: 30, ...spec } as any))
  return withCustomModel((built.graph as any).ws.inputs)
}
const refused = async (spec: Record<string, unknown>) => {
  try { await sent(spec); return null } catch (e) { return (e as Error).message }
}

const main = async () => {
  await loadCloudModels()
  const fetchesBefore = fetched.length
  const out: Record<string, unknown> = {
    blockEmptyLyrics: BLOCK_EMPTY_LYRICS,
    missing: { empty: musicMissing({ prompt: '  ', lyrics: '[verse] a' }), noLyrics: musicMissing({ prompt: 'folk', lyrics: '' }) },
    // no custom workflow: default WaveSpeed path, tag dropped
    ace241: await sent({ model: ACE_STEP, prompt: 'lofi', seconds: 241 }),
    ace3: await sent({ model: ACE_STEP, prompt: 'lofi', seconds: 3 }),
    minimax: await sent({ model: MINIMAX_MUSIC, prompt: 'pop', seconds: 180 }),
    yue2: await sent({ model: YUE2, prompt: 'mandarin pop', lyrics: '[verse] 你好', seconds: 120 }),
    yue2NoLyrics: await sent({ model: YUE2, prompt: 'mandarin pop', seconds: 120 }),
    yue2EmptyPrompt: await refused({ model: YUE2, prompt: '   ', lyrics: '[verse] 你好' }),
    aceEmptyPrompt: await refused({ model: ACE_STEP, prompt: '', lyrics: '' }),
    customGone: await refused({ model: CUSTOM_MUSIC_ID, prompt: 'lofi' }),
  }
  out.fetchesDuringJobs = fetched.length - fetchesBefore
  // mock custom workflow assigned for music: same path as every other custom action
  files['comfyart/workflows/music/my-song.json'] = JSON.stringify({ model: 'acme/custom-music', fields: { '@lyrics': 'lyrics' }, params: { seed: 3 } })
  workflowConfigAtom.set({ music: 'my-song.json' })
  customModelsAtom.set({ music: 'acme/custom-music' })
  out.custom = await sent({ model: CUSTOM_MUSIC_ID, prompt: 'lofi', lyrics: '[verse] la', seconds: 33 })
  out.builtInWithCustomAssigned = await sent({ model: ACE_STEP, prompt: 'lofi', seconds: 241 })
  console.log(JSON.stringify(out))
}
main()
