import { GIF_FLARE, clampFrameCount, clampFrameMs, gifModelId, gifSpec, placedFile } from '../../src/gifFile'

console.log(JSON.stringify({
  clamp: [clampFrameCount(1), clampFrameCount(99), clampFrameCount(undefined), clampFrameMs(5), clampFrameMs(undefined)],
  model: [gifModelId(undefined), gifModelId('openai/gpt-image-2.5-flare/text-to-image'), gifModelId('openai/gpt-image-2.6-sunburst/edit')],
  spec: gifSpec({ gif: { output_format: 'gif', frame_count: 4, frame_duration_ms: 40 } }),
  none: gifSpec({}),
  gif: placedFile('ws_abc_0.gif', 'poster', false),
  png: placedFile('ws_abc_0.png', 'poster', false),
  flare: GIF_FLARE,
}))
