import { useEffect, useState, type ReactNode } from 'react'
import type { Editor } from 'tldraw'

import { answerAsk, outputsOf, toolLabel, toolName, type BotBlock, type BotMessage } from '../bot'
import { draftAtom } from '../agent'
import { errorText } from '../jobs'
import { schedulesOpenAtom } from '../schedules'
import { Icons } from './icons'
import { Markdown } from './Markdown'
import { Thumb } from './TaskDetails'
import { CopyButton } from './CopyButton'
import { t } from '../i18n'
import { stepState } from './stepState'

const GEN_TOOLS = new Set(['generate_image', 'generate_video', 'edit_image', 'animate_image', 'upscale_image', 'remove_background', 'expand_image', 'split_layers', 'change_angle', 'replace_text', 'edit_region', 'erase_region', 'move_object', 'style_transfer', 'extend_video', 'upscale_video', 'remove_video_background', 'generate_music', 'generate_sound_effect', 'text_to_speech', 'image_to_3d', 'edit_elements', 'create_mockup', 'create_slides'])

export function textOf(m: BotMessage): string {
  return m.blocks.filter((b) => b.type === 'text').map((b) => b.text ?? '').join('').trim()
}

function summary(b: BotBlock): string {
  const input = b.input ?? {}
  const name = toolName(b.name)
  if (name === 'memory') return [input.action, input.text ?? input.new].filter(Boolean).join(t('chatMessage.colon'))
  if (name === 'skill') return [input.action, input.name].filter(Boolean).join(' ')
  return String(input.prompt ?? input.text ?? input.name ?? input.title ?? '').slice(0, 80)
}

function Step({ editor, use, result, thumbs = true }: { editor: Editor; use: BotBlock; result?: BotBlock; thumbs?: boolean }) {
  const [open, setOpen] = useState(false)
  const outputs = result && thumbs ? outputsOf([result]) : []
  const kind = stepState(result)
  const state = kind === 'running' ? t('chatMessage.inProgress') : kind === 'cancelled' ? t('chatMessage.cancelled') : kind === 'error' ? t('chatMessage.failed') : result?.duration_ms != null ? `${(result.duration_ms / 1000).toFixed(1)}s` : ''
  return (
    <div className="ca-chat__tool" data-error={kind === 'error' || undefined} data-cancelled={kind === 'cancelled' || undefined}>
      <button type="button" className="ca-chat__step" onClick={() => setOpen(!open)}>
        <span className="ca-icon">{GEN_TOOLS.has(toolName(use.name)) ? Icons.genImage : kind === 'error' ? Icons.close : kind === 'done' ? Icons.check : Icons.agent}</span>
        <span>{toolLabel(use.name)}</span>
        <span className="ca-chat__arg">{summary(use)}</span>
        <span className="ca-chat__status">{state}</span>
      </button>
      {open && (
        <div className="ca-chat__io">
          <pre>{JSON.stringify(use.input ?? {}, null, 2)}</pre>
          {result?.text && <pre>{result.text}</pre>}
        </div>
      )}
      {outputs.length > 0 && <div className="ca-chat__thumbs">{outputs.map((s) => <Thumb key={s} editor={editor} src={s} />)}</div>}
    </div>
  )
}

/** #232: an LLM timeout / 429 / 5xx retry, drawn as an ordinary tool row; 429 counts down to the retry. */
function Retry({ b: block, live }: { b: BotBlock; live: boolean }) {
  const b = block as BotBlock & { kind?: string; attempt?: number; max?: number; until?: number; http_status?: number }
  const [now, setNow] = useState(() => Date.now())
  const left = Math.ceil(((b.until ?? 0) - now) / 1000)
  const waiting = live && left > 0
  useEffect(() => {
    if (!waiting) return
    const id = setInterval(() => setNow(Date.now()), 250)
    return () => clearInterval(id)
  }, [waiting])
  const reason = b.kind === '429' ? t('chatMessage.retryRateLimited', b.attempt ?? 1, b.max ?? 2) : b.kind === 'timeout' ? t('chatMessage.retryTimeout', b.attempt ?? 1, b.max ?? 2) : t('chatMessage.retryServer', b.http_status || '5xx', b.attempt ?? 1, b.max ?? 2)
  return (
    <div className="ca-chat__tool" data-retry={b.kind}>
      <div className="ca-chat__step" style={{ cursor: 'default' }}>
        <span className="ca-icon">{Icons.agent}</span>
        <span>{t('chatMessage.retry')}</span>
        <span className="ca-chat__arg">{reason}</span>
        <span className="ca-chat__status">{waiting ? t('chatMessage.retryIn', left) : live ? t('chatMessage.inProgress') : t('chatMessage.retried')}</span>
      </div>
    </div>
  )
}

