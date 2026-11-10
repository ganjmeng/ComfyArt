import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useValue } from 'tldraw'

import { BUILTIN_AGENT, botEnabledAtom, listLocalLlmModels, llmSourceAtom, providerLabel, providersAtom, refreshBot, saveSettings, settingsAtom, testLocalLlm, type BotSettings as Settings, type LocalLlmTestCode, type ProviderInfo } from '../bot'
import { errorText } from '../jobs'
import { agentSetupFocusAtom, botSettingsOpenAtom, pendingLlmModeAtom } from './AgentPicker'
import { docsUrl } from './SettingsMenu'
import { FieldSelect } from './FieldSelect'
import { LlmModelSelect } from './LlmModelSelect'
import { inferLlmProvider, LLM_PROVIDERS, pickDefaultModel, providerById, providerLabel as byoProviderLabel, type LlmProviderId } from './llmProviders'
import { AgentLogo } from './agentLogos'
import { Icons } from './icons'
import { Modal } from './Modal'
import { Popover } from './Popover'
import { t } from '../i18n'
import deepseekMark from '../assets/agents/deepseek.svg'

// #219: the built-in agent's endpoint, model and key; the key is a password field and comes back masked
const TEXT_FIELDS: [string, string, string, ('text' | 'password')?][] = [
  ['bot-local-llm-url', t('botSettings.localLlmUrl'), t('botSettings.localLlmUrlHint')],
  ['bot-model-local-llm', t('botSettings.localLlmModel'), t('botSettings.localLlmModelHint')],
  ['bot-local-llm-key', t('botSettings.localLlmKey'), t('botSettings.localLlmKeyHint'), 'password'],
  ['bot-comfy-mcp-command', t('botSettings.comfyMcpCommand'), t('botSettings.leaveEmptyToFindComfy')],
]
const SWITCHES: [string, string][] = [
  ['enable-mcp', t('botSettings.enableMcpLetTheAgent')],
  ['enable-bot', t('botSettings.enableAgentUseCommandLine')],
]
const FLAGS: [string, string][] = [
  ['bot-enable-comfy-mcp', t('botSettings.alsoMountTheOfficialComfy')],
]

const URL_KEY = 'bot-local-llm-url'
const KEY_KEY = 'bot-local-llm-key'
const MODEL_KEY = 'bot-model-local-llm'
const WAVESPEED_HOST = 'llm.wavespeed.ai'
const hostOf = (url: unknown) => { try { return new URL(String(url ?? '').trim()).hostname.toLowerCase() } catch { return '' } }
const DEFAULT_URL = 'https://llm.wavespeed.ai/v1'
const DEFAULT_MODEL = 'deepseek/deepseek-v4.1-flash-1017'
const normLlm = (v: unknown) => String(v ?? '').trim().replace(/\/+$/, '')
const valuesAreCustom = (s: Settings) => normLlm(s[URL_KEY]) !== normLlm(DEFAULT_URL) || normLlm(s[MODEL_KEY]) !== normLlm(DEFAULT_MODEL)
const modeOf = (s: Settings): 'official' | 'custom' => {
  const m = String(s.llm_mode ?? '').trim()
  if (m === 'official' || m === 'custom') return m
  return valuesAreCustom(s) ? 'custom' : 'official'
}

const TEST_MSG: Record<LocalLlmTestCode, (model?: string) => string> = {
  ok: () => t('botSettings.testOk'),
  no_url: () => t('botSettings.enterUrlFirst'),
  unreachable: () => t('botSettings.testUnreachable'),
  auth_failed: () => t('botSettings.testAuthFailed'),
  model_missing: (model) => t('botSettings.testModelMissing', model || ''),
  timeout: () => t('botSettings.testTimeout'),
}

function failCopyOf(code: LocalLlmTestCode, status?: number): string {
  const failCopy = ({ unreachable: t('botSettings.customLlmFailHost'), auth_failed: t('botSettings.customLlmFailAuth'), timeout: t('botSettings.customLlmFailTimeout') } as Partial<Record<LocalLlmTestCode, string>>)[code]
  const httpCopy = code === 'unreachable' && Number(status) >= 400 ? t('botSettings.customLlmFailHttp', String(status)) : ''
  return httpCopy || failCopy || TEST_MSG[code]()
}

