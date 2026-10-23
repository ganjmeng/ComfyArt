// #95: the generator menu's Auto entry hands the model back to the agent / feature default; a user pick is used as-is.
import { g } from './comfy_stub'
import { adjustForModel, AUTO_IMAGE, AUTO_VIDEO, FEATURE_MODELS, isAuto, refCap, isCloudModel, isVideo, loadModels, modelOf } from '../../src/models'
import { modelIn, withModel, wsBuilt } from '../../src/wavespeed'

const feature = (ids: string[]) => ({ default: ids[0], available: true, models: ids.map((id, i) => ({ id, label: id, price: 0.01 * (i + 1), desc: '', default: i === 0, qualities: id.includes('2.5') ? ['low', 'medium', 'high'] : undefined, defaults: id.includes('2.5') ? { quality: 'medium' } : id.includes('kling') ? { duration: 5, resolution: '1080p' } : undefined, aspect_ratios: id.includes('kling') ? ['16:9', '9:16', '1:1'] : undefined, durations: id.includes('kling') ? [5, 10] : undefined, resolutions: id.includes('kling') ? ['720p', '1080p'] : undefined, max_images: id.includes('nano') ? 3 : undefined })) })
const features = {
  text_to_image: feature(['openai/gpt-image-2/text-to-image', 'openai/gpt-image-2.5-sunburst/text-to-image']),
  image_edit: feature(['openai/gpt-image-2/edit', 'google/nano-banana-pro/edit']),
  text_to_video: feature(['bytedance/seedance-2.0/text-to-video', 'kwaivgi/kling-v3.0-pro/text-to-video']),
  image_to_video: feature(['bytedance/seedance-2.0/image-to-video']),
}
g.fetch = async () => ({ ok: true, json: async () => ({ features }) })

await loadModels()
// what generate.ts builds for a text-to-image card, then startJob applies the agent's pending pick with withModel
const run = (workflow: string, agentPick?: string) => {
  const m = modelOf(workflow)!
  const built = wsBuilt({ feature: 'text_to_image', model: m.auto ? undefined : m.id, prompt: 'x' })
  withModel(built.graph, agentPick)
  return built.graph.ws.inputs.model ?? null
}
const pick = 'openai/gpt-image-2.5-sunburst/text-to-image'
console.log(JSON.stringify({
  autoIsCloud: isCloudModel(AUTO_IMAGE) && isCloudModel(AUTO_VIDEO), autoVideo: isVideo(AUTO_VIDEO), autoImageIsImage: !isVideo(AUTO_IMAGE),
  isAuto: [isAuto(AUTO_IMAGE), isAuto(pick)],
  autoNoAgent: run(AUTO_IMAGE), autoAgent: run(AUTO_IMAGE, 'google/nano-banana-pro/text-to-image'),
  userPick: run(pick, 'google/nano-banana-pro/text-to-image'),
  videoAuto: modelIn('text_to_video', AUTO_VIDEO) ?? null, videoPick: modelIn('text_to_video', 'kwaivgi/kling-v3.0-pro/text-to-video') ?? null,
  tabs: Object.fromEntries(Object.entries(FEATURE_MODELS).map(([f, l]) => [f, l.map((m) => m.id)])),
  tiers: modelOf(pick)?.qualities ?? null,
  // switching models keeps what still fits, resets the rest to the new model's default
  adjustKeep: adjustForModel({ ratio: '16:9', duration: 10, resolution: '720p', quality: 'standard' }, modelOf('kwaivgi/kling-v3.0-pro/text-to-video'), true),
  adjustReset: adjustForModel({ ratio: '21:9', duration: 15, resolution: '4k', quality: 'standard' }, modelOf('kwaivgi/kling-v3.0-pro/text-to-video'), true),
  adjustTier: adjustForModel({ ratio: '1:1', duration: 5, resolution: '1k', quality: 'standard' }, modelOf(pick), false),
  adjustAuto: adjustForModel({ ratio: '21:9', duration: 15, resolution: '4k', quality: 'x' }, modelOf(AUTO_VIDEO), true),
  refCap: [refCap(FEATURE_MODELS.image_edit[1], 5), refCap(FEATURE_MODELS.image_edit[1], 2), refCap(FEATURE_MODELS.image_edit[0], 9)],
}))