function Ask({ b }: { b: BotBlock }) {
  const [picked, setPicked] = useState<string[]>([])
  const [other, setOther] = useState('')
  const [error, setError] = useState('')
  const multi = (b.max_selections ?? 1) > 1
  const options = b.options ?? []
  if (b.status !== 'pending') {
    const labels = (b.selected ?? []).map((id) => options.find((o) => o.id === id)?.label ?? id)
    return (
      <div className="ca-chat__memo">
        <span className="ca-icon">{Icons.check}</span>
        {b.prompt} → {b.status === 'answered' ? [...labels, b.other_text].filter(Boolean).join(t('common.listSep')) : b.status === 'expired' ? t('chatMessage.timedOut') : t('chatMessage.canceled')}
      </div>
    )
  }
  const toggle = (id: string) => setPicked(multi ? (picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]) : [id])
  const submit = (selected: string[]) => void answerAsk(b.ask_id!, selected, other.trim()).catch((e) => setError(errorText(e)))
  return (
    <div className="ca-ask">
      <div className="ca-ask__title">{b.prompt}{multi && <span className="ca-menu__key">{t('chatMessage.multipleChoice')}</span>}</div>
      <div className="ca-panel__chips">
        {options.map((o) => (
          <button key={o.id} type="button" className="ca-panel__chip" title={o.description} data-on={picked.includes(o.id) || undefined} onClick={() => (b.kind === 'run_approval' ? submit([o.id]) : toggle(o.id))}>{o.label}</button>
        ))}
      </div>
      {b.allow_other && <input className="ca-panel__input" value={other} placeholder={t('chatMessage.orWriteYourOwn')} onChange={(e) => setOther(e.target.value)} onKeyDown={(e) => e.stopPropagation()} />}
      {error && <div className="ca-chat__hint">{error}</div>}
      {b.kind !== 'run_approval' && (
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__primary" disabled={!picked.length && !other.trim()} onClick={() => submit(picked)}>{t('chatMessage.submit')}</button>
        </div>
      )}
    </div>
  )
}

function Task({ editor, b }: { editor: Editor; b: BotBlock }) {
  return (
    <div className="ca-chat__task">
      <div className="ca-chat__step">
        <span className="ca-icon">{b.detail?.tool === 'generate_image' ? Icons.genImage : Icons.genVideo}</span>
        <span>{b.label}</span>
        <span className="ca-chat__status">{b.error ? t('chatMessage.generationFailed') : b.srcs ? '' : t('chatMessage.generating')}</span>
      </div>
      {b.srcs && <div className="ca-chat__thumbs">{b.srcs.map((s) => <Thumb key={s} editor={editor} src={s} />)}</div>}
    </div>
  )
}

function Plan({ b, live }: { b: BotBlock; live: boolean }) {
  const steps: { text?: string; status?: string }[] = Array.isArray(b.input?.steps) ? b.input.steps : []
  const done = steps.filter((s) => s.status === 'done').length
  return (
    <div className="ca-plan" data-live={live || undefined}>
      <div className="ca-plan__head"><span>{t('bot.plan')}</span><span className="ca-chat__status">{done}/{steps.length}</span></div>
      {steps.map((s, i) => (
        <div key={i} className="ca-plan__step" data-status={s.status}>
          <span className="ca-plan__mark">{s.status === 'done' && Icons.check}</span>
          <span>{s.text}</span>
        </div>
      ))}
    </div>
  )
}

function Thought({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="ca-chat__tool ca-chat__thought" data-open={open || undefined}>
      <button type="button" className="ca-chat__step" onClick={() => setOpen(!open)}>
        <span className="ca-icon">{Icons.agent}</span>
        <span>{live ? t('chatMessage.thinking') : t('chatMessage.thought')}</span>
        {!open && <span className="ca-chat__arg">{text.trim().split('\n').at(-1)}</span>}
        <span className="ca-chat__chev ca-icon">{Icons.chevron}</span>
      </button>
      {open && <div className="ca-chat__io ca-chat__thoughttext">{text.trim()}</div>}
    </div>
  )
}

type Pair = { use: BotBlock; result?: BotBlock; i: number }

function StepGroup({ editor, steps, stopped }: { editor: Editor; steps: Pair[]; stopped?: boolean }) {
  const [open, setOpen] = useState(false)
  const failed = steps.filter((s) => s.result?.status === 'error').length
  return (
    <div className="ca-chat__tool" data-open={open || undefined}>
      <button type="button" className="ca-chat__step" onClick={() => setOpen(!open)}>
        <span className="ca-icon">{failed || stopped ? Icons.close : Icons.check}</span>
        <span>{t('chatMessage.usedTools', steps.length)}</span>
        <span className="ca-chat__arg">{[...new Set(steps.map((s) => toolLabel(s.use.name)))].join(t('common.listSep'))}</span>
        <span className="ca-chat__chev ca-icon">{Icons.chevron}</span>
      </button>
      {open && <div className="ca-chat__group">{steps.map((s) => <Step key={s.i} editor={editor} use={s.use} result={s.result} thumbs={false} />)}</div>}
    </div>
  )
}

