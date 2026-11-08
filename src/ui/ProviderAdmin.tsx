import { useEffect, useMemo, useState } from 'react'

import { lang } from '../i18n'
import {
  checkLlm,
  loadProviderAdmin,
  ProviderAdminError,
  providerAdminOpen,
  restoreLlmProvider,
  restoreTool,
  saveLlmProvider,
  saveTool,
  saveToolBatch,
  setProviderAdminOpen,
  subscribeProviderAdmin,
  type EndPoint,
  type ProviderAdminState,
  type ToolChoice,
  type ToolRoute,
  type ToolRow,
} from '../providerAdmin'

const tx = (zh: string, en: string) => (lang === 'zh' ? zh : en)
const lt = (value: { zh?: string; en?: string } | undefined) => (lang === 'zh' ? value?.zh : value?.en) || value?.zh || value?.en || ''
const same = (a: EndPoint | null | undefined, b: EndPoint | null | undefined) => (a?.provider || '') === (b?.provider || '') && (a?.model || '') === (b?.model || '')
const routeKey = (route: ToolRoute | null) => JSON.stringify(route)

const GROUPS = [
  ['all', '全部', 'All'],
  ['image', '图像', 'Images'],
  ['video', '视频', 'Video'],
  ['other', '其他', 'Other'],
  ['llm', '语言模型', 'Language'],
] as const

function failText(e: unknown) {
  if (e instanceof ProviderAdminError && e.code === 'needs_key') return tx('还没有 Replicate 密钥，不能启用。正在用的线路没变。', 'No Replicate key, so this cannot be turned on. The live route is unchanged.')
  if (e instanceof ProviderAdminError) return e.message
  return tx('没有保存成功。请检查网络后再试。', 'Could not save. Check the connection and try again.')
}

function blank(): ToolRoute {
  return { primary: { provider: 'wavespeed', model: 'existing' }, backup: null, fallback: false }
}

function useOpen() {
  const [value, setValue] = useState(providerAdminOpen())
  useEffect(() => subscribeProviderAdmin(() => setValue(providerAdminOpen())), [])
  return value
}

