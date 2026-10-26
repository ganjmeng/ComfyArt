import { useEffect, useState } from 'react'
import { useValue } from 'tldraw'

import { BUILTIN_AGENT, botEnabledAtom, providerLabel, providersAtom, refreshBot, saveSettings, settingsAtom, type BotSettings as Settings, type ProviderInfo } from '../bot'
import { errorText } from '../jobs'
import { agentSetupFocusAtom, botSettingsOpenAtom } from './AgentPicker'
import { docsUrl } from './SettingsMenu'
import { FieldSelect } from './FieldSelect'
import { Modal } from './Modal'
import { t } from '../i18n'

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
const WAVESPEED_HOST = 'llm.wavespeed.ai'
const hostOf = (url: unknown) => { try { return new URL(String(url ?? '').trim()).hostname.toLowerCase() } catch { return '' } }

export function BotSettings({ onError }: { onError: (msg: string) => void }) {
  const open = useValue(botSettingsOpenAtom)
  const settings = useValue(settingsAtom)
  const providers = useValue(providersAtom)
  const enabled = useValue(botEnabledAtom)
  const [draft, setDraft] = useState<Settings>({})
  // #219: a stored custom key belongs to its host; a new host clears it (the backend enforces the same rule)
  const hostChanged = hostOf(draft[URL_KEY]) !== hostOf(settings[URL_KEY])
  const keyCleared = hostChanged && !!settings[KEY_KEY] && hostOf(draft[URL_KEY]) !== WAVESPEED_HOST
  const edit = (key: string, value: string) => {
    const next = { ...draft, [key]: value }
    if (key === URL_KEY && hostOf(value) !== hostOf(settings[URL_KEY]) && draft[KEY_KEY] === settings[KEY_KEY]) next[KEY_KEY] = ''
    if (key === URL_KEY && hostOf(value) === hostOf(settings[URL_KEY])) next[KEY_KEY] = settings[KEY_KEY] ?? ''
    setDraft(next)
  }

  useEffect(() => {
    if (open) void refreshBot().catch((e) => onError(errorText(e)))
  }, [open])

  useEffect(() => setDraft(settings), [settings])

  if (!open) return null
  const close = () => botSettingsOpenAtom.set(false)
  const save = () => void saveSettings(draft).then(() => refreshBot()).then(close).catch((e) => onError(errorText(e)))

  return (
    <Modal className="ca-botsettings" title={t('botSettings.agentSettings')} onClose={close}>
      <div className="ca-rename__body">
        {SWITCHES.map(([key, label]) => (
          <label key={key} className="ca-notice__push">
            <input type="checkbox" checked={!!draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })} />
            <span>{label}</span>
          </label>
        ))}
        {TEXT_FIELDS.map(([key, label, hint, type]) => (
          <label key={key} className="ca-rename__field">
            <span>{label}</span>
            <input className="ca-panel__input" type={type ?? 'text'} autoComplete="off" value={String(draft[key] ?? '')} placeholder={hint} onChange={(e) => edit(key, e.target.value)} onKeyDown={(e) => e.stopPropagation()} />
            {key === KEY_KEY && keyCleared && !draft[KEY_KEY] && <span className="ca-adv__help">{t('botSettings.urlChangedReenterKey')}</span>}
          </label>
        ))}
        <div className="ca-chat__hint">{t('botSettings.claudeCodeCodexQwenCode')}</div>
        <AgentSetup providers={providers} enabled={enabled} onError={onError} />
        {FLAGS.map(([key, label]) => (
          <label key={key} className="ca-notice__push">
            <input type="checkbox" checked={!!draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })} />
            <span>{label}</span>
          </label>
        ))}
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
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={close}>{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary" onClick={save}>{t('common.save')}</button>
        </div>
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
}
export const AGENT_GUIDE_PATH = '/guides/external-agents'
export const mcpConfig = (origin: string) => JSON.stringify({ mcpServers: { comfyart: { type: 'http', url: `${origin}/comfyart/mcp` } } }, null, 2)

function AgentSetup({ providers, enabled, onError }: { providers: ProviderInfo[]; enabled: boolean | null; onError: (msg: string) => void }) {
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
    <section className="ca-agentsetup" data-testid="agent-setup">
      <div className="ca-gen__label">{t('agentSetup.title')}</div>
      <div className="ca-chat__hint">{t('agentSetup.desc')}</div>
      {!enabled && <div className="ca-chat__hint">{t('botSettings.availableAgentsOnThisMachine')}</div>}
      {providers.filter((p) => p.id !== BUILTIN_AGENT).map((p) => (
        <div key={p.id} className="ca-agentsetup__card" data-agent={p.id}>
          <div className="ca-agentsetup__head">
            <span className="ca-agentsetup__name">{providerLabel(p)}</span>
            <span className="ca-agentsetup__chip" data-on={p.available || undefined} title={p.detail || p.version}>{p.available ? t('agentSetup.connected') : t('agentPicker.notDetected')}</span>
          </div>
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
