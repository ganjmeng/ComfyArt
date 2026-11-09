// #710: real QuestionCard / user bubble / composer stop slot. Chat data is injected; no network.
import { useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { ComposerSlot } from '../../../src/ui/ComposerSlot'
import { AssistantBlocks, isDockedQuestion, renderAsk, UserMessage } from '../../../src/ui/ChatMessage'
import { setLang } from '../i18n_stub'

type State = {
  lang?: 'zh' | 'en'
  theme?: 'light' | 'dark'
  prompt?: string
  status?: 'pending' | 'answered'
  selected?: string[]
  other?: string
  userText?: string
  skill?: string
  images?: number
  running?: boolean
}

const rootEl = document.getElementById('root')!
let root: Root | null = null

function App({ s }: { s: State }) {
  return <Screen key={`${s.lang}|${s.theme}|${s.status}|${s.running}|${s.prompt}|${s.images}|${(s.selected || []).join(',')}`} s={s} />
}

function Screen({ s }: { s: State }) {
  const lang = s.lang === 'en' ? 'en' : 'zh'
  setLang(lang)
  document.documentElement.dataset.theme = s.theme === 'dark' ? 'dark' : 'light'
  const [aborted, setAborted] = useState(false)
  const prompt = s.prompt || ''
  const status = s.status || 'pending'
  const ask: any = {
    type: 'ask', ask_id: 'plan1', kind: 'question', status,
    prompt,
    options: [
      { id: 'generate', label: '开始生成' },
      { id: 'regenerate', label: '换一组方案' },
    ],
    allow_other: true,
    allow_skip: true,
    min_selections: 1,
    max_selections: 1,
    questions: [{
      id: '_', prompt,
      options: [
        { id: 'generate', label: '开始生成' },
        { id: 'regenerate', label: '换一组方案' },
      ],
      allow_other: true, min_selections: 1, max_selections: 1,
    }],
    ...(status === 'answered' ? {
      selected: s.selected || [],
      other_text: s.other || '',
      answers: { _: { selected: s.selected || [], ...(s.other ? { other_text: s.other } : {}) } },
    } : {}),
  }
  const blocks: any[] = [ask]
  const m: any = { id: 'm1', role: 'assistant', status: s.running ? 'streaming' : 'done', blocks }
  const userBlocks: any[] = []
  if (s.skill) userBlocks.push({ type: 'skill', name: s.skill })
  for (let i = 0; i < (s.images || 0); i++) userBlocks.push({ type: 'image', url: `blob:ref-${i}` })
  if (s.userText) userBlocks.push({ type: 'text', text: s.userText })
  const user: any = { id: 'u1', role: 'user', status: 'done', blocks: userBlocks }
  const docked = m.blocks.filter(isDockedQuestion)
  const running = !!s.running && !aborted
  const editor: any = {}
  return (
    <div className="ca-panel" data-testid="plan-harness" data-run={aborted ? 'aborted' : running ? 'running' : 'idle'} style={{ width: 440, display: 'flex', flexDirection: 'column', background: 'var(--ca-float, #fff)' }}>
      <div className="ca-chat" style={{ overflow: 'visible' }}>
        {userBlocks.length > 0 && <UserMessage editor={editor} m={user} />}
        <div className="ca-chat__bot" data-testid="bot">
          <AssistantBlocks editor={editor} m={m} dockAsks />
        </div>
      </div>
      {docked.length > 0 && <div className="ca-chat__dock" data-testid="question-dock">{docked.map((b: any, i: number) => renderAsk(b, b.ask_id ?? i))}</div>}
      <div className="ca-composer" data-testid="composer">
        <ComposerSlot
          showSend={false}
          setVoice={() => {}}
          canSend={false}
          onSend={() => {}}
          onText={() => {}}
          onError={() => {}}
          onStop={running && docked.length === 0 ? () => setAborted(true) : undefined}
        />
      </div>
    </div>
  )
}

function render(s: State) {
  if (!s) return
  if (!root) root = createRoot(rootEl)
  root.render(<App s={s} />)
  ;(window as any).__ready = true
}
;(window as any).__render = render
