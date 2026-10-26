import { useEffect, useState, type ReactNode } from 'react'
import type { Editor } from 'tldraw'

import { answerAsk, outputsOf, toolLabel, toolName, type AskAnswers, type AskQuestion, type BotBlock, type BotMessage } from '../bot'
import { setAgentPlanConfirmed } from '../comfy'
import { draftAtom } from '../agent'
import { errorText } from '../jobs'
import { confirmAtom } from './Confirm'
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

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

type QState = { selected: string[]; other: string }

function askQuestions(b: BotBlock): AskQuestion[] {
  if (b.questions?.length) return b.questions
  return [{
    id: '_',
    prompt: b.prompt ?? '',
    options: b.options ?? [],
    min_selections: b.min_selections,
    max_selections: b.max_selections,
    allow_other: b.allow_other,
    defaults: b.defaults,
    page: b.page ?? 1,
  }]
}

function askPageCount(b: BotBlock, questions: AskQuestion[]): number {
  if (b.page_count && b.page_count > 0) return b.page_count
  return Math.max(1, ...questions.map((q) => q.page ?? 1))
}

function qDefaults(q: AskQuestion): string[] {
  const max = q.max_selections ?? (q.options?.length ? 1 : 0)
  if (q.defaults?.length) return q.defaults.slice(0, max)
  const rec = (q.options ?? []).filter((o) => o.recommended).map((o) => o.id)
  return rec.slice(0, max)
}

function initQStates(questions: AskQuestion[]): Record<string, QState> {
  const out: Record<string, QState> = {}
  for (const q of questions) {
    out[q.id] = { selected: qDefaults(q), other: '' }
  }
  return out
}

function qAnswerLabels(q: AskQuestion, selected: string[], other?: string): string {
  const options = q.options ?? []
  const labels = selected.map((id) => options.find((o) => o.id === id)?.label ?? id)
  return [...labels, other].filter(Boolean).join(t('common.listSep'))
}

function askAnswerLabels(b: BotBlock): string {
  const questions = askQuestions(b)
  if (b.answers && questions.length) {
    return questions.map((q) => {
      const a = b.answers![q.id]
      if (!a) return ''
      return qAnswerLabels(q, a.selected ?? [], a.other_text)
    }).filter(Boolean).join(t('common.listSep')) || ''
  }
  const options = b.options ?? []
  const labels = (b.selected ?? []).map((id) => options.find((o) => o.id === id)?.label ?? id)
  return [...labels, b.other_text].filter(Boolean).join(t('common.listSep'))
}

function qFilled(q: AskQuestion, st: QState): boolean {
  const textOnly = !(q.options?.length) && !!q.allow_other
  if (textOnly) return st.other.trim().length > 0
  if (st.selected.length > 0) return true
  return !!(q.allow_other && st.other.trim().length > 0)
}

function toAnswers(questions: AskQuestion[], states: Record<string, QState>): AskAnswers {
  const answers: AskAnswers = {}
  for (const q of questions) {
    const st = states[q.id] ?? { selected: [], other: '' }
    const entry: { selected: string[]; other_text?: string } = { selected: st.selected }
    if (q.allow_other && st.other.trim()) {
      entry.other_text = st.other.trim()
    }
    answers[q.id] = entry
  }
  return answers
}

/** Historical chip asks (no kind) keep the memo path; new question cards use the grey Q/A bubble. */
function AskMemo({ b }: { b: BotBlock }) {
  const labels = askAnswerLabels(b)
  return (
    <div className="ca-chat__memo">
      <span className="ca-icon">{Icons.check}</span>
      {b.prompt} → {b.status === 'answered' ? labels : b.status === 'expired' ? t('chatMessage.timedOut') : t('chatMessage.canceled')}
    </div>
  )
}

