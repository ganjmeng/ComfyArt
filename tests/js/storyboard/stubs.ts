// Browser-only pieces stubbed for the #168 storyboard flow (no DOM, no websocket, no network beyond the test server).
export function atom<T>(_n: string, v: T) { let x = v; return { get: () => x, set: (n: T) => { x = n } } }
export const useValue = (a: { get: () => unknown }) => a.get()
let n = 0
export const createShapeId = () => `shape:sb${++n}`
export const isShapeId = (s: string) => s.startsWith('shape:')
export const AssetRecordType = { createId: () => `asset:sb${++n}` }
// ui/Confirm: the cost dialog. Records what the user is asked, then presses OK.
export const asked: { desc: string; title: string }[] = []
export const confirmAtom = { get: () => null, set: (c: { desc: string; title: string; run: () => void } | null) => { if (c) { asked.push({ desc: c.desc, title: c.title }); c.run() } } }
export const readLocal = () => null
export const onComfyEvent = () => () => {}
export const keySettingsOpenAtom = atom('k', false)
export const keyStatusAtom = atom('s', null)
export const outOfCredit = () => false
export const refreshKeyStatus = async () => {}
export const GENERATOR = 'generator'
export const takePendingModel = () => null
export const withModel = () => {}
