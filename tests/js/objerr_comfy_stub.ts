// ./comfy stand-in for object_errors.ts: every request answers with the body the test sets, nothing leaves the process.
export const g = globalThis as any
export const api = async (_url: string, _init?: unknown) => ({ ok: false, status: 500, json: async () => g.__body })
export const uploadImage = async () => ({ filename: 'x.png', subfolder: '', type: 'input' })
export const viewUrl = () => '/view?filename=x.png'
export const queuePrompt = async () => 'p1'
export const waitForImages = async () => []
