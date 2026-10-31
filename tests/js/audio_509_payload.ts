// #509 PR2: speech/clone/sfx through wsBuilt -> withCustomModel (mock custom files; no WaveSpeed spend).
import { files } from './comfy_stub'
import { CUSTOM_SPEECH, withCustomModel, workflowConfigAtom } from '../../src/customWorkflows'
import { wsBuilt } from '../../src/wavespeed'

const g = globalThis as any
g.fetch = async () => ({ ok: true, json: async () => ({ enabled: true, features: {} }) })

/** Mirror of assetGen.audioInputs — mutations in test_audio_509.py assert the real source stays in sync. */
function audioInputs(spec: { kind: 'speech'; text: string; voice: string } | { kind: 'clone'; text: string; reference: string } | { kind: 'sfx'; prompt: string; seconds: number }, customSpeech = false): Record<string, unknown> {
  if (spec.kind === 'sfx') return { feature: 'sound_effect', custom: 'sfx', prompt: spec.prompt, duration: spec.seconds }
  if (spec.kind === 'speech') return { feature: 'text_to_speech', custom: 'speech', text: spec.text, prompt: spec.text, ...(customSpeech ? {} : { voice: spec.voice }) }
  return { feature: 'voice_clone', custom: 'clone', text: spec.text, prompt: spec.text, audio: spec.reference }
}

const sent = async (inputs: Record<string, unknown>) => {
  const built = wsBuilt(inputs)
  return withCustomModel((built.graph as any).ws.inputs)
}
const refused = async (inputs: Record<string, unknown>) => {
  try { await sent(inputs); return null } catch (e) { return (e as Error).message }
}

const main = async () => {
  workflowConfigAtom.set({})
  const out: Record<string, unknown> = {
    speech: await sent(audioInputs({ kind: 'speech', text: 'hello', voice: 'Serena' }, false)),
    clone: await sent(audioInputs({ kind: 'clone', text: 'hi', reference: 'a.wav [input]' })),
    sfx: await sent(audioInputs({ kind: 'sfx', prompt: 'boom', seconds: 5 })),
    speechGone: await refused({ feature: 'text_to_speech', custom: 'speech', model: CUSTOM_SPEECH, text: 'x', prompt: 'x' }),
  }
  files['comfyart/workflows/speech/my-voice.json'] = JSON.stringify({ model: 'acme/custom-tts', fields: { '@prompt': 'text' }, params: { voice: 'Alloy' } })
  files['comfyart/workflows/clone/my-clone.json'] = JSON.stringify({ model: 'acme/custom-clone', fields: { '@audio': 'audio', '@prompt': 'text' }, params: {} })
  files['comfyart/workflows/sfx/my-sfx.json'] = JSON.stringify({ model: 'acme/custom-sfx', fields: { '@prompt': 'prompt' }, params: { seed: 1 } })
  workflowConfigAtom.set({ speech: 'my-voice.json', clone: 'my-clone.json', sfx: 'my-sfx.json' })
  out.customSpeech = await sent(audioInputs({ kind: 'speech', text: 'hello', voice: 'Serena' }, true))
  out.customClone = await sent(audioInputs({ kind: 'clone', text: 'hi', reference: 'a.wav [input]' }))
  out.customSfx = await sent(audioInputs({ kind: 'sfx', prompt: 'boom', seconds: 5 }))
  out.speechTaggedWithCustomAssigned = await sent(audioInputs({ kind: 'speech', text: 'hello', voice: 'Serena' }, false))
  console.log(JSON.stringify(out))
}
main()
