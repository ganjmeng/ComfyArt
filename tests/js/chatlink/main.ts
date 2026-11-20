import { ChatReadGate, chatReadPath, readChatLink } from '../../../src/chatLink.ts'

const absent = readChatLink(new URLSearchParams('project=quote-card-fc8d1a79'))
if (absent.kind !== 'absent') throw new Error('project without chat must stay absent')

const invalid = readChatLink(new URLSearchParams('chat=8c140643962742f993e078febaf4268a'))
if (invalid.kind !== 'invalid') throw new Error('chat without project must be an invalid link')

const open = readChatLink(new URLSearchParams('project=quote-card-fc8d1a79&chat=8c140643962742f993e078febaf4268a'))
if (open.kind !== 'open' || open.project !== 'quote-card-fc8d1a79' || open.chat !== '8c140643962742f993e078febaf4268a') {
  throw new Error('project and chat must open that pair')
}

const path = chatReadPath('proj b', 'chat/1')
if (path !== '/comfyart/bot/chats/chat%2F1?project=proj%20b') throw new Error('read path ' + path)

const gate = new ChatReadGate()
const first = gate.begin()
const second = gate.begin()
if (gate.isCurrent(first)) throw new Error('an older read must be discarded')
if (!gate.isCurrent(second)) throw new Error('the latest read must stay current')
gate.invalidate()
if (gate.isCurrent(second)) throw new Error('a project change must discard the in-flight read')

console.log('ok')
