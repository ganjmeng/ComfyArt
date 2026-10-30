// #420: canvas tools on process rail — main (broken off-rail Steps) | ours (continuous spine + failed on rail).
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { TOOL_LABELS } from '../../../src/bot'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
TOOL_LABELS.get_canvas = t('bot.viewCanvas')
TOOL_LABELS.create_frame = t('bot.createArtboard')
TOOL_LABELS.add_text = t('bot.addText')

const use = (id: string, name: string, input: any = {}) => ({ type: 'tool_use', id, name, input })
const res = (id: string, name: string, text: string, status: string) => (
  { type: 'tool_result', id, name, status, text }
)

const think = { type: 'thinking', text: lang === 'en' ? 'lay out the board' : '先摆画板' }
const reply = { type: 'text', text: lang === 'en' ? 'Frame and text are ready.' : '画板和文字好了。' }

// Shared successful canvas steps + one failed add_text
const canvasBlocks = (prefix: string) => [
  think,
  use(`${prefix}1`, 'mcp__comfyart__get_canvas', {}),
  res(`${prefix}1`, 'mcp__comfyart__get_canvas', '{"pages":1}', 'success'),
  use(`${prefix}2`, 'mcp__comfyart__create_frame', { name: 'A' }),
  res(`${prefix}2`, 'mcp__comfyart__create_frame', '{"id":"shape:f1"}', 'success'),
  use(`${prefix}3`, 'mcp__comfyart__add_text', { text: 'Hi' }),
  res(`${prefix}3`, 'mcp__comfyart__add_text', 'no shape Hi', 'error'),
  reply,
]

// main: force the pre-#420 path by rendering the same message through a shim that
// strips processKindOf→tool (simulate old null) — we approximate by showing the
// broken layout via data attribute and a note; actual main build uses current
// ChatMessage without the catch-all. For SBS we re-implement the broken layout
// as static HTML for "main", and live AssistantBlocks for "ours".
function MainBroken() {
  const L = TOOL_LABELS
  const fail = t('chatMessage.failed')
  const thought = t('chatMessage.thought')
  return (
    <div className="ca-chat__bot" id="main" data-testid="main-panel">
      {/* lone thought — no continuous rail into tools */}
      <div className="ca-chat__tool ca-chat__thought">
        <button type="button" className="ca-chat__step">
          <span className="ca-chat__thinkicon"><span className="ca-icon">◇</span></span>
          <span className="ca-chat__thinklabel">{thought}</span>
        </button>
      </div>
      {/* off-rail tool steps — breaks the vertical line */}
      <div className="ca-chat__tool">
        <button type="button" className="ca-chat__step">
          <span className="ca-icon">✓</span>
          <span>{L.get_canvas}</span>
          <span className="ca-chat__status">0.1s</span>
        </button>
      </div>
      <div className="ca-chat__tool">
        <button type="button" className="ca-chat__step">
          <span className="ca-icon">✓</span>
          <span>{L.create_frame}</span>
          <span className="ca-chat__status">0.2s</span>
        </button>
      </div>
      <div className="ca-chat__tool" data-error={true}>
        <button type="button" className="ca-chat__step">
          <span className="ca-icon">✕</span>
          <span>{L.add_text}</span>
          <span className="ca-chat__status">{fail}</span>
        </button>
      </div>
      <div>{reply.text}</div>
    </div>
  )
}

const oursMsg: any = {
  id: 'o', role: 'assistant', status: 'done', blocks: canvasBlocks('o'),
}

createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ width: 900, padding: 16, display: 'flex', gap: 24, background: 'var(--ca-bg)' }}>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ font: '12px/16px system-ui', opacity: .55, marginBottom: 8 }}>main</div>
      <div className="ca-chat"><MainBroken /></div>
    </div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ font: '12px/16px system-ui', opacity: .55, marginBottom: 8 }}>ours</div>
      <div className="ca-chat"><div className="ca-chat__bot" id="ours"><AssistantBlocks editor={null as any} m={oursMsg} /></div></div>
    </div>
  </div>)
;(globalThis as any).__ready = true
