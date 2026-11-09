import { canvasSrcAllowed, rasterLoadSrc, RASTER_FAIL_PNG, svgAsset, svgModelId, svgSpec, SVG_FLARE, SVG_SUNBURST } from '../../src/svgFile'

const placed = svgAsset({ filename: 'ws_abc_0.svg', svg_preview: 'ws_abc_0.preview.png', svg_state: 'transparent', svg_message: '背景是透明的' })
const failed = svgAsset({ filename: 'ws_abc_1.svg', svg_state: 'preview_failed', svg_message: '预览失败，原 SVG 仍可下载。' })

console.log(JSON.stringify({
  model: [svgModelId(undefined), svgModelId('openai/gpt-image-2.5-flare/text-to-image'), svgModelId('openai/gpt-image-2.6-sunburst/text-to-image'), svgModelId('openai/gpt-image-2.6-sunburst/edit')],
  spec: svgSpec({ svg: { output_format: 'svg', n: 4 } }),
  none: svgSpec({}),
  flare: SVG_FLARE,
  sun: SVG_SUNBURST,
  placed,
  failed,
  allowed: [
    canvasSrcAllowed(placed!.displaySrc),
    canvasSrcAllowed('/api/view?filename=ws_abc_0.svg&type=output'),
    canvasSrcAllowed(rasterLoadSrc('/api/view?filename=ws_abc_0.svg&type=output')),
  ],
  failPng: RASTER_FAIL_PNG.startsWith('data:image/png'),
  inline: placed!.inlineSvg,
}))
