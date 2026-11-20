import { chatIdAtom, startBot } from '../../../src/bot.ts'
import { chatReads, finishRefresh, gates, resetChain, setNoteSelection } from './stubs/comfy.ts'

const seen: Array<string | null> = []

function selected(): string | null {
  return chatIdAtom.get()
}

function mark(where: string) {
  const id = selected()
  seen.push(id)
  console.log(`trace mark ${where} selected=${id ?? 'null'} reads=${chatReads.join('|') || 'none'}`)
}

setNoteSelection((where: string) => {
  const id = selected()
  seen.push(id)
  console.log(`trace ${where} selected=${id ?? 'null'}`)
})

function setUrl(chat: string | null) {
  const query = chat ? `project=p&chat=${chat}` : 'project=p'
  ;(globalThis as { location: { href: string } }).location = { href: `http://127.0.0.1/comfyart/?${query}` }
}

function beginCase() {
  seen.length = 0
  chatIdAtom.set(null)
  resetChain()
}

setUrl('A')
beginCase()
mark('cleanup-before-start')
const stopOnly = startBot('p', () => false)
mark('cleanup-after-start-before-release')
const onlySync = gates.length
stopOnly()
mark('cleanup-after-cleanup-before-release')
await finishRefresh(0, onlySync)
mark('cleanup-after-old-refresh')
if (chatReads.length !== 0) throw new Error('cleanup then refresh issued ' + chatReads.join(','))
if (selected() !== null) throw new Error('cleanup completion selected ' + selected())
if (seen.some((id) => id === 'A')) throw new Error('cancelled init selected A')
console.log('ok chain-cleanup-then-refresh')

beginCase()
setUrl('A')
mark('switch-before-A')
const a0 = gates.length
const stopA = startBot('p', () => false)
const a1 = gates.length
mark('switch-after-A-start')
stopA()
mark('switch-after-A-cleanup')
setUrl('B')
const b0 = gates.length
const stopB = startBot('p', () => false)
const b1 = gates.length
mark('switch-after-B-start')
await finishRefresh(b0, b1)
mark('switch-after-B-refresh')
if (selected() !== 'B') throw new Error('after B refresh selected ' + selected())
await finishRefresh(a0, a1)
mark('switch-after-A-finish')
stopB()
mark('switch-after-B-cleanup')
if (selected() !== 'B') throw new Error('after A finished last selected ' + selected())
if (seen.some((id) => id === 'A')) throw new Error('old init A was selected; trace saw A')
if (chatReads.length !== 1 || !chatReads[0].includes('/comfyart/bot/chats/B?project=p')) {
  throw new Error('A finishing last changed the chat read: ' + chatReads.join(','))
}
if (chatReads.some((path) => path.includes('/comfyart/bot/chats/A?'))) throw new Error('old init issued a read for A')
console.log('ok chain-A-finishes-after-B')

beginCase()
setUrl(null)
mark('no-chat-before')
const n0 = gates.length
const stopNone = startBot('p', () => false)
const n1 = gates.length
await finishRefresh(n0, n1)
mark('no-chat-after-refresh')
stopNone()
mark('no-chat-after-cleanup')
if (chatReads.length !== 0) throw new Error('absent chat param issued ' + chatReads.join(','))
if (selected() !== null) throw new Error('absent chat param selected ' + selected())
console.log('ok chain-no-chat')

console.log('ok')
