// #167: drive the video editor's own edit functions (add, trim, split, reorder, remove, music, beat snap) and build the
// export graph. No model, upload, queue or network: fetch throws and the comfy stub records calls.
import { calls, g } from './comfy_stub'
import { appendClip, clipLength, freshEdit, layout, moveClip, removeClip, splitAt, type Edit } from '../../src/videoEdit'
import { snap } from '../../src/beats'
import { timelineGraph } from '../../src/videoRender'

const net: string[] = []
g.location = { origin: 'http://127.0.0.1:8188' }
g.fetch = async (url: string) => { net.push(String(url)); throw new Error('network disabled in tests') }
const v = (n: string) => `/view?filename=${n}&type=input`

let edit: Edit = freshEdit(v('red.mp4'), 2)
edit = appendClip(edit, v('green.mp4'), 2)
edit = appendClip(edit, v('blue.mp4'), 2)
const added = { n: edit.clips.length, total: layout(edit).total }
// trim like the timeline handles do: green keeps source 0.5..1.5
edit = { ...edit, clips: edit.clips.map((c, i) => (i === 1 ? { ...c, start: 0.5, end: 1.5 } : c)) }
const trimmed = { len: clipLength(edit.clips[1]), total: layout(edit).total }
// reorder: blue to the front -> blue, red, green
edit = moveClip(edit, 2, 0)
const order = edit.clips.map((c) => c.src)
const outOfRange = moveClip(edit, 0, 9) === edit
// split red (at 2.0..4.0) at 3.0 then remove the second half -> blue 2, red 1, green 1
const split = splitAt(edit, 3)!
const splitN = split.clips.length
edit = removeClip(split, 2)
const noSplitEdge = splitAt(edit, 0.05) === null
// music: song offset snapped to the nearest beat within 0.2 s
const beats = [0, 0.5, 1.0, 1.5]
const snapped = snap(1.07, beats, 0.2)
const unsnapped = snap(1.3, beats, 0.1)
edit = { ...edit, music: { src: v('song.wav'), name: 'song', start: snapped, volume: 0.8 } }
const built = await timelineGraph(edit, 64, 48)
console.log(JSON.stringify({ added, trimmed, order, outOfRange, splitN, noSplitEdge, snapped, unsnapped, total: layout(edit).total, built, calls, net }))
