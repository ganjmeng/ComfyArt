// #393: the real chat ask router (renderAsk → OverQuote) + the real <Confirm/> modal. fetch is the real one: the
// test serves the page and routes /api/* to the real aiohttp bot routes, so a click reaches the backend's ask.
import { createRoot } from 'react-dom/client'
import { renderAsk } from '../../../src/ui/ChatMessage'
import { Confirm } from '../../../src/ui/Confirm'
import { chatsAtom, chatIdAtom } from '../../../src/bot'
import type { BotBlock } from '../../../src/bot'
import { setLang } from '../i18n_stub'

const g = globalThis as any
const root = createRoot(document.getElementById('root')!)
let n = 0
g.__render = (b: BotBlock, chatId: string, lng: 'zh' | 'en', theme: 'light' | 'dark') => {
  setLang(lng)
  document.documentElement.dataset.theme = theme
  chatsAtom.set([{ id: chatId } as any])
  chatIdAtom.set(chatId)
  n += 1
  root.render(
    <div id="wrap" key={n} className="ca-root" style={{ position: 'static', display: 'block', background: 'var(--ca-float)', color: 'var(--ca-text)', width: 380, minHeight: 60, padding: 16 }}>
      {renderAsk(b, 0)}
      <Confirm />
    </div>,
  )
}
g.__ready = true
