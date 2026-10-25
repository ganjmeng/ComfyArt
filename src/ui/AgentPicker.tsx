import { atom, useValue } from 'tldraw'

import { BUILTIN_AGENT, chatIdAtom, chatsAtom, defaultProvider, lostProvider, NO_KEY_DETAIL, providerLabel, messagesAtom, newProviderAtom, openChat, providersAtom, saveSettings, settingsAtom, updateChat, type ProviderInfo } from '../bot'
import { errorText } from '../jobs'
import { confirmAtom } from './Confirm'
import { AgentLogo } from './agentLogos'
import { Icons } from './icons'
import { t } from '../i18n'

export const botSettingsOpenAtom = atom('bot settings open', false)
export const agentSetupFocusAtom = atom<string | null>('agent setup focus', null)

// #219: the composer bar shows a short name; the full name stays in the list and on hover
const SHORT_LABELS: Record<string, string> = { 'deepseek-harness': 'DeepSeek' }
// built-in first, then detected tools, then undetected ones
const rank = (p: ProviderInfo) => (p.id === BUILTIN_AGENT ? 0 : p.available ? 1 : 2)
export const shortLabel = (p: ProviderInfo) => (p.id === BUILTIN_AGENT ? t('agentPicker.builtinAgentShort') : SHORT_LABELS[p.id] ?? providerLabel(p))

// #246: the agent list lives in the composer mode menu; same items, ✓, #220 disabled/confirm rules
export function useCurrentAgent() {
  const providers = useValue(providersAtom)
  const chat = useValue('current chat', () => chatsAtom.get().find((c) => c.id === chatIdAtom.get()) ?? null, [])
  const pending = useValue(newProviderAtom)
  const providerId = chat?.provider ?? (pending || defaultProvider())
  return providers.find((p) => p.id === providerId) ?? null
}

export function AgentItems({ onError, current, close, onChosen }: { onError: (msg: string) => void; current: boolean; close: () => void; onChosen: () => void }) {
  const providers = useValue(providersAtom)
  const chat = useValue('current chat', () => chatsAtom.get().find((c) => c.id === chatIdAtom.get()) ?? null, [])
  const started = useValue('chat started', () => messagesAtom.get().length > 0, [])
  const pending = useValue(newProviderAtom)
  const providerId = chat?.provider ?? (pending || defaultProvider())
  const provider = providers.find((p) => p.id === providerId)
  const fail = (e: unknown) => onError(errorText(e))
  const lost = lostProvider()
  const choose = (id: string) => {
    onChosen()
    if (id === providerId) return
    newProviderAtom.set(id)
    void saveSettings({ 'bot-provider': id }).catch(fail)
    if (chat && started) void openChat(null)
  }
  const pick = (id: string) => {
    close()
    if (id === BUILTIN_AGENT || id === providerId || settingsAtom.get()['enable-mcp'] === true) return choose(id)
    confirmAtom.set({
      title: t('agentPicker.enableMcpTitle'),
      desc: t('agentPicker.enableMcpConfirm'),
      ok: t('agentPicker.enableMcpOk'),
      run: () => { void saveSettings({ 'enable-mcp': true }).then(() => choose(id)).catch(fail) },
    })
  }
  return (
    <>
      <div className="ca-agentpick__list">
      {[...providers].sort((x, y) => rank(x) - rank(y)).map((p) => !p.available && p.id !== BUILTIN_AGENT ? (
        // #247: an undetected tool can't be picked; the whole row (40%) opens its setup card instead
        <button key={p.id} type="button" className="ca-menu__item ca-agentpick__row ca-agentpick__off" title={p.detail || p.version} onClick={() => { close(); agentSetupFocusAtom.set(p.id); botSettingsOpenAtom.set(true) }}>
          <AgentLogo id={p.id} />
          <span className="ca-agentpick__text"><span className="ca-agentpick__name">{providerLabel(p)}</span><span className="ca-agentpick__status">{t('agentPicker.notDetected')} · <span className="ca-agentpick__setup">{t('agentSetup.setUp')}</span></span></span>
          <span className="ca-agentpick__check" />
        </button>
      ) : (
        <button key={p.id} type="button" className="ca-menu__item ca-agentpick__row" disabled={!p.available} title={p.detail || p.version} onClick={() => pick(p.id)}>
          <AgentLogo id={p.id} />
          <span className="ca-agentpick__text"><span className="ca-agentpick__name">{providerLabel(p)}</span>{!p.available && <span className="ca-agentpick__status">{t('botSettings.unavailable')}</span>}</span>
          <span className="ca-agentpick__check">{current && p.id === providerId && Icons.check}</span>
        </button>
      ))}
      </div>
      {provider && !provider.available && provider.detail && provider.detail !== NO_KEY_DETAIL && <div className="ca-chat__hint">{provider.detail}</div>}
      {lost && <div className="ca-chat__hint">{t('agentPicker.fellBackToBuiltin', providerLabel(lost))}</div>}
      {chat && started && <div className="ca-chat__hint">{t('agentPicker.switchingAgentStartsANew')}</div>}
    </>
  )
}

// #246: what the old Agent button's menu had below the list (model, ask-before-generating, Agent settings); shown in agent mode only
export function AgentExtras({ onError, close }: { onError: (msg: string) => void; close: () => void }) {
  const providers = useValue(providersAtom)
  const settings = useValue(settingsAtom)
  const chat = useValue('current chat', () => chatsAtom.get().find((c) => c.id === chatIdAtom.get()) ?? null, [])
  const pending = useValue(newProviderAtom)
  const providerId = chat?.provider ?? (pending || defaultProvider())
  const provider = providers.find((p) => p.id === providerId)
  const modelKey = `bot-model-${providerId}`
  const model = String(settings[modelKey] ?? '')
  const options = provider?.model_options ?? provider?.models.map((m) => ({ value: m, label: m, group: '' })) ?? []
  const fail = (e: unknown) => onError(errorText(e))
  return (
    <>
      {options.length > 0 && (
        <>
          <div className="ca-gen__title">{t('agentPicker.model')}</div>
          <select className="ca-panel__input" value={model} onChange={(e) => void saveSettings({ [modelKey]: e.target.value }).catch(fail)}>
            <option value="">{t('common.default')}</option>
            {options.map((o) => <option key={o.value} value={o.value}>{o.group ? `${o.group} · ` : ''}{o.label}</option>)}
          </select>
        </>
      )}
      <label className="ca-notice__push">
        <input
          type="checkbox"
          checked={chat?.run_mode === 'ask'}
          disabled={!chat}
          onChange={(e) => chat && void updateChat(chat.id, { run_mode: e.target.checked ? 'ask' : 'auto' }).catch(fail)}
        />
        <span>{t('agentPicker.askBeforeGenerating', chat ? '' : t('agentPicker.availableAfterTheFirstMessage'))}</span>
      </label>
      <button type="button" className="ca-menu__item" onClick={() => { close(); botSettingsOpenAtom.set(true) }}>
        <span className="ca-icon">{Icons.adjust}</span><span className="ca-menu__grow">{t('agentPicker.agentSettings')}</span>
      </button>
    </>
  )
}
