import { type Editor, type TLImageShape } from 'tldraw'

import { uploadImage, viewUrl } from './comfy'
import { wsBuilt } from './wavespeed'
import { GAP, placeMedia, spawnHolder, startJob, toMedia, type ErrorSink } from './jobs'
import { bakeMockup } from './mockupGl'
import { placementOf, sourcesOf, type MockupShape } from './shapes/MockupShape'
import { annotated, editGraph } from './workflows'
import { t } from './i18n'

const MOCKUP_MODEL = 'alibaba/qwen-image-3.0/edit'
const MOCKUP_PROMPT = 'Turn this image into a realistic product mockup sticker: printed naturally on a product surface, following its curvature, material texture and lighting.'
const BLEND_PROMPT = 'Make the printed design look naturally printed on the product: follow its folds, curvature, fabric or material texture and lighting. Keep the design content and position, the product and the background unchanged.'

export function createMockup(editor: Editor, shape: TLImageShape, onError: ErrorSink) {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return
  const { src, name, w, h } = asset.props
  const holder = spawnHolder(editor, shape)
  // cloud mode: the local birefnet surface workflow is replaced by WaveSpeed qwen-image-3.0 edit
  void startJob(editor, holder, Promise.resolve(wsBuilt({ feature: 'image_edit', model: MOCKUP_MODEL, image: annotated(src), prompt: MOCKUP_PROMPT, width: w, height: h })), { name: t('mockup.name', name) }, onError)
  return holder
}

async function bakedRef(shape: MockupShape) {
  return uploadImage(await bakeMockup(sourcesOf(shape.props), placementOf(shape.props)), `${shape.props.name || 'mockup'}.png`)
}

export async function bakeToImage(editor: Editor, shape: MockupShape) {
  const media = await toMedia(await bakedRef(shape), 'image')
  const b = editor.getShapePageBounds(shape)!
  const id = placeMedia(editor, media, shape.props.name, b.maxX + GAP, b.y, b.w)
  editor.select(id)
  return id
}

export function aiBlend(editor: Editor, shape: MockupShape, onError: ErrorSink) {
  const holder = spawnHolder(editor, shape)
  void startJob(editor, holder, (async () => editGraph(annotated(viewUrl(await bakedRef(shape))), BLEND_PROMPT))(), { name: t('mockup.blendName', shape.props.name) }, onError)
  return holder
}
