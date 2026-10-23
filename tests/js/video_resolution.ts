// #159: a video card shows, writes back, quotes and submits one tier; '1K' never rides along on a video.
import { VIDEO_RESOLUTIONS, videoResolution } from '../../src/genOptions'

const seed = ['480p', '720p', '1080p', '4k']
console.log(JSON.stringify({
  list: VIDEO_RESOLUTIONS,
  unknownModel: ['', '1K', '2K', 'custom', '768p'].map((r) => videoResolution(r)),
  seedance: ['', '1K', '768p', '720p', '4k'].map((r) => videoResolution(r, seed)),
  seedanceDefault: videoResolution('1K', seed, '720p'),
  badDefault: videoResolution('1K', seed, '1K'),
}))
