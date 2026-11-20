import { ChatReadGate, InitEpoch, chatReadPath, readChatLink, settleBotInit } from '../../../src/chatLink.ts'

const absent = readChatLink(new URLSearchParams('project=quote-card-fc8d1a79'))
if (absent.kind !== 'absent') throw new Error('project without chat must stay absent')
const blankChat = readChatLink(new URLSearchParams('project=quote-card-fc8d1a79&chat='))
if (blankChat.kind !== 'absent') throw new Error('an empty chat param must not select a chat')

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

const link = (chat: string) => readChatLink(new URLSearchParams(`project=p&chat=${chat}`))
const absentLink = readChatLink(new URLSearchParams('project=p'))

function finish(epoch: InitEpoch, id: number, captured: ReturnType<typeof readChatLink>, live: ReturnType<typeof readChatLink>, projectId: string, opens: string[]) {
  const chat = settleBotInit({
    epoch: id,
    currentEpoch: epoch.current(),
    stale: false,
    captured,
    live,
    projectId,
  })
  if (chat) opens.push(chat)
}

const afterCleanup: string[] = []
const epoch = new InitEpoch()
const old = epoch.begin()
epoch.cancel()
finish(epoch, old, link('A'), link('A'), 'p', afterCleanup)
if (afterCleanup.length !== 0) throw new Error('cleanup then late init reopened ' + afterCleanup.join(','))
console.log('ok cleanup-then-finish')

const switched: string[] = []
const same = new InitEpoch()
const initA = same.begin()
same.cancel()
const initB = same.begin()
finish(same, initB, link('B'), link('B'), 'p', switched)
finish(same, initA, link('A'), link('A'), 'p', switched)
if (switched.join(',') !== 'B') throw new Error('A finishing last reopened ' + switched.join(','))
console.log('ok A-finishes-after-B')

const noChat: string[] = []
const plain = new InitEpoch()
const init = plain.begin()
finish(plain, init, absentLink, absentLink, 'p', noChat)
if (noChat.length !== 0) throw new Error('absent chat param opened ' + noChat.join(','))
console.log('ok no-chat')

const moved: string[] = []
const url = new InitEpoch()
const initUrl = url.begin()
finish(url, initUrl, link('A'), link('B'), 'p', moved)
if (moved.length !== 0) throw new Error('stale URL intent opened ' + moved.join(','))
console.log('ok url-A-to-B')

console.log('ok')