function QuestionAnswered({ b }: { b: BotBlock }) {
  if (b.status !== 'answered') {
    return (
      <div className="ca-chat__memo">
        <span className="ca-icon">{Icons.check}</span>
        {b.prompt} → {b.status === 'expired' ? t('chatMessage.timedOut') : t('chatMessage.canceled')}
      </div>
    )
  }
  const questions = askQuestions(b)
  if (questions.length > 1 || (b.answers && Object.keys(b.answers).length > 1)) {
    return (
      <div className="ca-qmemo">
        {questions.map((q) => {
          const a = b.answers?.[q.id]
          const answer = a ? (qAnswerLabels(q, a.selected ?? [], a.other_text) || t('chatMessage.skipped')) : (askAnswerLabels(b) || t('chatMessage.skipped'))
          return (
            <div key={q.id} className="ca-qmemo__block">
              <div className="ca-qmemo__row"><span className="ca-qmemo__k">{t('chatMessage.qaAsk')}</span><span className="ca-qmemo__v">{q.prompt}</span></div>
              <div className="ca-qmemo__row"><span className="ca-qmemo__k">{t('chatMessage.qaAnswer')}</span><span className="ca-qmemo__v">{answer}</span></div>
            </div>
          )
        })}
      </div>
    )
  }
  const answer = askAnswerLabels(b) || t('chatMessage.skipped')
  return (
    <div className="ca-qmemo">
      <div className="ca-qmemo__row"><span className="ca-qmemo__k">{t('chatMessage.qaAsk')}</span><span className="ca-qmemo__v">{b.prompt}</span></div>
      <div className="ca-qmemo__row"><span className="ca-qmemo__k">{t('chatMessage.qaAnswer')}</span><span className="ca-qmemo__v">{answer}</span></div>
    </div>
  )
}

