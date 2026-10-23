// In-memory stand-in for ./comfy: user files + the backend custom check.
export const files: Record<string, string> = {}
export const g = globalThis as any
export const listUserFiles = async (dir: string) => Object.keys(files).filter((p) => p.startsWith(dir + '/')).map((p) => p.slice(dir.length + 1))
export const readUserJson = async (p: string, d: unknown) => (p in files ? JSON.parse(files[p]) : d)
export const writeUserText = async (p: string, s: string) => { files[p] = s }
export const writeUserJson = async (p: string, v: unknown) => { files[p] = JSON.stringify(v) }
export const setWsHook = () => {}
export const api = async (_url: string, init?: { body: string }) => (init ? g.__check(JSON.parse(init.body)) : { ok: false })
export const loadModelPaths = async () => ({})
