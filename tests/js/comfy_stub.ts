// In-memory stand-in for ./comfy: user files + the backend custom check.
export const files: Record<string, string> = {}
export const g = globalThis as any
export const listUserFiles = async (dir: string) => Object.keys(files).filter((p) => p.startsWith(dir + '/')).map((p) => p.slice(dir.length + 1))
export const readUserJson = async (p: string, d: unknown) => (p in files ? JSON.parse(files[p]) : d)
export const writeUserText = async (p: string, s: string) => { files[p] = s }
export const writeUserJson = async (p: string, v: unknown) => { files[p] = JSON.stringify(v) }
export const setWsHook = () => {}
export const api = async (url: string, init?: { body: string }) => (g.__server ? g.__server(url, init) : init ? g.__check(JSON.parse(init.body)) : { ok: false })
export const loadModelPaths = async () => ({})
// #130: render-path stand-ins; every call is recorded so a test can prove nothing was queued or uploaded.
export const calls: string[] = []
export type ImageRef = { filename: string; subfolder: string; type: string }
export const viewUrl = (r: ImageRef) => `/view?filename=${r.filename}`
export const uploadImage = async (_b: unknown, name: string) => { calls.push(`upload:${name}`); return { filename: name, subfolder: '', type: 'input' } }
export const queuePrompt = async (_g: unknown, runOn?: string) => { calls.push(`queue:${runOn}`); return 'p1' }
export const waitForImages = async () => { calls.push('wait'); return [] }
