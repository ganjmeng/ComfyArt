// #513 step1 / #528: motion/lipsync/generate through wsBuilt -> withCustomModel (mock; $0).
import { files } from './comfy_stub'
import { CUSTOM_GENERATE, withCustomModel, workflowConfigAtom } from '../../src/customWorkflows'
import { wsBuilt } from '../../src/wavespeed'

const g = globalThis as any
g.fetch = async () => ({ ok: true, json: async () => ({ enabled: true, features: {} }) })

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
    motion: await sent({ feature: 'motion_control', custom: 'motion', image: 'c.png [input]', video: 'm.mp4 [input]', prompt: 'move' }),
    lipsync: await sent({ feature: 'lip_sync', custom: 'lipsync', image: 'f.png [input]', audio: 's.mp3 [input]', prompt: 'talk' }),
    generateGone: await refused({ feature: 'text_to_image', custom: 'generate', model: CUSTOM_GENERATE, prompt: 'x', width: 512, height: 512 }),
  }
  files['comfyart/workflows/motion/my-motion.json'] = JSON.stringify({ model: 'acme/custom-motion', fields: { '@image': 'image', '@video': 'video', '@prompt': 'prompt' }, params: {} })
  files['comfyart/workflows/lipsync/my-lipsync.json'] = JSON.stringify({ model: 'acme/custom-lipsync', fields: { '@image': 'image', '@audio': 'audio', '@prompt': 'prompt' }, params: {} })
  files['comfyart/workflows/generate/my-gen.json'] = JSON.stringify({ model: 'acme/custom-gen', fields: { '@prompt': 'prompt', '@image': 'image' }, params: {} })
  files['comfyart/workflows/generate/my-gen-base.json'] = JSON.stringify({ model: 'acme/custom-gen-base', fields: { '@prompt': 'prompt', '@image': 'image', '@base': 'image', '@strength': 'strength' }, params: {} })
  files['comfyart/workflows/generate/my-gen-nobase.json'] = JSON.stringify({ model: 'acme/custom-gen2', fields: { '@prompt': 'prompt' }, params: {} })
  workflowConfigAtom.set({ motion: 'my-motion.json', lipsync: 'my-lipsync.json', generate: 'my-gen.json' })
  out.customMotion = await sent({ feature: 'motion_control', custom: 'motion', image: 'c.png [input]', video: 'm.mp4 [input]', prompt: 'move' })
  out.customLipsync = await sent({ feature: 'lip_sync', custom: 'lipsync', image: 'f.png [input]', audio: 's.mp3 [input]', prompt: 'talk' })
  out.customGenerate = await sent({ feature: 'text_to_image', custom: 'generate', model: CUSTOM_GENERATE, prompt: 'a cat', width: 512, height: 512, image: 'a.png [input]' })
  out.needsVideo = await refused({ feature: 'motion_control', custom: 'motion', image: 'c.png [input]', prompt: 'move' })
  out.needsAudio = await refused({ feature: 'lip_sync', custom: 'lipsync', image: 'f.png [input]', prompt: 'talk' })
  out.needsImage = await refused({ feature: 'text_to_image', custom: 'generate', model: CUSTOM_GENERATE, prompt: 'x', width: 512, height: 512 })
  workflowConfigAtom.set({ generate: 'my-gen-base.json' })
  out.customGenerateBase = await sent({ feature: 'text_to_image', custom: 'generate', model: CUSTOM_GENERATE, prompt: 'a cat', width: 512, height: 512, image: 'a.png [input]', base: 'b.png [input]', strength: 0.5 })
  workflowConfigAtom.set({ generate: 'my-gen-nobase.json' })
  out.unusedBase = await refused({ feature: 'text_to_image', custom: 'generate', model: CUSTOM_GENERATE, prompt: 'x', width: 512, height: 512, base: 'b.png [input]' })
  console.log(JSON.stringify(out))
}
main()
