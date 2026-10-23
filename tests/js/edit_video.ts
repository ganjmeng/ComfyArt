// #130: edit_video builds one local ComfyArtTimeline graph (24 fps, mp4) and touches no model, upload, queue or network.
import { calls, g } from './comfy_stub'
import { timelineGraph } from '../../src/videoRender'
import type { Edit } from '../../src/videoEdit'

const net: string[] = []
g.location = { origin: 'http://127.0.0.1:8188' }
g.fetch = async (url: string) => { net.push(String(url)); throw new Error('network disabled in tests') }
const edit: Edit = {
  clips: [
    { src: '/view?filename=a.mp4&type=input', start: 1, end: 4, speed: 1, volume: 1 },
    { src: '/view?filename=b.mp4&type=input', start: 0, end: 4, speed: 2, volume: 0.5 },
  ],
  transitions: [{ type: 'fade', duration: 0.5 }],
  subtitles: [],
  music: { src: '/view?filename=song.mp3&type=input', name: 'song', start: 10, volume: 0.3 },
}
const built = await timelineGraph(edit, 1280, 720)
const hard = await timelineGraph({ ...edit, transitions: [{ type: 'none', duration: 0.5 }], music: null }, 640, 360)
console.log(JSON.stringify({ built, hard, calls, net }))
