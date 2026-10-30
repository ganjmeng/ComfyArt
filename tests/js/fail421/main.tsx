// #421: failed generate_image row — main (wrong success) | ours (failed label). $0 mocks.
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { TOOL_LABELS } from '../../../src/bot'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
// TOOL_LABELS captured t() at import (en default); refresh so zh shots get 生成图像 etc.
TOOL_LABELS.generate_image = t('bot.generateImage')

const use = (id: string, name: string, input: any) => ({ type: 'tool_use', id, name, input })
const res = (id: string, name: string, text: string, status: string) => (
  { type: 'tool_result', id, name, status, text }
)
const failText = JSON.stringify({
  status: 'failed', error: 'WaveSpeed task failed', model: 'bytedance/seedream-v5.0-pro',
})
// Same locale on both panels — design HOLD on mixed zh/en body copy
const failBody = lang === 'en'
  ? 'Generation failed. Try another prompt.'
  : '生成失败，请换个提示词再试。'

// Simulate main before #421: payload failed but status stayed success → success-looking row
const mainMsg: any = {
  id: 'm', role: 'assistant', status: 'done', blocks: [
    { type: 'thinking', text: 'gen' },
    use('g1', 'mcp__comfyart__generate_image', { model: 'bytedance/seedream-v5.0-pro', prompt: 'cat' }),
    res('g1', 'mcp__comfyart__generate_image', failText, 'success'),
    { type: 'text', text: failBody },
  ],
}
// Fixed: status error → failed label
const oursMsg: any = {
  id: 'o', role: 'assistant', status: 'done', blocks: [
    { type: 'thinking', text: 'gen' },
    use('g2', 'mcp__comfyart__generate_image', { model: 'bytedance/seedream-v5.0-pro', prompt: 'cat' }),
    res('g2', 'mcp__comfyart__generate_image', failText, 'error'),
    { type: 'text', text: failBody },
  ],
}

createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ width: 840, padding: 16, display: 'flex', gap: 24, background: 'var(--ca-bg)' }}>
    <div style={{ flex: 1 }}>
      <div style={{ font: '12px/16px system-ui', opacity: .55, marginBottom: 8 }}>main</div>
      <div className="ca-chat"><div className="ca-chat__bot" id="main"><AssistantBlocks editor={null as any} m={mainMsg} /></div></div>
    </div>
    <div style={{ flex: 1 }}>
      <div style={{ font: '12px/16px system-ui', opacity: .55, marginBottom: 8 }}>ours</div>
      <div className="ca-chat"><div className="ca-chat__bot" id="ours"><AssistantBlocks editor={null as any} m={oursMsg} /></div></div>
    </div>
  </div>)
;(globalThis as any).__ready = true
