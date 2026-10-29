// #437: a finished search + generation turn through the real AssistantBlocks; $0 mocks, no network.
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { setLang } from '../i18n_stub'

const q = new URLSearchParams(location.search)
setLang(q.get('lang') === 'en' ? 'en' : 'zh')
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'
const use = (id: string, name: string, input: any) => ({ type: 'tool_use', id, name, input })
const res = (id: string, name: string, text: string) => ({ type: 'tool_result', id, name, status: 'success', text })
const m: any = { id: 'a1', role: 'assistant', status: 'done', blocks: [
  use('g1', 'mcp__comfyart__generate_image', { model: 'GPT Image Flare', prompt: 'apple' }), res('g1', 'mcp__comfyart__generate_image', '{"prompt_id":"p1"}'),
  { type: 'text', text: 'ok' },
] }
const s: any = { id: 'a2', role: 'assistant', status: 'done', blocks: [
  { type: 'thinking', text: 'Search.' },
  use('w1', 'WebSearch', { query: 'fuji', num_results: 1 }), res('w1', 'WebSearch', '{"results":[{"url":"https://www.google.com/search?q=fuji"}]}'),
  { type: 'text', text: 'done' },
] }
createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ width: 392 }}><div className="ca-chat">
    <div className="ca-chat__bot" id="gen"><AssistantBlocks editor={null as any} m={m} /></div>
    <div className="ca-chat__bot" id="search"><AssistantBlocks editor={null as any} m={s} /></div>
  </div></div>)
;(globalThis as any).__ready = true