export function AssistantBlocks({ editor, m }: { editor: Editor; m: BotMessage }) {
  const results = new Map(m.blocks.filter((b) => b.type === 'tool_result' && b.id).map((b) => [b.id, b]))
  const resultOf = (b: BotBlock, i: number) => (b.id ? results.get(b.id) : m.blocks[i + 1]?.type === 'tool_result' ? m.blocks[i + 1] : undefined)
  const isPlan = (b: BotBlock) => b.type === 'tool_use' && toolName(b.name) === 'update_plan'
  const plan = m.blocks.filter(isPlan).at(-1)
  const done = m.status !== 'streaming'
  const outputs = done ? outputsOf(m.blocks.filter((b) => b.type !== 'task')) : []
  const items: ReactNode[] = []
  let run: Pair[] = []
  const flush = (stopped = false) => {
    if (run.length > 1) items.push(<StepGroup key={`g${run[0].i}`} editor={editor} steps={run} stopped={stopped} />)
    else if (run.length) items.push(<Step key={run[0].i} editor={editor} use={run[0].use} result={run[0].result} thumbs={false} />)
    run = []
  }
  let planShown = false
  m.blocks.forEach((b, i) => {
    if (isPlan(b)) {
      if (planShown) return
      planShown = true
      flush()
      items.push(<Plan key={`p${i}`} b={plan!} live={!done} />)
    } else if (b.type === 'tool_use' && done) run.push({ use: b, result: resultOf(b, i), i })
    else if (b.type !== 'tool_result') {
      flush(b.type === 'notice' && b.level === 'error') // turn ended in error / loop-guard stop: reuse the failed icon
      if (b.type === 'text') items.push(<Markdown key={i} text={b.text ?? ''} />)
      if (b.type === 'thinking' && b.text?.trim()) items.push(<Thought key={i} text={b.text} live={!done && i === m.blocks.length - 1} />)
      if (b.type === 'tool_use') items.push(<Step key={i} editor={editor} use={b} result={resultOf(b, i)} />)
      if (b.type === 'retry') items.push(<Retry key={i} b={b} live={!done && !m.blocks.slice(i + 1).some((x) => x.type === 'retry')} />)
      if (b.type === 'ask') items.push(<Ask key={b.ask_id ?? i} b={b} />)
      if (b.type === 'task') items.push(<Task key={i} editor={editor} b={b} />)
      if (b.type === 'notice') items.push(<div key={i} className="ca-chat__notice" data-level={b.level}>{b.text}</div>)
    }
  })
  flush()
  if (outputs.length) items.push(<div key="results" className="ca-chat__thumbs ca-chat__results">{outputs.map((s) => <Thumb key={s} editor={editor} src={s} />)}</div>)
  return <>{items}</>
}

export function UserMessage({ editor, m, onBranch }: { editor: Editor; m: BotMessage; onBranch?: () => void }) {
  const text = textOf(m)
  const media = m.blocks.filter((b) => b.type === 'image' || b.type === 'video' || b.type === 'audio')
  return (
    <div className="ca-chat__user" data-queued={m.status === 'queued' || undefined}>
      <div className="ca-chat__acts">
        <button type="button" className="ca-history__del" title={t('chatMessage.editAgain')} onClick={() => draftAtom.set(text)}>{Icons.textTool}</button>
        <CopyButton text={text} />
        <button type="button" className="ca-history__del" title={t('chatMessage.setAsScheduledTask')} onClick={() => schedulesOpenAtom.set({ prompt: text })}>{Icons.bell}</button>
        {onBranch && <button type="button" className="ca-history__del" title={t('chatMessage.forkNewChatFromHere')} onClick={onBranch}>{Icons.merge}</button>}
      </div>
      {media.length > 0 && <div className="ca-chat__thumbs">{media.map((b) => <Thumb key={b.url} editor={editor} src={b.url!} />)}</div>}
      {m.blocks.filter((b) => b.type === 'skill').map((b) => <span key={b.name} className="ca-chip"><span className="ca-icon">{Icons.skill}</span>{b.name}</span>)}
      {m.blocks.filter((b) => b.type === 'kit').map((b) => <span key={b.name} className="ca-chip"><span className="ca-icon">{Icons.assets}</span>{b.name}</span>)}
      {m.blocks.filter((b) => b.type === 'file').map((b) => <a key={b.url} className="ca-chip" href={b.url} target="_blank" rel="noreferrer"><span className="ca-icon">{Icons.page}</span>{b.name}</a>)}
      {text && <div className="ca-chat__bubble">{text}</div>}
      {m.status === 'queued' && <span className="ca-chat__hint">{t('chatMessage.queuedSendsAfterTheCurrent')}</span>}
    </div>
  )
}
