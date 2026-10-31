// #513 step1 / #528: generate refs+base, motion, lipsync tag shape (source mutations guard drift).
import { CUSTOM_GENERATE } from '../../src/customWorkflows'
import { CUSTOM_ACTIONS, MARKERS } from '../../src/customMarkers'

function motionInputs(image = 'char.png [input]', video = 'motion.mp4 [input]'): Record<string, unknown> {
  return { feature: 'motion_control', custom: 'motion', image, video, prompt: 'The character performs the motion of the video.', duration: 5, ratio: '16:9' }
}
function lipsyncInputs(image = 'face.png [input]', audio = 'speech.mp3 [input]'): Record<string, unknown> {
  return { feature: 'lip_sync', custom: 'lipsync', image, audio, prompt: 'The person talks naturally to the camera.', duration: 4, ratio: '1:1' }
}
function generateCustom(opts: { image?: string; image2?: string; base?: string; strength?: number } = {}): Record<string, unknown> {
  return {
    feature: 'text_to_image', custom: 'generate', model: CUSTOM_GENERATE,
    prompt: 'a cat', width: 1024, height: 1024,
    image: opts.image, image2: opts.image2, images: opts.image2 ? [opts.image2] : undefined,
    base: opts.base, strength: opts.strength, png: false,
  }
}

const main = () => {
  console.log(JSON.stringify({
    motion: motionInputs(),
    lipsync: lipsyncInputs(),
    generatePlain: generateCustom(),
    generateRefs: generateCustom({ image: 'a.png [input]', image2: 'b.png [input]' }),
    generateBase: generateCustom({ base: 'base.png [input]', strength: 0.65 }),
    customGenerateId: CUSTOM_GENERATE,
    hasMotion: CUSTOM_ACTIONS.some((a) => a.id === 'motion'),
    hasLipsync: CUSTOM_ACTIONS.some((a) => a.id === 'lipsync'),
    generateOptional: CUSTOM_ACTIONS.find((a) => a.id === 'generate')!.optional,
    markerIds: MARKERS.map((m) => m.id),
  }))
}
main()
