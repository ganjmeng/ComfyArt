import tracer from 'imagetracerjs'
import type { Editor, TLImageShape } from 'tldraw'

import { loadImage } from './adjust'
import { uploadImage, viewUrl } from './comfy'
import { rasterLoadSrc, RASTER_FAIL_PNG } from './svgFile'
import { GAP, placeMedia } from './jobs'
import { t } from './i18n'

const MAX_SIDE = 1024
const RASTER_STEP = 512
const RASTER_MAX = 4096
const rasters = new Map<string, Promise<string>>()
const OPTIONS = { numberofcolors: 16, ltres: 1, qtres: 1, pathomit: 8, colorquantcycles: 3, roundcoords: 1, viewbox: true }

export function svgRaster(src: string, w: number, h: number, scale: number): Promise<string> {
  const px = Math.min(RASTER_MAX, RASTER_STEP * 2 ** Math.max(0, Math.ceil(Math.log2(Math.max(w, h) * scale / RASTER_STEP))))
  const target = rasterLoadSrc(src)
  const key = `${target}|${px}`
  if (!rasters.has(key)) {
    // #826: load the server PNG (or another non-SVG source). Failure is a PNG, never the SVG URL.
    rasters.set(key, loadImage(target).then((img) => {
      const k = px / Math.max(w, h)
      const c = document.createElement('canvas')
      c.width = Math.round(w * k)
      c.height = Math.round(h * k)
      c.getContext('2d')!.drawImage(img, 0, 0, c.width, c.height)
      return new Promise<string>((resolve) => c.toBlob((b) => resolve(b ? URL.createObjectURL(b) : RASTER_FAIL_PNG), 'image/png'))
    }).catch(() => RASTER_FAIL_PNG))
  }
  return rasters.get(key)!
}

export async function vectorize(editor: Editor, shape: TLImageShape) {
  const asset = shape.props.assetId ? editor.getAsset(shape.props.assetId) : null
  if (asset?.type !== 'image' || !asset.props.src) return
  const img = await loadImage(asset.props.src)
  const k = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight))
  const c = document.createElement('canvas')
  c.width = Math.round(img.naturalWidth * k)
  c.height = Math.round(img.naturalHeight * k)
  const ctx = c.getContext('2d')!
  ctx.drawImage(img, 0, 0, c.width, c.height)
  const svg = tracer.imagedataToSVG(ctx.getImageData(0, 0, c.width, c.height), OPTIONS)
  const name = `${(asset.props.name || 'image').replace(/\.\w+$/, '')}.svg`
  const ref = await uploadImage(new Blob([svg], { type: 'image/svg+xml' }), name)
  const b = editor.getShapePageBounds(shape)!
  const id = placeMedia(editor, { ref, src: viewUrl(ref), w: c.width, h: c.height, kind: 'image' }, t('vectorize.vector', asset.props.name), b.maxX + GAP, b.y, b.w)
  editor.select(id)
  return id
}