function ProviderMark({ id }: { id: string }) {
  const p = providerById(id)
  if (p.id === 'deepseek') return <img className="ca-llm-mark ca-llm-mark--img" src={deepseekMark} alt="" />
  return <span className="ca-llm-mark" aria-hidden="true">{p.mark}</span>
}

function ProviderSelect({ value, onChange }: { value: LlmProviderId; onChange: (id: LlmProviderId) => void }) {
  const [open, setOpen] = useState(false)
  const selected = byoProviderLabel(value)
  return (
    <div className="ca-fieldselect-wrap ca-llm-provider" data-testid="llm-provider">
      <Popover open={open} onOpenChange={setOpen} side="bottom" align="start" trigger={({ open: o, toggle }) => (
        <button type="button" className="ca-fieldselect ca-llm-provider__trigger" data-open={o || undefined} onClick={toggle} onKeyDown={(e) => e.stopPropagation()}>
          <ProviderMark id={value} />
          <span className="ca-fieldselect__text">{selected}</span>
          <span className="ca-icon">{Icons.chevron}</span>
        </button>
      )}>
        <div className="ca-menu ca-fieldselect__menu">
          {LLM_PROVIDERS.map((p) => (
            <button
              key={p.id}
              type="button"
              className="ca-menu__item"
              data-on={value === p.id || undefined}
              onClick={() => { onChange(p.id); setOpen(false) }}
            >
              <ProviderMark id={p.id} />
              <span className="ca-menu__grow">{byoProviderLabel(p.id)}</span>
              {value === p.id && <span className="ca-icon">{Icons.check}</span>}
            </button>
          ))}
        </div>
      </Popover>
    </div>
  )
}

