/** #978 harness: the modules agent.ts imports that are not under test. The real src/skills.ts and
 *  src/agent.ts sendToAgent run; only the boundary below is replaced so the exact send body can be asserted. */
import { atom } from 'tldraw'

export const settingsAtom = atom<Record<string, unknown>>('settings', { 'memory-enabled': true })
export const botEnabledAtom = atom<boolean | null>('bot enabled', true)
export const sent: Record<string, unknown>[] = []
export async function sendMessage(input: Record<string, unknown>) { sent.push(structuredClone(input)) }
export async function logDirect() {}

export const capRefs = (refs: unknown[]) => refs
export function createGenerator() { return 'shape:generator' }
export async function generate() { return [] }
export const genInfoOf = () => null
export const nearestRatio = (ratio: number) => ratio

export const fileSrc = () => null
export const placeMedia = () => 'shape:media'
export async function toMedia() { return { w: 1, h: 1, ref: {}, name: '' } }

export const describeItem = () => ''
export const itemImages = () => []
export const linkedKit = () => null

export const ask = async () => ''
export const ocrLines = async () => []
export const parseJson = (raw: string) => { try { return JSON.parse(raw) } catch { return null } }
export const transcribeFile = async () => ''

export const api = async () => ({ ok: false, json: async () => ({}) })
export const uploadImage = async () => ({ filename: 'preset978.png', subfolder: '', type: 'input' })
export const viewUrl = (ref: { filename?: string } | undefined) => `/view?filename=${ref?.filename ?? 'preset978.png'}`
export const listUserFiles = async () => [] as string[]
export const readUserText = async () => null
export const writeUserText = async () => {}
export const deleteUserFile = async () => {}

export const memoryPrompt = () => ''
export const refFrameContents = () => ({ media: [], notes: [] })
export const refFrameOf = () => null
export const refLinkedOf = () => false
export const formatCanvasSnapshot = () => ({ text: '' })
export const packUnifiedContext = () => ({ snapshot: '', memoryPrompt: '' })
export const directSettings = () => ({})
export const modelOf = () => null
export const commentTarget = () => null

export const AUDIO = 'ca-audio'
export const AUDIO_SIZE = [320, 180]
export const GENERATOR = 'ca-generator'
export const COMMENT = 'ca-comment'