export function ProviderAdmin() {
  const open = useOpen()
  const [state, setState] = useState<ProviderAdminState | null>(null)
  const [loading, setLoading] = useState(false)
  const [forbidden, setForbidden] = useState(false)
  const [group, setGroup] = useState<(typeof GROUPS)[number][0]>('all')
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState('generate_image')
  const [drafts, setDrafts] = useState<Record<string, ToolRoute>>({})
  const [checked, setChecked] = useState<string[]>([])
  const [batchModel, setBatchModel] = useState('openai/gpt-image-2.6-flare')
  const [leave, setLeave] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [llmProvider, setLlmProvider] = useState('wavespeed')
  const [llmModel, setLlmModel] = useState('existing')
  const [llmNote, setLlmNote] = useState('')
  const [details, setDetails] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setForbidden(false)
    setError('')
    setNotice('')
    setLeave(false)
    loadProviderAdmin().then((next) => {
      setState(next)
      const first = next.tools[0]?.id || 'generate_image'
      setPicked(first)
      setDrafts(Object.fromEntries(next.tools.map((tool) => [tool.id, tool.active ? { ...tool.active, backup: tool.active.backup || null } : blank()])))
      const llm = next.llm.active
      setLlmProvider(llm?.provider || 'wavespeed')
      setLlmModel(llm?.model || 'existing')
    }).catch((e: unknown) => {
      if (e instanceof ProviderAdminError && e.status === 403) setForbidden(true)
      else setError(e instanceof Error ? e.message : String(e))
    }).finally(() => setLoading(false))
  }, [open])

  const absorb = (next: ProviderAdminState) => {
    setState(next)
    setDrafts(Object.fromEntries(next.tools.map((tool) => {
      const route = tool.active || tool.draft
      return [tool.id, route ? { primary: route.primary, backup: route.backup || null, fallback: route.fallback } : blank()]
    })))
  }
  const dirtyIds = useMemo(() => {
    if (!state) return []
    return state.tools.filter((tool) => routeKey(drafts[tool.id] || blank()) !== routeKey(tool.active || blank())).map((tool) => tool.id)
  }, [state, drafts])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      if (dirtyIds.length) setLeave(true)
      else setProviderAdminOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, dirtyIds])

  if (!open) return null
  const tools = state?.tools || []
  const shown = tools.filter((tool) => {
    const text = `${lt(tool.label)} ${tool.id}`.toLowerCase()
    if (query && !text.includes(query.trim().toLowerCase())) return false
    if (group !== 'all' && group !== 'llm' && tool.group !== group) return false
    return true
  })
  const current = tools.find((tool) => tool.id === picked) || shown[0]
  const draft = current ? drafts[current.id] || blank() : blank()
  const dirty = current ? dirtyIds.includes(current.id) : false

  const close = () => {
    if (dirtyIds.length) { setLeave(true); return }
    setProviderAdminOpen(false)
  }
  const move = (delta: number) => {
    const ids = shown.map((tool) => tool.id)
    const index = Math.max(0, ids.indexOf(picked))
    const next = ids[(index + delta + ids.length) % Math.max(ids.length, 1)]
    if (next) setPicked(next)
  }

  const saveOne = (activate: boolean) => {
    if (!current) return
    setBusy(true); setError(''); setNotice('')
    saveTool(current.id, { ...draft, activate }).then((next) => {
      absorb(next)
      const blocked = next.blocked === 'quote_unknown' || (next.usable === false && draft.primary.provider === 'replicate')
      setNotice(activate
        ? (blocked ? '' : tx('已启用。新的这个工具会走刚保存的线路。', 'Enabled. New runs of this tool use the saved route.'))
        : tx('草稿已记住，正在用的线路没有改。', 'Draft kept. The live route did not change.'))
    }).catch((e: unknown) => {
      setError(failText(e))
    }).finally(() => setBusy(false))
  }

  return (
    <div className="ca-prov" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) close() }}>
      <div
        className="ca-prov__sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="provider-title"
        data-testid="provider-admin"
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
          if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
        }}
      >
        <header className="ca-prov__head">
          <div>
            <h2 id="provider-title">{tx('供应商', 'Providers')}</h2>
            <p>{tx('每个工具各自一条线路。没改过的工具继续用现在的默认。', 'Each tool has its own route. Untouched tools keep today’s default.')}</p>
          </div>
          <button type="button" className="ca-prov__x" aria-label={tx('关闭', 'Close')} onClick={close}>×</button>
        </header>
        {!forbidden && (
          <div className="ca-prov__segs" role="tablist">
            {GROUPS.map(([id, zh, en]) => (
              <button key={id} type="button" role="tab" aria-selected={group === id} data-on={group === id || undefined} data-testid={`provider-group-${id}`} onClick={() => setGroup(id)}>{tx(zh, en)}</button>
            ))}
          </div>
        )}
        {loading && <p className="ca-prov__empty" data-testid="provider-loading">{tx('正在读取…', 'Loading…')}</p>}
        {forbidden && <p className="ca-prov__banner" role="alert" data-testid="provider-forbidden">{tx('只有管理员可以查看和修改。', 'Only an admin can view or change this.')}</p>}
        {!loading && !forbidden && state && group !== 'llm' && (
          <div className="ca-prov__body">
            <aside className="ca-prov__list">
              <input className="ca-prov__search" data-testid="provider-search" placeholder={tx('搜索工具', 'Search tools')} value={query} onChange={(e) => setQuery(e.target.value)} aria-label={tx('搜索工具', 'Search tools')} />
              <div className="ca-prov__tools" role="listbox" aria-label={tx('工具', 'Tools')} data-testid="provider-tools">
                {shown.length === 0 && <p className="ca-prov__empty" data-testid="provider-empty">{tx('没有找到这个工具。', 'No tool matches.')}</p>}
                {shown.map((tool) => (
                  <div key={tool.id} className="ca-prov__row" data-on={tool.id === current?.id || undefined}>
                    {tool.connected ? (
                      <button type="button" className="ca-prov__tick" role="checkbox" aria-checked={checked.includes(tool.id)} aria-label={lt(tool.label)} data-testid={`provider-check-${tool.id}`} data-on={checked.includes(tool.id) || undefined} onClick={() => setChecked(checked.includes(tool.id) ? checked.filter((id) => id !== tool.id) : [...checked, tool.id])} />
                    ) : <span className="ca-prov__tick ca-prov__tick--space" />}
                    <button type="button" role="option" aria-selected={tool.id === current?.id} data-testid={`provider-tool-${tool.id}`} onClick={() => setPicked(tool.id)}>
                      <strong>{lt(tool.label)}</strong>
                      <Status tool={tool} dirty={dirtyIds.includes(tool.id)} />
                    </button>
                  </div>
                ))}
              </div>
            </aside>
            {current && (
              <section className="ca-prov__edit" data-testid="provider-editor">
                <h3>{lt(current.label)}</h3>
                <p className="ca-prov__blurb">{lt(current.blurb)}</p>
                <p className="ca-prov__now" data-testid="provider-effective">
                  {tx('现在生效', 'Live now')}
                  <b>{liveText(current)}</b>
                </p>
                {!current.connected && <p className="ca-prov__quiet" data-testid="provider-unverified">{tx('这条先继续用 WaveSpeed。Replicate 还没接通，不是不能用。', 'This stays on WaveSpeed. Replicate is not wired yet, which is not the same as unusable.')}</p>}
                <div className="ca-prov__block">
                  <h4>{tx('主线路', 'Primary')}</h4>
                  <ChoiceList value={draft.primary} choices={current.choices} testId="provider-primary" onChange={(primary) => setDrafts({ ...drafts, [current.id]: { ...draft, primary } })} />
                </div>
                <div className="ca-prov__block">
                  <h4>{tx('备选', 'Backup')}</h4>
                  <ChoiceList
                    value={draft.backup || { provider: '', model: '' }}
                    choices={[{ provider: '', model: '', label: { zh: '不设备选', en: 'No backup' }, enabled: current.connected, quote: '', reason: current.connected ? '' : tx('还没有可接通的备选', 'No wired backup yet') }, ...current.choices.filter((choice) => !(choice.provider === draft.primary.provider && choice.model === draft.primary.model)).map((choice) => choice.backup === false ? { ...choice, enabled: false, reason: choice.backup_reason || choice.reason } : choice)]}
                    testId="provider-backup"
                    onChange={(backup) => setDrafts({ ...drafts, [current.id]: { ...draft, backup: backup.provider ? backup : null, fallback: backup.provider ? draft.fallback : false } })}
                  />
                </div>
                <label className="ca-prov__switch">
                  <button type="button" className="ca-switch" role="switch" aria-checked={draft.fallback} data-on={draft.fallback || undefined} data-testid="provider-fallback" disabled={!draft.backup} onClick={() => setDrafts({ ...drafts, [current.id]: { ...draft, fallback: !draft.fallback } })}><span /></button>
                  <span>{tx('主线路明确没受理时，自动试一次备选', 'If the primary clearly never created a task, try the backup once')}</span>
                </label>
                {dirty && <p className="ca-prov__impact" data-testid="provider-impact">{impact(current, draft)}</p>}
                {current.blocked === 'quote_unknown' && current.effective.source === 'saved' && <p className="ca-prov__banner" role="status" data-testid="provider-blocked">{tx('这条已保存，但价格未知，所以新任务会停住，不会扣费。保存成功不等于已经能用。', 'This is saved, but the price is unknown, so a new job stops and is not charged. Saved does not mean usable.')}</p>}
                {!current.key_ok && draft.primary.provider === 'replicate' && <p className="ca-prov__banner" data-testid="provider-nokey">{tx('还没有 Replicate 密钥。可以先留草稿，不能启用。', 'No Replicate key yet. You can keep a draft, but you cannot turn it on.')}</p>}
                {notice && <p className="ca-prov__banner" role="status" data-testid="provider-saved">{notice}</p>}
                {error && <p className="ca-prov__banner" role="alert" data-testid="provider-error">{error}</p>}
                <details className="ca-prov__more" data-testid="provider-details" onToggle={(e) => setDetails((e.target as HTMLDetailsElement).open)}>
                  <summary>{tx('什么时候会换、什么时候不会', 'When it switches, and when it does not')}</summary>
                  {details && <p>{tx('超时、已有任务号、内容没通过、价格对不上，都不会自动换。每次最多主一次、备一次。已接通的是 GPT Image 2.6。视频和其他工具保持原路。', 'Timeouts, an existing task id, a safety block, or a mismatched price will not switch. At most one primary try and one backup. Only GPT Image 2.6 is wired. Video and other tools stay put.')}</p>}
                </details>
              </section>
            )}
          </div>
        )}
        {!loading && !forbidden && state && group === 'llm' && (
          <LlmPane state={state} providerId={llmProvider} modelId={llmModel} note={llmNote} onProvider={setLlmProvider} onModel={setLlmModel} onNote={setLlmNote} onState={setState} />
        )}
        <footer className="ca-prov__foot">
          {leave ? (
            <>
              <span>{tx(`还有 ${dirtyIds.length} 个工具没保存。`, `${dirtyIds.length} tools are not saved.`)}</span>
              <button type="button" className="ca-prov__btn" onClick={() => setLeave(false)}>{tx('继续编辑', 'Keep editing')}</button>
              <button type="button" className="ca-prov__btn ca-prov__btn--primary" data-testid="provider-discard" onClick={() => { setLeave(false); setProviderAdminOpen(false) }}>{tx('放弃并关闭', 'Discard and close')}</button>
            </>
          ) : group === 'llm' ? (
            <span className="ca-prov__hint">{tx('语言模型和图像工具分开保存。', 'The language model is saved apart from the image tools.')}</span>
          ) : (
            <>
              {checked.length > 0 && (
                <div className="ca-prov__batch" data-testid="provider-batch">
                  <span data-testid="provider-batch-count">{tx(`已选 ${checked.length} 个可切换工具`, `${checked.length} switchable tools selected`)}</span>
                  <span className="ca-prov__batchpicks" role="group" aria-label={tx('批量主线路', 'Batch primary')}>
                    <button type="button" data-on={batchModel.endsWith('flare') || undefined} onClick={() => setBatchModel('openai/gpt-image-2.6-flare')}>Flare</button>
                    <button type="button" data-on={batchModel.endsWith('sunburst') || undefined} onClick={() => setBatchModel('openai/gpt-image-2.6-sunburst')}>Sunburst</button>
                  </span>
                  <span className="ca-prov__hint">{tx('只改这些工具的主线路，不碰没选中的，也不改它们的备选。', 'Only these tools’ primary route changes. Unselected tools and backups stay.')}</span>
                  <button type="button" className="ca-prov__btn" data-testid="provider-batch-apply" disabled={busy} onClick={() => {
                    setBusy(true); setError('')
                    saveToolBatch({ ids: checked, primary: { provider: 'replicate', model: batchModel }, backup: null, fallback: false, activate: true }).then((next) => {
                      absorb(next)
                      setChecked([])
                      setNotice(next.usable ? tx('所选工具已启用。', 'Selected tools are on.') : tx(`已保存 ${next.applied?.length || checked.length} 个。价格未知，这些新任务会停住，不会扣费。没选中的工具没变。`, `Saved ${next.applied?.length || 0}. Price unknown, so those new jobs stop and are not charged. Unselected tools are unchanged.`))
                    }).catch((e: unknown) => setError(failText(e))).finally(() => setBusy(false))
                  }}>{tx('保存所选', 'Save selected')}</button>
                </div>
              )}
              <div className="ca-prov__bar">
              <button type="button" className="ca-prov__btn" data-testid="provider-restore" disabled={!current?.can_restore || busy} onClick={() => current && restoreTool(current.id).then((next) => { absorb(next); setNotice(tx('已回到这个工具的上一份。别的工具没动。', 'Restored this tool’s previous setup. Other tools are untouched.')) }).catch((e: unknown) => setError(failText(e)))}>{tx('恢复这个工具', 'Restore this tool')}</button>
              <button type="button" className="ca-prov__btn" disabled={!dirty || busy} data-testid="provider-draft" onClick={() => saveOne(false)}>{tx('只留草稿', 'Keep draft')}</button>
              <button type="button" className="ca-prov__btn ca-prov__btn--primary" data-testid="provider-save" disabled={!dirty || busy || (draft.primary.provider === 'replicate' && !current?.key_ok)} onClick={() => saveOne(true)}>{busy ? tx('正在保存', 'Saving') : tx('保存并启用', 'Save and turn on')}</button>
              </div>
            </>
          )}
        </footer>
      </div>
    </div>
  )
}

