import { atom } from 'tldraw'
export const memoryAtom = atom<unknown[]>('memory', [])
export const remember = async () => []
export const toInputs = (x: unknown) => x
export const logMemory = async () => {}
export const OWNER_DEFAULT = 'local'
export const WORKSPACE_DEFAULT = 'local'
// re-export path: proactive imports OWNER from memoryStore