function QuestionBlock({ q, st, onChange }: { q: AskQuestion; st: QState; onChange: (next: QState) => void }) {
  const options = q.options ?? []
  const multi = (q.max_selections ?? 1) > 1
  const allowOther = !!q.allow_other
  const textOnly = !options.length && allowOther
  const recommended = new Set([...(q.defaults ?? []), ...options.filter((o) => o.recommended).map((o) => o.id)])
  const otherLetter = LETTERS[options.length] ?? 'A'

  const toggle = (id: string) => {
    // Product lock: pick A–D keeps other text; only moves soft-select (do NOT clear other)
    if (!multi) onChange({ ...st, selected: [id] })
    else {
      const selected = st.selected.includes(id)
        ? st.selected.filter((x) => x !== id)
        : [...st.selected, id].slice(-(q.max_selections ?? 1))
      onChange({ ...st, selected })
    }
  }
  const onOther = (value: string) => {
    // Single-select: typing/filling other clears A–D soft-select; multi: other coexists
    if (!multi && value.trim()) onChange({ ...st, selected: [], other: value })
    else onChange({ ...st, other: value })
  }
  const stealOther = () => {
    // Refocus nonempty other steals soft-select back (deselects A–D); text stays
    if (!multi && st.other.trim() && st.selected.length) onChange({ ...st, selected: [] })
  }
  // Soft-select on other only when it is the active answer (single: no A–D selected; multi: when filled)
  const otherOn = !!st.other.trim() && (multi || st.selected.length === 0)

  return (
    <div className="ca-q__block">
      <div className="ca-q__prompt">{q.prompt}{multi && <span className="ca-q__hint">{t('chatMessage.multipleChoice')}</span>}</div>
      <div className="ca-q__opts">
        {textOnly ? (
          <div className="ca-q__opt" data-text="" data-on={st.other.trim() ? true : undefined}>
            <span className="ca-q__letter">A</span>
            <textarea
              className="ca-q__input"
              rows={1}
              value={st.other}
              placeholder={q.placeholder || t('chatMessage.writeYourIdea')}
              onChange={(e) => onOther(e.target.value)}
              onKeyDown={(e) => e.stopPropagation()}
            />
          </div>
        ) : (
          <>
            {options.map((o, i) => (
              <button key={o.id} type="button" className="ca-q__opt" title={o.description} data-on={st.selected.includes(o.id) || undefined} onClick={() => toggle(o.id)}>
                <span className="ca-q__letter">{LETTERS[i] ?? String(i + 1)}</span>
                <span className="ca-q__text">{o.label}</span>
                {recommended.has(o.id) && <span className="ca-q__rec">{t('chatMessage.recommended')}</span>}
              </button>
            ))}
            {allowOther && (
              <div className="ca-q__opt" data-other="" data-text="" data-on={otherOn || undefined}>
                <span className="ca-q__letter">{otherLetter}</span>
                <textarea
                  className="ca-q__input"
                  rows={1}
                  value={st.other}
                  placeholder={q.placeholder || t('chatMessage.other')}
                  onChange={(e) => onOther(e.target.value)}
                  onFocus={stealOther}
                  onKeyDown={(e) => e.stopPropagation()}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/** #328/#330: Lovart-style Question card — multi-q + in-card paging. */
function QuestionCard({ b }: { b: BotBlock }) {
  const questions = askQuestions(b)
  const pageCount = askPageCount(b, questions)
  const allowSkip = b.allow_skip !== false
  const [page, setPage] = useState(1)
  const [furthest, setFurthest] = useState(1)
  const [states, setStates] = useState<Record<string, QState>>(() => initQStates(questions))
  const [error, setError] = useState('')
  if (b.status !== 'pending') return <QuestionAnswered b={b} />

  const onPage = questions.filter((q) => (q.page ?? 1) === page)
  const pageOk = onPage.every((q) => qFilled(q, states[q.id] ?? { selected: [], other: '' }))
  const allOk = questions.every((q) => qFilled(q, states[q.id] ?? { selected: [], other: '' }))
  const isLast = page >= pageCount
  const showPager = pageCount > 1

  const setQ = (id: string, next: QState) => setStates((s) => ({ ...s, [id]: next }))
  const go = (n: number) => {
    const next = Math.max(1, Math.min(pageCount, n))
    setPage(next)
    setFurthest((f) => Math.max(f, next))
  }
  const resolve = (answers: AskAnswers) => {
    const qs = questions
    const flatSel = qs.length === 1 ? (answers[qs[0].id]?.selected ?? []) : []
    const flatOther = qs.length === 1 ? (answers[qs[0].id]?.other_text ?? '') : ''
    void answerAsk(b.ask_id!, flatSel, flatOther, answers).catch((e) => setError(errorText(e)))
  }
  const onSkip = () => resolve(Object.fromEntries(questions.map((q) => [q.id, { selected: [] as string[] }])))
  const onNext = () => { if (!pageOk) return; go(page + 1) }
  const onSubmit = () => { if (!allOk) return; resolve(toAnswers(questions, states)) }

  return (
    <div className="ca-q">
      <div className="ca-q__head">
        <div className="ca-q__label"><span className="ca-icon">{Icons.question}</span>{t('chatMessage.question')}</div>
        {showPager && (
          <div className="ca-q__page">
            <button type="button" className="ca-q__chev" disabled={page <= 1} aria-label={t('chatMessage.prevPage')} onClick={() => go(page - 1)}>
              <span className="ca-icon ca-q__chev-icon ca-q__chev-icon--left">{Icons.next}</span>
            </button>
            <span>{t('chatMessage.pageOf', page, pageCount)}</span>
            <button type="button" className="ca-q__chev" disabled={page >= pageCount || (page >= furthest && !pageOk)} aria-label={t('chatMessage.nextPage')} onClick={() => { if (page < furthest || pageOk) go(page + 1) }}>
              <span className="ca-icon ca-q__chev-icon">{Icons.next}</span>
            </button>
          </div>
        )}
      </div>
      <div className="ca-q__body">
        {onPage.map((q) => (
          <QuestionBlock key={q.id} q={q} st={states[q.id] ?? { selected: [], other: '' }} onChange={(next) => setQ(q.id, next)} />
        ))}
      </div>
      {error && <div className="ca-chat__hint">{error}</div>}
      <div className="ca-q__foot">
        {allowSkip && <button type="button" className="ca-q__skip" onClick={onSkip}>{t('chatMessage.skip')}</button>}
        {isLast ? (
          <button type="button" className="ca-q__submit" disabled={!allOk} onClick={onSubmit}>{t('chatMessage.submit')} <span className="ca-q__key">↵</span></button>
        ) : (
          <button type="button" className="ca-q__submit" disabled={!pageOk} onClick={onNext}>{t('chatMessage.next')} <span className="ca-q__key">→</span></button>
        )}
      </div>
    </div>
  )
}

/** run_approval keeps the chip one-click Ask UI. */
function Ask({ b }: { b: BotBlock }) {
  const [picked, setPicked] = useState<string[]>([])
  const [other, setOther] = useState('')
  const [error, setError] = useState('')
  const multi = (b.max_selections ?? 1) > 1
  const options = b.options ?? []
  if (b.status !== 'pending') return <AskMemo b={b} />
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

function renderAsk(b: BotBlock, key: string | number) {
  if (b.kind === 'plan_quote') return <PlanQuote key={key} b={b} />
  if (b.kind === 'run_approval') return <Ask key={key} b={b} />
  // New question cards (kind=question) and in-flight pending without kind use QuestionCard.
  // Historical answered chips without kind keep the memo path.
  if (b.status !== 'pending' && b.kind !== 'question') return <AskMemo key={key} b={b} />
  return <QuestionCard key={key} b={b} />
}

/** #235: the plan total uses the same cost-confirm card as a single job. No second card, no new styles. */
function PlanQuote({ b }: { b: BotBlock }) {
  const [error, setError] = useState('')
  const askId = b.ask_id
  const pending = b.status === 'pending'
  const startLabel = (b.options ?? []).find((o) => o.id === 'start')?.label ?? ''
  useEffect(() => {
    if (!pending || !askId) return
    let live = true
    const open = () => confirmAtom.set({
      title: t('jobs.confirmTitle'),
      desc: b.prompt ?? '',
      ok: startLabel,
      lines: b.lines ?? [],
      totalLabel: b.total_label,
      total: b.total,
      run: () => {
        if (!live) return
        setAgentPlanConfirmed(true)
        void answerAsk(askId, ['start'], '').catch((e) => {
          if (!live) return
          setAgentPlanConfirmed(false)
          setError(errorText(e))
          open()
        })
      },
      cancel: () => {
        if (!live) return
        setAgentPlanConfirmed(false)
        void answerAsk(askId, ['cancel'], '').catch((e) => { if (live) setError(errorText(e)) })
      },
    })
    open()
    return () => {
      live = false
      const cur = confirmAtom.get()
      if (cur && cur.desc === (b.prompt ?? '')) confirmAtom.set(null)
    }
  }, [pending, askId]) // eslint-disable-line react-hooks/exhaustive-deps -- reopen only when this ask starts or resolves
  if (pending) return error ? <div className="ca-chat__hint">{error}</div> : null
  const started = b.status === 'answered' && (b.selected ?? []).includes('start')
  return (
    <div className="ca-chat__memo">
      <span className="ca-icon">{started ? Icons.check : Icons.close}</span>
      {b.prompt} → {started ? startLabel : b.status === 'expired' ? t('chatMessage.timedOut') : t('chatMessage.canceled')}
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
    <div className="ca-chat__tool ca-chat__thought" data-live={live || undefined} data-open={open || undefined}>
      <button type="button" className="ca-chat__step" onClick={() => setOpen(!open)}>
        <span className="ca-chat__thinkicon"><span className="ca-icon">{Icons.think}</span></span>
        <span className="ca-chat__thinklabel">{live ? t('chatMessage.thinking') : t('chatMessage.thought')}</span>
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
      if (b.type === 'ask') items.push(renderAsk(b, b.ask_id ?? i))
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