function Status({ tool, dirty }: { tool: ToolRow; dirty: boolean }) {
  if (dirty) return <span className="ca-prov__chip" data-state="draft">{tx('未保存', 'Unsaved')}</span>
  if (tool.effective.source === 'default') return <span className="ca-prov__chip">{tx('默认', 'Default')}</span>
  if (tool.blocked) return <span className="ca-prov__chip" data-state="blocked">{tx('不能生成', 'Blocked')}</span>
  return <span className="ca-prov__chip" data-state="live">{tool.effective.provider === 'replicate' ? 'Replicate' : 'WaveSpeed'}</span>
}

function providerName(provider: string) {
  if (provider === 'replicate') return 'Replicate'
  if (provider === 'wavespeed') return 'WaveSpeed'
  return provider
}

function liveText(tool: ToolRow) {
  if (tool.effective.source === 'default') return tx('WaveSpeed，系统默认', 'WaveSpeed, the system default')
  const name = providerName(tool.effective.provider)
  const extra = tool.effective.backup
    ? (tool.effective.fallback ? tx('，没受理时会试备选', ', backup will be tried') : tx('，备选已设但不会自动换', ', backup is set and stays manual'))
    : ''
  return `${name} · ${shortModel(tool.effective.model)}${extra}`
}

function shortModel(model: string) {
  if (model === 'existing') return tx('现有模型', 'current model')
  if (model.endsWith('flare')) return 'Flare'
  if (model.endsWith('sunburst')) return 'Sunburst'
  return model
}

