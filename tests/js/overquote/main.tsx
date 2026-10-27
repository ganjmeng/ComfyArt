// #393: the real chat ask router (renderAsk → OverQuote) + the real <Confirm/> modal. fetch is the real one: the
// test serves the page and routes /api/* to the real aiohttp bot routes, so a click reaches the backend's ask.
import { createRoot } from 'react-dom/client'
import { renderAsk } from '../../../src/ui/ChatMessage'
import { Confirm, confirmAtom } from '../../../src/ui/Confirm'
import { Modal } from '../../../src/ui/Modal'
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
// EL guard (#393): an ordinary confirm, the exact shape MemoryDialog's delete uses (no over-quote props), and a plain
// <Modal> with its defaults. window.__log records which callback fired.
g.__log = []
g.__confirm = (lng: 'zh' | 'en', theme: 'light' | 'dark') => {
  setLang(lng)
  document.documentElement.dataset.theme = theme
  g.__log = []
  n += 1
  root.render(<div key={n} className="ca-root"><Confirm /></div>)
  confirmAtom.set({ title: 'Delete this memory?', desc: 'It will be removed: likes cats', ok: 'Delete', danger: true,
    run: () => g.__log.push('run'), cancel: () => g.__log.push('cancel') })
}
g.__modal = () => {
  g.__log = []
  n += 1
  root.render(<div key={n} className="ca-root"><Modal title="Rename" onClose={() => g.__log.push('close')}><div className="ca-rename__body"><div>body</div></div></Modal></div>)
}
g.__ready = true
