// #393: render the real RunStop stop cards; fetch is recorded, nothing leaves the page.
import { createRoot } from 'react-dom/client'
import { RunStop } from '../../../src/ui/ChatMessage'
import type { BotBlock } from '../../../src/bot'
import { setLang } from '../i18n_stub'

const g = globalThis as any
g.__calls = []
window.fetch = (async (url: any, init?: any) => {
  g.__calls.push({ url: String(url), method: init?.method ?? 'GET', body: init?.body ?? null })
  return new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })
}) as any
const root = createRoot(document.getElementById('root')!)
let n = 0
g.__render = (cards: BotBlock[], lng: 'zh' | 'en', theme: 'light' | 'dark') => {
  setLang(lng)
  document.documentElement.dataset.theme = theme
  n += 1
  root.render(
    <div id="wrap" key={n} className="ca-root" style={{ position: 'static', display: 'block', background: 'var(--ca-float)', color: 'var(--ca-text)', width: 380, padding: 16 }}>
      {cards.map((b, i) => <div key={i} style={{ marginBottom: 12 }}><RunStop b={b} latest /></div>)}
    </div>,
  )
}
g.__ready = true