function impact(tool: ToolRow, draft: ToolRoute) {
  const now = tool.active || blank()
  const bits = [tx('保存后只影响这个工具的新任务。', 'After saving, only new runs of this tool change.')]
  if (!same(now.primary, draft.primary)) bits.push(tx(`主线路改为 ${providerName(draft.primary.provider)}。`, `Primary becomes ${providerName(draft.primary.provider)}.`))
  if (!same(now.backup, draft.backup)) bits.push(draft.backup ? tx('备选已设置。', 'A backup is set.') : tx('去掉备选。', 'Backup removed.'))
  if (now.fallback !== draft.fallback) bits.push(draft.fallback ? tx('兜底会打开。', 'Fallback will turn on.') : tx('兜底会关掉。', 'Fallback will turn off.'))
  if (draft.primary.provider === 'replicate') bits.push(tx('价格未知，启用后新任务会停住。', 'Price unknown. After turning it on, a new job stops.'))
  return bits.join(' ')
}

function ChoiceList({ value, choices, onChange, testId }: { value: EndPoint; choices: ToolChoice[]; onChange: (value: EndPoint) => void; testId: string }) {
  return (
    <div className="ca-prov__picks" data-testid={testId}>
      {choices.map((choice) => {
        const on = choice.provider === value.provider && choice.model === value.model
        return (
          <button key={`${choice.provider}:${choice.model}`} type="button" disabled={!choice.enabled} data-on={on || undefined} onClick={() => onChange({ provider: choice.provider, model: choice.model })}>
            <i />
            <span>{lt(choice.label)}</span>
            {choice.quote === 'unknown' && choice.enabled && <small>{tx('价格未知', 'Price unknown')}</small>}
            {!choice.enabled && choice.reason && <small>{choice.reason}</small>}
          </button>
        )
      })}
    </div>
  )
}

