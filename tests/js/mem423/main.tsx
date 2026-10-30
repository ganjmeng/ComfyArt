// #423: one 记忆已更新 › per turn + 「已保存 N 条」 detail — main (3 rows, no count) | ours (1 row + count).
import { createRoot } from 'react-dom/client'
import { AssistantBlocks } from '../../../src/ui/ChatMessage'
import { Icons } from '../../../src/ui/icons'
import { setLang, t } from '../i18n_stub'

const q = new URLSearchParams(location.search)
const lang = q.get('lang') === 'en' ? 'en' : 'zh'
setLang(lang)
if (q.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark'

const use = (id: string) => ({ type: 'tool_use', id, name: 'mcp__comfyart__memory', input: { action: 'add' } })
const res = (id: string, body: object) => (
  { type: 'tool_result', id, name: 'mcp__comfyart__memory', status: 'success', text: JSON.stringify(body) }
)

const facts = lang === 'en'
  ? ['Brand colour: blue', 'Font: Source Han Sans', 'Audience: young people']
  : ['品牌色：蓝色', '字体：思源黑体', '受众：年轻人']
const reply = lang === 'en' ? 'Got it.' : '好的，已记下。'

// Pre-#423 main: three separate 记忆已更新 › rows (hand-built — current AssistantBlocks folds them).
function MainBroken() {
  const label = t('chatMessage.memoryUpdated')
  return (
    <div className="ca-process">
      <div className="ca-process__steps">
        {facts.map((tx, i) => (
          <div key={i} className="ca-process__group">
            <div className="ca-process__row" data-kind="memory_updated" data-testid={i === 0 ? 'memory-updated-row' : undefined}>
              <span className={`ca-process__icon ca-process__icon--memory_updated`} data-kind="memory_updated">
                <span className="ca-icon">{Icons.memoryHead}</span>
              </span>
              <span className="ca-process__label">
                {label}
                <span className="ca-process__memchev ca-icon">{Icons.memoryChev}</span>
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className="ca-chat__text" style={{ marginTop: 8 }}>{reply}</div>
      <div style={{ font: '11px/14px system-ui', opacity: .4, marginTop: 4 }}>{facts.join(' · ')}</div>
    </div>
  )
}

// Ours: one merged memory_updated with count + texts → one row + 「已保存 3 条」 detail
const oursMsg: any = {
  id: 'o', role: 'assistant', status: 'done', blocks: [
    { type: 'thinking', text: 'mem' },
    use('c1'), res('c1', { saved: true, memory_ids: ['m1'], texts: [facts[0]] }),
    use('c2'), res('c2', { saved: true, memory_ids: ['m2'], texts: [facts[1]] }),
    use('c3'), res('c3', { saved: true, memory_ids: ['m3'], texts: [facts[2]] }),
    {
      type: 'memory_updated',
      memory_ids: ['m1', 'm2', 'm3'],
      texts: facts,
      tool_id: 'c1',
      tool_ids: ['c1', 'c2', 'c3'],
      updated_ids: [],
      count: 3,
      added_count: 3,
      updated: 0,
    },
    { type: 'text', text: reply },
  ],
}

createRoot(document.getElementById('root')!).render(
  <div className="ca-root" style={{ width: 840, padding: 16, display: 'flex', gap: 24, background: 'var(--ca-bg)' }}>
    <div style={{ flex: 1 }}>
      <div style={{ font: '12px/16px system-ui', opacity: .55, marginBottom: 8 }}>main</div>
      <div className="ca-chat"><div className="ca-chat__bot" id="main"><MainBroken /></div></div>
    </div>
    <div style={{ flex: 1 }}>
      <div style={{ font: '12px/16px system-ui', opacity: .55, marginBottom: 8 }}>ours</div>
      <div className="ca-chat"><div className="ca-chat__bot" id="ours"><AssistantBlocks editor={null as any} m={oursMsg} /></div></div>
    </div>
  </div>)
;(globalThis as any).__ready = true
