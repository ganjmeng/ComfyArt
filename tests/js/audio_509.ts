// #509 PR2: speech / clone / sfx tag shape (mirrors src/assetGen.ts audioInputs; source mutations guard drift).
import { CUSTOM_SPEECH, workflowConfigAtom } from '../../src/customWorkflows'

/** Mirror of assetGen.audioInputs — keep in sync; test_audio_509 mutations assert the real source. */
function audioInputs(spec: { kind: 'speech'; text: string; voice: string } | { kind: 'clone'; text: string; reference: string } | { kind: 'sfx'; prompt: string; seconds: number }, customSpeech = !!workflowConfigAtom.get().speech): Record<string, unknown> {
  if (spec.kind === 'sfx') return { feature: 'sound_effect', custom: 'sfx', prompt: spec.prompt, duration: spec.seconds }
  if (spec.kind === 'speech') return { feature: 'text_to_speech', custom: 'speech', text: spec.text, prompt: spec.text, ...(customSpeech ? {} : { voice: spec.voice }) }
  return { feature: 'voice_clone', custom: 'clone', text: spec.text, prompt: spec.text, audio: `${spec.reference}` }
}

const main = () => {
  workflowConfigAtom.set({})
  const speechBuiltIn = audioInputs({ kind: 'speech', text: '你好', voice: 'Serena' }, false)
  const speechCustom = audioInputs({ kind: 'speech', text: '你好', voice: 'Serena' }, true)
  const clone = audioInputs({ kind: 'clone', text: '克隆一句', reference: 'ref.wav [input]' })
  const sfx = audioInputs({ kind: 'sfx', prompt: 'whoosh', seconds: 8 })
  console.log(JSON.stringify({
    speechBuiltIn,
    speechCustom,
    clone,
    sfx,
    customSpeechId: CUSTOM_SPEECH,
  }))
}
main()