function LlmPane({ state, providerId, modelId, note, onProvider, onModel, onNote, onState }: {
  state: ProviderAdminState
  providerId: string
  modelId: string
  note: string
  onProvider: (id: string) => void
  onModel: (id: string) => void
  onNote: (text: string) => void
  onState: (state: ProviderAdminState) => void
}) {
  const info = state.llm.providers.find((item) => item.id === providerId)
  const model = info?.models.find((item) => item.id === modelId)
  const dirty = providerId !== (state.llm.active?.provider || 'wavespeed') || modelId !== (state.llm.active?.model || 'existing')
  return (
    <section className="ca-prov__edit ca-prov__llm" data-testid="provider-llm">
      <h3>{tx('语言模型', 'Language model')}</h3>
      <p className="ca-prov__now" data-testid="provider-llm-status">{tx('现在生效', 'Live now')} <b>{state.llm.active ? `${state.llm.active.provider} · ${state.llm.active.model}` : tx('WaveSpeed · deepseek/deepseek-v4.1-flash-1017', 'WaveSpeed · deepseek/deepseek-v4.1-flash-1017')}</b></p>
      <div className="ca-prov__picks" data-testid="provider-llm-providers">
        {state.llm.providers.map((provider) => (
          <button key={provider.id} type="button" data-on={provider.id === providerId || undefined} data-testid={`provider-llm-${provider.id}`} onClick={() => { onProvider(provider.id); onModel(provider.models[0]?.id || 'existing'); onNote('') }}>
            <span>{lt(provider.label)}</span>
            <small>{provider.configured || provider.mode === 'existing' ? tx('密钥可用', 'Key available') : tx('密钥未配置', 'Key missing')}</small>
          </button>
        ))}
      </div>
      <div className="ca-prov__picks">
        {(info?.models || []).map((item) => (
          <button key={item.id} type="button" data-on={item.id === modelId || undefined} onClick={() => { onModel(item.id); onNote('') }}><span>{lt(item.label)}</span></button>
        ))}
      </div>
      {info?.base_url && <p className="ca-prov__hint" data-testid="provider-llm-base">{tx('地址', 'Endpoint')} {info.base_url}</p>}
      {model && !model.passthrough && <p className="ca-prov__hint">{lt(model.note)}</p>}
      {dirty && <p className="ca-prov__impact">{tx('还没保存。检查和保存都不会改正在进行的对话。', 'Not saved. Checking or saving does not change a chat already running.')}</p>}
      {note && <p className="ca-prov__banner" role="status" data-testid="provider-llm-check-result">{note}</p>}
      <div className="ca-prov__actions">
        <button type="button" className="ca-prov__btn" data-testid="provider-llm-check" onClick={() => {
          checkLlm({ provider: providerId, model: modelId }).then((result) => onNote(result.message || tx('未调用。', 'No call.'))).catch((e: unknown) => onNote(String(e)))
        }}>{tx('检查草稿', 'Check draft')}</button>
        <button type="button" className="ca-prov__btn ca-prov__btn--primary" data-testid="provider-llm-save" disabled={!dirty || (providerId === 'deepseek' && !info?.configured)} title={!info?.configured && providerId === 'deepseek' ? tx('还没有官方密钥，不能启用', 'No official key, so this cannot be turned on') : undefined} onClick={() => {
          saveLlmProvider({ provider: providerId, model: modelId }).then((next) => { onState(next); onNote(tx('语言模型已保存。图像工具没变。', 'Language model saved. Image tools are unchanged.')) }).catch((e: unknown) => onNote(String(e)))
        }}>{tx('保存语言模型', 'Save language model')}</button>
        <button type="button" className="ca-prov__btn" disabled={!state.llm.can_restore} onClick={() => restoreLlmProvider().then((next) => { onState(next); onNote(tx('语言模型已恢复。', 'Language model restored.')) })}>{tx('恢复', 'Restore')}</button>
      </div>
    </section>
  )
}
