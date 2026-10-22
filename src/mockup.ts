import { createShapeId, type Editor, type TLImageShape } from 'tldraw'

import { uploadImage, viewUrl } from './comfy'
import { GAP, placeMedia, spawnHolder, startJob, toMedia, type ErrorSink } from './jobs'
import { bakeMockup } from './mockupGl'
import { MOCKUP, placementOf, sourcesOf, type MockupShape } from './shapes/MockupShape'
import { annotated, editGraph } from './workflows'
import { t } from './i18n'

const BLEND_PROMPT = 'Make the printed design look naturally printed on the product: follow its folds, curvature, fabric or material texture and lighting. Keep the design content and position, the product and the background unchanged.'

async function solidPng(color: string, name: string): Promise<string> {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 4
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = color
  ctx.fillRect(0, 0, 4, 4)
  const blob = await new Promise<Blob>((ok, fail) => canvas.toBlob((b) => (b ? ok(b) : fail(new Error('canvas export failed'))), 'image/png'))
  return viewUrl(await uploadImage(blob, name))
}

// The local depth/surface model is gone: the mockup starts on a flat surface (uniform depth, full mask).
export function createMockup(editor: Editor, shape: TLImageShape, onError: ErrorSink) {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return
  const { src, name } = asset.props
  const b = editor.getShapePageBounds(shape)!
  const id = createShapeId()
  void (async () => {
    const [depth, mask] = await Promise.all([solidPng('#808080', 'mockup-flat-depth.png'), solidPng('#ffffff', 'mockup-full-mask.png')])
    editor.createShape<MockupShape>({ id, type: MOCKUP, x: b.maxX + GAP, y: b.y, props: { w: b.w, h: b.h, name: t('mockup.name', name), photo: src, depth, mask } })
    editor.select(id)
  })().catch((e: unknown) => onError(e instanceof Error ? e.message : String(e)))
  return id
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
