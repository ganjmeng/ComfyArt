// #509 PR3: extend / videoUpscale / videoCutout / model3d tag shape (source mutations guard drift).
import { CUSTOM_MODEL3D } from '../../src/customWorkflows'
import { videoTargetResolution } from '../../src/videoGraphs'

/** Mirrors actions.ts video tagging + assetGen modelGraph custom branch. */
function videoInputs(kind: 'extend' | 'videoUpscale' | 'videoCutout', video = 'clip.mp4 [input]'): Record<string, unknown> {
  if (kind === 'extend') return { feature: 'extend_video', custom: 'extend', video, prompt: 'Continue the shot naturally.', duration: 5 }
  if (kind === 'videoUpscale') return { feature: 'upscale_video', custom: 'videoUpscale', video, params: { target_resolution: videoTargetResolution(2560) } }
  return { feature: 'remove_video_background', custom: 'videoCutout', video }
}

function model3dInputs(custom: boolean, image = 'a.png [input]'): Record<string, unknown> {
  if (custom) return { feature: 'image_to_3d', custom: 'model3d', model: CUSTOM_MODEL3D, image }
  return { feature: 'image_to_3d', image }
}

const main = () => {
  console.log(JSON.stringify({
    extend: videoInputs('extend'),
    videoUpscale: videoInputs('videoUpscale'),
    videoCutout: videoInputs('videoCutout'),
    model3dBuiltIn: model3dInputs(false),
    model3dCustom: model3dInputs(true),
    customModel3dId: CUSTOM_MODEL3D,
    target1080: videoTargetResolution(1920),
    target2k: videoTargetResolution(2560),
    target4k: videoTargetResolution(3840),
    targetBelow1080: videoTargetResolution(1280),
  }))
}
main()
