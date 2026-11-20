import { startBot } from '../../../src/bot.ts'
import { chatReads, finishRefresh, gates, resetChain } from './stubs/comfy.ts'

function setUrl(chat: string | null) {
  const query = chat ? `project=p&chat=${chat}` : 'project=p'
  ;(globalThis as { location: { href: string } }).location = { href: `http://127.0.0.1/comfyart/?${query}` }
}

setUrl('A')
resetChain()
const stopOnly = startBot('p', () => false)
const onlySync = gates.length
stopOnly()
await finishRefresh(0, onlySync)
if (chatReads.length !== 0) throw new Error('cleanup then refresh issued ' + chatReads.join(','))
console.log('ok chain-cleanup-then-refresh')

resetChain()
setUrl('A')
const a0 = gates.length
const stopA = startBot('p', () => false)
const a1 = gates.length
stopA()
setUrl('B')
const b0 = gates.length
const stopB = startBot('p', () => false)
const b1 = gates.length
await finishRefresh(b0, b1)
await finishRefresh(a0, a1)
stopB()
if (chatReads.length !== 1 || !chatReads[0].includes('/comfyart/bot/chats/B?project=p')) {
  throw new Error('A finishing last changed the chat read: ' + chatReads.join(','))
}
if (chatReads.some((path) => path.includes('/comfyart/bot/chats/A?'))) throw new Error('old init issued a read for A')
console.log('ok chain-A-finishes-after-B')

resetChain()
setUrl(null)
const n0 = gates.length
const stopNone = startBot('p', () => false)
const n1 = gates.length
await finishRefresh(n0, n1)
stopNone()
if (chatReads.length !== 0) throw new Error('absent chat param issued ' + chatReads.join(','))
console.log('ok chain-no-chat')

console.log('ok')
