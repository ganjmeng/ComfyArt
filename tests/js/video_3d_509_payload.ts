// #509 PR3: extend/videoUpscale/videoCutout/model3d through wsBuilt -> withCustomModel (mock; $0).
import { files } from './comfy_stub'
import { CUSTOM_MODEL3D, withCustomModel, workflowConfigAtom } from '../../src/customWorkflows'
import { videoTargetResolution } from '../../src/videoGraphs'
import { wsBuilt } from '../../src/wavespeed'

const g = globalThis as any
g.fetch = async () => ({ ok: true, json: async () => ({ enabled: true, features: {} }) })

function videoInputs(kind: 'extend' | 'videoUpscale' | 'videoCutout', video = 'clip.mp4 [input]'): Record<string, unknown> {
  if (kind === 'extend') return { feature: 'extend_video', custom: 'extend', video, prompt: 'go on', duration: 5 }
  if (kind === 'videoUpscale') return { feature: 'upscale_video', custom: 'videoUpscale', video, params: { target_resolution: videoTargetResolution(2560) } }
  return { feature: 'remove_video_background', custom: 'videoCutout', video }
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
    extend: await sent(videoInputs('extend')),
    videoUpscale: await sent(videoInputs('videoUpscale')),
    videoCutout: await sent(videoInputs('videoCutout')),
    model3dBuiltIn: await sent({ feature: 'image_to_3d', image: 'a.png [input]' }),
    model3dGone: await refused({ feature: 'image_to_3d', custom: 'model3d', model: CUSTOM_MODEL3D, image: 'a.png [input]' }),
  }
  files['comfyart/workflows/extend/my-extend.json'] = JSON.stringify({ model: 'acme/custom-extend', fields: { '@video': 'video', '@prompt': 'prompt' }, params: {} })
  files['comfyart/workflows/videoUpscale/my-up.json'] = JSON.stringify({ model: 'acme/custom-vup', fields: { '@video': 'video' }, params: { seed: 1 } })
  files['comfyart/workflows/videoCutout/my-cut.json'] = JSON.stringify({ model: 'acme/custom-vcut', fields: { '@video': 'video' }, params: {} })
  files['comfyart/workflows/model3d/my-3d.json'] = JSON.stringify({ model: 'acme/custom-3d', fields: { '@image': 'image' }, params: {} })
  workflowConfigAtom.set({ extend: 'my-extend.json', videoUpscale: 'my-up.json', videoCutout: 'my-cut.json', model3d: 'my-3d.json' })
  out.customExtend = await sent(videoInputs('extend'))
  out.customUpscale = await sent(videoInputs('videoUpscale'))
  out.customCutout = await sent(videoInputs('videoCutout'))
  out.customModel3d = await sent({ feature: 'image_to_3d', custom: 'model3d', model: CUSTOM_MODEL3D, image: 'a.png [input]' })
  out.needsVideo = await refused({ feature: 'extend_video', custom: 'extend', prompt: 'x', duration: 5 })
  console.log(JSON.stringify(out))
}
main()
