// #201: the negative prompt box follows the model schema (negative_prompt in inputs); hidden models never send it.
import { g } from './comfy_stub'
import { hasNegative, loadModels, modelOf } from '../../src/models'

const m = (id: string, inputs: string[]) => ({ id, label: id, price: 0.01, desc: '', default: false, inputs })
const features = {
  text_to_image: { default: 'a/with-neg/text-to-image', available: true, models: [m('a/with-neg/text-to-image', ['prompt', 'negative_prompt', 'seed']), m('b/no-neg/text-to-image', ['prompt', 'seed'])] },
  image_edit: { available: true, models: [] }, text_to_video: { available: true, models: [m('c/vid-neg/text-to-video', ['prompt', 'negative_prompt'])] }, image_to_video: { available: true, models: [] },
}
g.fetch = async () => ({ ok: true, json: async () => ({ features }) })
await loadModels()
console.log(JSON.stringify({
  withNeg: hasNegative(modelOf('a/with-neg/text-to-image')), noNeg: hasNegative(modelOf('b/no-neg/text-to-image')),
  video: hasNegative(modelOf('c/vid-neg/text-to-video')), auto: hasNegative(modelOf('auto')), missing: hasNegative(undefined),
}))
