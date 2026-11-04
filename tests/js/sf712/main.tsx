// #712: a run billed with no image -> the failed row + the relayed zh/en reason and amount. The kind/charged come
// from the mocked backend's real poll result (query string); the copy is the real wsErrorText. $0 mocks.
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { TOOL_LABELS } from '../../../src/bot'
import { wsErrorText } from '../../../src/wsErrors'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
TOOL_LABELS.generate_image = t('bot.generateImage')
const charged = q.get('charged') ? Number(q.get('charged')) : undefined
const msg = wsErrorText(q.get('kind'), charged) ?? 'unknown kind'
const model = q.get('model') || ''
const m: any = {
  id: 'f', role: 'assistant', status: 'done', blocks: [
    { type: 'tool_use', id: 'g1', name: 'mcp__comfyart__generate_image', input: { model, prompt: 'cat' } },
    { type: 'tool_result', id: 'g1', name: 'mcp__comfyart__generate_image', status: 'error',
      text: JSON.stringify({ status: 'failed', generation_succeeded: false, error: msg, user_message: msg, model }) },
    { type: 'text', text: msg },
  ],
}
createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ width: 520, padding: 16, background: 'var(--ca-bg)' }}>
    <div className="ca-chat"><div className="ca-chat__bot" id="ours" data-testid="ws-failure"><AssistantBlocks editor={null as any} m={m} /></div></div>
  </div>)
;(globalThis as any).__ready = true
