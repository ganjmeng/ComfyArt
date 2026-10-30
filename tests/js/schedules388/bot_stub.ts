import { atom } from 'tldraw'
export const chatIdAtom = atom<string | null>('chat id', null)
export const chatsAtom = atom<{ id: string; busy?: boolean }[]>('chats', [])
export async function openChat(_id: string | null) {}
