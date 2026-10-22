import { createShapeId, type Editor, type TLImageShape } from 'tldraw'

import { promptHistory, uploadImage, viewUrl, type ImageRef } from './comfy'
import { wsBuilt } from './wavespeed'
import { GAP, placeMedia, registerPlacer, selectResults, spawnHolder, startJob, toMedia, type ErrorSink } from './jobs'
import { bakeMockup } from './mockupGl'
import { MOCKUP, placementOf, sourcesOf, type MockupShape } from './shapes/MockupShape'
import { annotated, editGraph } from './workflows'
import { t } from './i18n'

const BLEND_PROMPT = 'Make the printed design look naturally printed on the product: follow its folds, curvature, fabric or material texture and lighting. Keep the design content and position, the product and the background unchanged.'

export function createMockup(editor: Editor, shape: TLImageShape, onError: ErrorSink) {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return
  const { src, name } = asset.props
  const holder = spawnHolder(editor, shape)
  // cloud mode: upstream mockup-surface workflow (BiRefNet mask + DepthAnythingV2 depth) runs on WaveSpeed
  void startJob(editor, holder, Promise.resolve(wsBuilt({ feature: 'mockup_surface', image: annotated(src) })), { name: t('mockup.name', name), placer: 'mockup', extra: { photo: src } }, onError)
  return holder
}

registerPlacer('mockup', async (editor, holder, [depth], job) => {
  const hist = await promptHistory(job.id)
  const mask = hist?.outputs?.mask?.images?.[0] as ImageRef | undefined
  if (!mask) throw new Error('mockup surface has no mask')
  const { w, h } = holder.props as { w: number; h: number }
  const id = createShapeId()
  editor.run(() => {
    editor.deleteShape(holder.id)
    editor.createShape<MockupShape>({ id, type: MOCKUP, x: holder.x, y: holder.y, parentId: holder.parentId, props: { w, h, name: job.name, photo: String(job.extra?.photo), depth: depth.src, mask: viewUrl(mask) } })
  }, { history: 'ignore' })
  selectResults(editor, holder, [id])
})

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