export function BotSettings({ onError }: { onError: (msg: string) => void }) {
  const open = useValue(botSettingsOpenAtom)
  const settings = useValue(settingsAtom)
  const providers = useValue(providersAtom)
  const enabled = useValue(botEnabledAtom)
  const llmSource = useValue(llmSourceAtom)
  const [draft, setDraft] = useState<Settings>({})
  const [testing, setTesting] = useState(false)
  const [testState, setTestState] = useState<{ ok: boolean; text: string } | null>(null)
  const [modeOverride, setModeOverride] = useState<'official' | 'custom' | null>(null)
  const [provider, setProvider] = useState<LlmProviderId>('wavespeed')
  const [urlEditable, setUrlEditable] = useState(false)
  const [models, setModels] = useState<string[]>([])
  const [listState, setListState] = useState<{ loading: boolean; typable: boolean; text: string }>({ loading: false, typable: false, text: '' })
  const fetchSeq = useRef(0)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const hostChanged = hostOf(draft[URL_KEY]) !== hostOf(settings[URL_KEY])
  const keyCleared = hostChanged && !!settings[KEY_KEY] && hostOf(draft[URL_KEY]) !== WAVESPEED_HOST
  const edit = (key: string, value: string) => {
    const next = { ...draft, [key]: value }
    if (key === URL_KEY && hostOf(value) !== hostOf(settings[URL_KEY]) && draft[KEY_KEY] === settings[KEY_KEY]) next[KEY_KEY] = ''
    if (key === URL_KEY && hostOf(value) === hostOf(settings[URL_KEY])) next[KEY_KEY] = settings[KEY_KEY] ?? ''
    setDraft(next)
    setTestState(null)
  }

  useEffect(() => {
    if (!open) {
      setModeOverride(null)
      return
    }
    void refreshBot().catch((e) => onError(errorText(e)))
  }, [open])

  // Hydrate from saved settings when the dialog opens or when saved settings
  // actually change (save / refresh). Do not depend on modeOverride: setMode
  // already writes llm_mode onto the current draft and must keep unsaved URL /
  // provider / model / Key (AC12). Cancel clears modeOverride; the next open
  // runs this effect and shows the previously saved settings.
  useEffect(() => {
    if (!open) return
    const next = { ...settings } as Settings
    const pending = pendingLlmModeAtom.get()
    if (pending === 'official' || pending === 'custom') {
      setModeOverride(pending)
      pendingLlmModeAtom.set(null)
      next.llm_mode = pending
    } else if (modeOverride) {
      next.llm_mode = modeOverride
    }
    setDraft(next)
    setTestState(null)
    const inferred = inferLlmProvider(String(next[URL_KEY] ?? ''), String(next.llm_provider ?? ''))
    setProvider(inferred)
    const preset = providerById(inferred).url
    const current = String(next[URL_KEY] ?? '')
    setUrlEditable(inferred === 'custom' || (!!normLlm(current) && normLlm(current) !== normLlm(preset)))
    setModels(String(next[MODEL_KEY] ?? '').trim() ? [String(next[MODEL_KEY])] : [])
    setListState({ loading: false, typable: false, text: '' })
    // modeOverride is applied only while hydrating from saved settings, not as a trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, settings])

  const managed = llmSource.source === 'admin'
  const mode = modeOverride ?? modeOf(draft)
  const officialDisplayName = String(settings.official_llm_display_name ?? '')
  const officialReady = settings.official_llm_ready === true
  const hasCustomConfig = valuesAreCustom(draft) || Boolean(String(draft[KEY_KEY] ?? '').trim())
  const draftUrl = String(draft[URL_KEY] ?? '')
  const draftKey = String(draft[KEY_KEY] ?? '')
  const providerChosen = Boolean(provider)
  const urlFilled = Boolean(draftUrl.trim())
  const keyOptional = provider === 'wavespeed' || provider === 'ollama'
  const keyFilled = Boolean(draftKey.trim()) || keyOptional
  const modelReady = !!String(draft[MODEL_KEY] ?? '').trim()
  const incomplete = !providerChosen || !urlFilled || !keyFilled || !modelReady
  const notSetupCopy = (!providerChosen || !urlFilled || !keyFilled)
    ? t('botSettings.customLlmNotSetup')
    : t('botSettings.customLlmNotSetupModel')
  const testFailed = !!(testState && !testState.ok)

  const fetchModels = () => {
    const url = draftUrl.trim()
    if (!url) {
      setListState({ loading: false, typable: true, text: t('botSettings.enterUrlFirst') })
      return
    }
    const seq = ++fetchSeq.current
    setListState((s) => ({ ...s, loading: true, text: '' }))
    void listLocalLlmModels({ url, key: draftKey }).then((r) => {
      if (seq !== fetchSeq.current) return
      const ids = (r.models ?? []).map((m) => m.id).filter(Boolean)
      if (r.ok) {
        setModels(ids)
        const picked = pickDefaultModel({ saved: String(draft[MODEL_KEY] ?? ''), ids, provider })
        if (picked && picked !== String(draft[MODEL_KEY] ?? '')) edit(MODEL_KEY, picked)
        setListState({ loading: false, typable: false, text: '' })
      } else {
        const code = (r.code in TEST_MSG ? r.code : 'unreachable') as LocalLlmTestCode
        setListState({ loading: false, typable: true, text: `${failCopyOf(code, r.status)}\n${t('botSettings.fetchModelsFailed')}` })
      }
    }).catch(() => {
      if (seq !== fetchSeq.current) return
      setListState({ loading: false, typable: true, text: t('botSettings.fetchModelsFailed') })
    })
  }

  useEffect(() => {
    if (!open || managed || mode !== 'custom') return
    if (!draftUrl.trim()) return
    if (!(draftKey.trim() || provider === 'wavespeed' || provider === 'ollama')) return
    fetchModels()
    // Auto-fetch on open / source / provider change only — not on every URL or key keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, managed, mode, provider])

  if (!open) return null
  const close = () => { setModeOverride(null); botSettingsOpenAtom.set(false) }
  const save = () => void saveSettings({
    ...draft,
    llm_mode: modeOf({ ...draft, llm_mode: modeOverride ?? draft.llm_mode }),
    llm_provider: provider,
  }).then(() => refreshBot()).then(close).catch((e) => onError(errorText(e)))
  const testConnection = () => {
    if (testing || !modelReady) return
    setTesting(true)
    setTestState(null)
    void testLocalLlm({
      url: draftUrl,
      key: draftKey,
      model: String(draft[MODEL_KEY] ?? ''),
    }).then((r) => {
      const code = (r.code in TEST_MSG ? r.code : 'unreachable') as LocalLlmTestCode
      const selected = String(draft[MODEL_KEY] ?? '').trim()
      setTestState({
        ok: !!r.ok,
        text: r.ok
          ? (selected ? t('botSettings.testOkWithModel', selected) : t('botSettings.testOk'))
          : failCopyOf(code, r.status),
      })
    }).catch(() => {
      setTestState({ ok: false, text: t('botSettings.testFailed') })
    }).finally(() => setTesting(false))
  }
  const setMode = (id: 'official' | 'custom') => {
    if (managed) return
    setModeOverride(id)
    setDraft({ ...draft, llm_mode: id })
    if (id === 'official') setTestState(null)
  }
  const changeProvider = (id: LlmProviderId) => {
    const prevPreset = providerById(provider).url
    const current = draftUrl
    const keep = !!normLlm(current) && normLlm(current) !== normLlm(prevPreset)
    const nextUrl = keep ? current : providerById(id).url
    setProvider(id)
    const next = { ...draft, llm_provider: id, [URL_KEY]: nextUrl } as Settings
    if (hostOf(nextUrl) !== hostOf(settings[URL_KEY]) && draft[KEY_KEY] === settings[KEY_KEY]) next[KEY_KEY] = ''
    if (hostOf(nextUrl) === hostOf(settings[URL_KEY])) next[KEY_KEY] = settings[KEY_KEY] ?? ''
    setDraft(next)
    setUrlEditable(id === 'custom' || keep)
    setTestState(null)
    setListState({ loading: false, typable: false, text: '' })
  }

  return (
    <Modal className="ca-botsettings" title={t('botSettings.agentSettings')} onClose={close}>
      <div className="ca-rename__body">
        <section className="ca-botsettings__section" data-testid="botsettings-builtin">
          <div className="ca-botsettings__sectiontitle">{t('botSettings.builtinAgent')}</div>
          {!managed && <div className="ca-chat__hint">{t('botSettings.builtinAgentHint')}</div>}
          {managed ? (
            <>
              <div className="ca-botsettings__adminnotice" data-testid="llm-source">
                {t('botSettings.llmManagedByAdmin')}
              </div>
              <label className="ca-rename__field">
                <span>{t('botSettings.localLlmUrl')}</span>
                <input className="ca-panel__input" type="text" autoComplete="off" readOnly value={llmSource.url || ''} onKeyDown={(e) => e.stopPropagation()} />
              </label>
              <label className="ca-rename__field">
                <span>{t('botSettings.localLlmModel')}</span>
                <input className="ca-panel__input" type="text" autoComplete="off" readOnly value={llmSource.model || ''} onKeyDown={(e) => e.stopPropagation()} />
              </label>
              <div className="ca-botsettings__adminkey" data-testid="llm-admin-key">{t('botSettings.llmKeyProvidedByAdmin')}</div>
            </>
          ) : (
            <>
              <div className="ca-botsettings__sourcecards" role="radiogroup" aria-label={t('botSettings.llmModeOfficial')} data-testid="llm-mode">
                {(['official', 'custom'] as const).map((id) => (
                  <button
                    key={id}
                    type="button"
                    role="radio"
                    aria-checked={mode === id}
                    data-on={mode === id || undefined}
                    data-err={(id === 'custom' && testFailed) || undefined}
                    data-testid={`llm-mode-${id}`}
                    className="ca-botsettings__sourcecard"
                    onClick={() => setMode(id)}
                  >
                    <span className="ca-botsettings__sourceicon" aria-hidden="true">{id === 'official' ? Icons.agent : Icons.key}</span>
                    <span className="ca-botsettings__sourcecopy">
                      <span className="ca-botsettings__sourcetitle">
                        {id === 'official' ? t('botSettings.llmModeOfficial') : t('botSettings.llmModeCustom')}
                        {id === 'custom' && testFailed && <span className="ca-botsettings__errdot" aria-hidden="true" />}
                      </span>
                      <span className="ca-botsettings__sourcesub">{id === 'official' ? t('botSettings.llmModeOfficialSub') : t('botSettings.llmModeCustomSub')}</span>
                    </span>
                  </button>
                ))}
              </div>
              {mode === 'official' && (
                <>
                  {officialReady ? (
                    <div className="ca-botsettings__officialnotice" data-testid="llm-official-notice">{t('botSettings.llmOfficialNotice', officialDisplayName)}</div>
                  ) : (
                    <div className="ca-botsettings__notsetup" role="status" data-testid="llm-official-not-ready">{t('botSettings.llmOfficialNotReady')}</div>
                  )}
                  {hasCustomConfig && officialReady && (
                    <div className="ca-botsettings__customkept" data-testid="llm-custom-kept">{t('botSettings.llmCustomKept')}</div>
                  )}
                </>
              )}
              {mode === 'custom' && incomplete && (
                <div className="ca-botsettings__notsetup" role="status" data-testid="llm-custom-not-setup">{notSetupCopy}</div>
              )}
              {mode === 'custom' && (
                <>
                  <label className="ca-rename__field">
                    <span>{t('botSettings.llmProvider')}</span>
                    <ProviderSelect value={provider} onChange={changeProvider} />
                  </label>
                  <label className="ca-rename__field">
                    <span className="ca-botsettings__fieldhead">
                      <span>{t('botSettings.localLlmUrl')}</span>
                      {provider !== 'custom' && !urlEditable && (
                        <button type="button" className="ca-botsettings__fieldlink" data-testid="llm-use-custom-url" onClick={() => setUrlEditable(true)}>{t('botSettings.useCustomUrl')}</button>
                      )}
                    </span>
                    <input
                      className="ca-panel__input"
                      type="text"
                      autoComplete="off"
                      readOnly={provider !== 'custom' && !urlEditable}
                      value={draftUrl}
                      placeholder={provider === 'custom' ? t('botSettings.localLlmUrlHint') : undefined}
                      onChange={(e) => edit(URL_KEY, e.target.value)}
                      onBlur={() => { if (mode === 'custom' && draftUrl.trim()) fetchModels() }}
                      onKeyDown={(e) => e.stopPropagation()}
                    />
                    {provider === 'custom' && <span className="ca-adv__help">{t('botSettings.localLlmUrlHint')}</span>}
                  </label>
                  <label className="ca-rename__field">
                    <span>{t('botSettings.localLlmKey')}</span>
                    <input
                      className="ca-panel__input"
                      type="password"
                      autoComplete="off"
                      value={draftKey}
                      placeholder={provider === 'wavespeed' ? t('botSettings.localLlmKeyHint') : undefined}
                      onChange={(e) => edit(KEY_KEY, e.target.value)}
                      onBlur={() => { if (mode === 'custom' && draftUrl.trim()) fetchModels() }}
                      onKeyDown={(e) => e.stopPropagation()}
                    />
                    {keyCleared && !draft[KEY_KEY] && <span className="ca-adv__help">{t('botSettings.urlChangedReenterKey')}</span>}
                    {provider === 'wavespeed' && <span className="ca-adv__help">{t('botSettings.localLlmKeyHint')}</span>}
                  </label>
                  <label className="ca-rename__field">
                    <span className="ca-botsettings__fieldhead">
                      <span>{t('botSettings.localLlmModel')}</span>
                      <button type="button" className="ca-botsettings__fieldlink" data-testid="llm-fetch-models" disabled={listState.loading} onClick={fetchModels}>
                        {models.length || listState.typable ? t('botSettings.refetchModels') : t('botSettings.fetchModels')}
                      </button>
                    </span>
                    <LlmModelSelect
                      value={String(draft[MODEL_KEY] ?? '')}
                      models={models}
                      typable={listState.typable}
                      loading={listState.loading}
                      onChange={(id) => edit(MODEL_KEY, id)}
                    />
                    {listState.typable && listState.text && (
                      <span className="ca-botsettings__listerr" role="status">{listState.text}</span>
                    )}
                    {!listState.typable && !listState.loading && models.length > 100 && (
                      <span className="ca-adv__help">{t('botSettings.modelCountHint', String(models.length))}</span>
                    )}
                  </label>
                  <div className="ca-botsettings__test" data-testid="local-llm-test">
                    <button type="button" className="ca-panel__secondary" disabled={testing || !modelReady} onClick={testConnection}>
                      {testing ? t('botSettings.testing') : t('botSettings.testConnection')}
                    </button>
                    {!modelReady && <span className="ca-botsettings__testmsg">{t('botSettings.chooseModelFirst')}</span>}
                    {testState && (
                      <span className="ca-botsettings__testmsg" data-ok={testState.ok || undefined} data-err={!testState.ok || undefined} role="status">
                        {testState.text}
                      </span>
                    )}
                    {testFailed && !incomplete && (
                      <button
                        type="button"
                        className="ca-panel__secondary ca-botsettings__switchback"
                        data-testid="use-official-llm"
                        onClick={() => setMode('official')}
                      >
                        {t('botSettings.useOfficialDefault')}
                      </button>
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </section>

        <section className="ca-botsettings__section" data-testid="botsettings-review">
          <label className="ca-notice__push" data-testid="bot-enable-review">
            <input
              type="checkbox"
              checked={draft['bot-enable-review'] !== false}
              onChange={(e) => setDraft({ ...draft, 'bot-enable-review': e.target.checked })}
            />
            <span>{t('botSettings.review')}</span>
          </label>
          <div className="ca-chat__hint">{t('botSettings.reviewDesc')}</div>
        </section>

        <AgentSetup providers={providers} enabled={enabled} onError={onError} draft={draft} edit={edit}>
          {SWITCHES.map(([key, label]) => (
            <label key={key} className="ca-notice__push">
              <input type="checkbox" checked={!!draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })} />
              <span>{label}</span>
            </label>
          ))}
        </AgentSetup>

        <section className="ca-botsettings__section" data-testid="botsettings-advanced">
          <button
            type="button"
            className="ca-botsettings__advtoggle"
            aria-expanded={advancedOpen}
            onClick={() => setAdvancedOpen((v) => !v)}
          >
            <span className="ca-botsettings__sectiontitle">{t('botSettings.advanced')}</span>
            <span className="ca-icon" data-flip={advancedOpen || undefined}>{Icons.chevron}</span>
          </button>
          {advancedOpen && (
            <div className="ca-botsettings__advbody">
              {TEXT_FIELDS.filter(([key]) => key === 'bot-comfy-mcp-command').map(([key, label, hint, type]) => (
                <label key={key} className="ca-rename__field">
                  <span>{label}</span>
                  <input className="ca-panel__input" type={type ?? 'text'} autoComplete="off" value={String(draft[key] ?? '')} placeholder={hint} onChange={(e) => edit(key, e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
                </label>
              ))}
              {FLAGS.map(([key, label]) => (
                <label key={key} className="ca-notice__push">
                  <input type="checkbox" checked={!!draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })} />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          )}
        </section>

        <label className="ca-rename__field">
          <span>{t('botSettings.ocrEngine')}</span>
          <FieldSelect
            value={String(draft['ocr-engine'] ?? 'local')}
            options={[
              { id: 'local', label: t('botSettings.ocrLocal') },
              { id: 'agent', label: t('botSettings.ocrAgent') },
            ]}
            onChange={(id) => setDraft({ ...draft, 'ocr-engine': id })}
          />
        </label>
      </div>
      <div className="ca-panel__foot">
        {managed ? (
          <button type="button" className="ca-panel__secondary" data-testid="botsettings-close" onClick={close}>{t('common.close')}</button>
        ) : (
          <>
            <button type="button" className="ca-panel__secondary" onClick={close}>{t('common.cancel')}</button>
            <button type="button" className="ca-panel__primary" onClick={save}>{t('common.save')}</button>
          </>
        )}
      </div>
    </Modal>
  )
}

// #247: setup guide for each external agent tool the backend knows about (no new tools here).
// Install links go to each tool's official docs only; we never write install commands ourselves.
export const AGENT_DOCS: Record<string, string> = {
  'claude-code': 'https://docs.claude.com/en/docs/claude-code/overview',
  codex: 'https://developers.openai.com/codex/cli',
  'qwen-code': 'https://github.com/QwenLM/qwen-code',
  'deepseek-harness': 'https://www.npmjs.com/package/@deepseek-ai/dsh',
  hermes: 'https://hermes-agent.nousresearch.com/docs/getting-started/installation',
}
export const AGENT_GUIDE_PATH = '/guides/external-agents'
export const mcpConfig = (origin: string) => JSON.stringify({ mcpServers: { comfyart: { type: 'http', url: `${origin}/comfyart/mcp` } } }, null, 2)

function AgentSetup({ providers, enabled, onError, draft, edit, children }: {
  providers: ProviderInfo[]
  enabled: boolean | null
  onError: (msg: string) => void
  draft: Settings
  edit: (key: string, value: string) => void
  children?: ReactNode
}) {
  const [copied, setCopied] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const config = mcpConfig(location.origin)
  const guide = `${docsUrl()}${AGENT_GUIDE_PATH}`
  const copy = (id: string) => void navigator.clipboard?.writeText(config).then(() => { setCopied(id); setTimeout(() => setCopied(null), 1500) }).catch(() => {})
  const focus = useValue(agentSetupFocusAtom)
  useEffect(() => {
    if (!focus) return
    document.querySelector(`.ca-agentsetup__card[data-agent="${focus}"]`)?.scrollIntoView({ block: 'start' })
    agentSetupFocusAtom.set(null)
  }, [focus, providers.length])
  const check = () => { setChecking(true); void refreshBot({ refresh: true }).catch((e) => onError(errorText(e))).finally(() => setChecking(false)) }
  return (
    <section className="ca-agentsetup ca-botsettings__section" data-testid="agent-setup">
      <div className="ca-botsettings__sectiontitle">{t('agentSetup.title')}</div>
      <div className="ca-chat__hint">{t('agentSetup.desc')}</div>
      {children}
      {!enabled && <div className="ca-chat__hint">{t('botSettings.availableAgentsOnThisMachine')}</div>}
      {providers.filter((p) => p.id !== BUILTIN_AGENT).map((p) => (
        <div key={p.id} className="ca-agentsetup__card" data-agent={p.id}>
          <div className="ca-agentsetup__head">
            <span className="ca-agentsetup__name"><AgentLogo id={p.id} />{providerLabel(p)}</span>
            <span className="ca-agentsetup__chip" data-on={p.available || undefined} title={p.detail || p.version}>{p.available ? t('agentSetup.connected') : t('agentPicker.notDetected')}</span>
          </div>
          {p.id === 'hermes' && (
            <div className="ca-agentsetup__hermes" data-testid="hermes-settings">
              <label className="ca-rename__field">
                <span>{t('botSettings.hermesSshHost')}</span>
                <textarea
                  className="ca-panel__input ca-agentsetup__hermes-hint"
                  rows={2}
                  autoComplete="off"
                  value={String(draft['bot-hermes-ssh-host'] ?? '')}
                  placeholder={t('botSettings.hermesSshHostHint')}
                  onChange={(e) => edit('bot-hermes-ssh-host', e.target.value)}
                  onKeyDown={(e) => e.stopPropagation()}
                />
              </label>
              <label className="ca-rename__field">
                <span>{t('botSettings.hermesProfile')}</span>
                <input
                  className="ca-panel__input"
                  type="text"
                  autoComplete="off"
                  value={String(draft['bot-hermes-profile'] ?? '')}
                  placeholder={t('botSettings.hermesProfileHint')}
                  onChange={(e) => edit('bot-hermes-profile', e.target.value)}
                  onKeyDown={(e) => e.stopPropagation()}
                />
              </label>
            </div>
          )}
          <ol className="ca-agentsetup__steps">
            <li>
              <span>{t('agentSetup.install')}</span>
              {AGENT_DOCS[p.id] && <a href={AGENT_DOCS[p.id]} target="_blank" rel="noopener noreferrer">{t('agentSetup.officialDocs')}</a>}
              <a href={guide} target="_blank" rel="noopener noreferrer">{t('agentSetup.viewGuide')}</a>
            </li>
            <li>
              <span>{t('agentSetup.connect')}</span>
              <div className="ca-agentsetup__code"><pre>{config}</pre><button type="button" className="ca-panel__secondary" onClick={() => copy(p.id)}>{copied === p.id ? t('agentSetup.copied') : t('agentSetup.copy')}</button></div>
            </li>
            <li>
              <button type="button" className="ca-panel__secondary" disabled={checking} onClick={check}>{t('agentSetup.checkAgain')}</button>
            </li>
          </ol>
        </div>
      ))}
    </section>
  )
}
