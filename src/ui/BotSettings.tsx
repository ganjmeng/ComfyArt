import { useEffect, useState } from 'react'
import { useValue } from 'tldraw'

import { BUILTIN_AGENT, botEnabledAtom, providerLabel, providersAtom, refreshBot, saveSettings, settingsAtom, type BotSettings as Settings } from '../bot'
import { errorText } from '../jobs'
import { botSettingsOpenAtom } from './AgentPicker'
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

export function BotSettings({ onError }: { onError: (msg: string) => void }) {
  const open = useValue(botSettingsOpenAtom)
  const settings = useValue(settingsAtom)
  const providers = useValue(providersAtom)
  const enabled = useValue(botEnabledAtom)
  const [draft, setDraft] = useState<Settings>({})

  useEffect(() => {
    if (open) void refreshBot().catch((e) => onError(errorText(e)))
  }, [open])

  useEffect(() => setDraft(settings), [settings])

  if (!open) return null
  const close = () => botSettingsOpenAtom.set(false)
  const save = () => void saveSettings(draft).then(refreshBot).then(close).catch((e) => onError(errorText(e)))

  return (
    <Modal title={t('botSettings.agentSettings')} onClose={close}>
      <div className="ca-rename__body">
        {SWITCHES.map(([key, label]) => (
          <label key={key} className="ca-notice__push">
            <input type="checkbox" checked={!!draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })} />
            <span>{label}</span>
          </label>
        ))}
        <div className="ca-gen__label">{t('botSettings.availableAgents')}</div>
        {!enabled && <div className="ca-chat__hint">{t('botSettings.availableAgentsOnThisMachine')}</div>}
        {providers.map((p) => (
          <div key={p.id} className="ca-keys__row">
            <span>{providerLabel(p)}</span>
            <span className="ca-menu__key" title={p.detail}>{p.available ? p.version || t('botSettings.available') : p.id === BUILTIN_AGENT ? t('botSettings.unavailable') : t('agentPicker.notDetected')}</span>
          </div>
        ))}
        <div className="ca-chat__hint">{t('botSettings.claudeCodeCodexQwenCode')}</div>
        {TEXT_FIELDS.map(([key, label, hint, type]) => (
          <label key={key} className="ca-rename__field">
            <span>{label}</span>
            <input className="ca-panel__input" type={type ?? 'text'} autoComplete="off" value={String(draft[key] ?? '')} placeholder={hint} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} onKeyDown={(e) => e.stopPropagation()} />
          </label>
        ))}
        {FLAGS.map(([key, label]) => (
          <label key={key} className="ca-notice__push">
            <input type="checkbox" checked={!!draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })} />
            <span>{label}</span>
          </label>
        ))}
        <label className="ca-rename__field">
          <span>{t('botSettings.ocrEngine')}</span>
          <select className="ca-panel__input" value={String(draft['ocr-engine'] ?? 'local')} onChange={(e) => setDraft({ ...draft, 'ocr-engine': e.target.value })}>
            <option value="local">{t('botSettings.ocrLocal')}</option>
            <option value="agent">{t('botSettings.ocrAgent')}</option>
          </select>
        </label>
        <div className="ca-panel__foot">
          <button type="button" className="ca-panel__secondary" onClick={close}>{t('common.cancel')}</button>
          <button type="button" className="ca-panel__primary" onClick={save}>{t('common.save')}</button>
        </div>
      </div>
    </Modal>
  )
}
