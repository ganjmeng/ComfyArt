import './polyfill'
import { files } from '../../../src/comfy'
import { draftItem, libraryAtom, loadLibrary, saveDraft, updateLibrary, type LibraryItem } from '../../../src/library'

const FILE = 'comfyart/library.json'
const heard: unknown[] = []
const probe = new BroadcastChannel('comfyart-library')
probe.onmessage = (ev) => { heard.push(ev.data) }

function item(id: string, name: string): LibraryItem {
  return { id, kind: 'brand', name, description: '', images: [], colors: [], fonts: [] }
}
const names = (list: LibraryItem[]) => list.map((x) => x.name)
function disk(): LibraryItem[] {
  return JSON.parse(files[FILE] || '[]')
}

files[FILE] = JSON.stringify([item('a', 'Alpha')])
libraryAtom.set([])
const merged = await updateLibrary((list) => [...list, item('b', 'Beta')])
if (names(merged).join() !== 'Alpha,Beta') throw new Error(`merge dropped a saved item: ${names(merged).join()}`)
if (names(disk()).join() !== 'Alpha,Beta') throw new Error(`disk lost Alpha: ${names(disk()).join()}`)
if (names(libraryAtom.get()).join() !== 'Alpha,Beta') throw new Error(`atom lost Alpha: ${names(libraryAtom.get()).join()}`)
if (heard.join() !== 'changed') throw new Error(`broadcast ${JSON.stringify(heard)}`)

files[FILE] = JSON.stringify([item('a', 'Alpha')])
draftItem(null)
await loadLibrary()
draftItem(item('a', 'Alpha edited'))
if (libraryAtom.get()[0]?.name !== 'Alpha edited') throw new Error('draft did not overlay the open item')
files[FILE] = JSON.stringify([item('a', 'Alpha'), item('b', 'Beta')])
await loadLibrary()
if (names(libraryAtom.get()).join() !== 'Alpha edited,Beta') throw new Error(`reload clobbered the draft: ${names(libraryAtom.get()).join()}`)
await saveDraft()
if (names(disk()).join() !== 'Alpha edited,Beta') throw new Error(`saveDraft overwrote the other tab: ${names(disk()).join()}`)
if (names(libraryAtom.get()).join() !== 'Alpha edited,Beta') throw new Error(`atom after save ${names(libraryAtom.get()).join()}`)

probe.close()
console.log(JSON.stringify({
  merged: names(merged),
  draftKept: names(disk()),
  broadcasts: heard.length,
}))
